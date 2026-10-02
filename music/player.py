import asyncio
import logging
import random
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Optional

import discord
from discord.ext import commands

from .audio import DynamicEqualizerAudio
from .discovery import DiscoveryPreset, artist_key, discovery_queries, rank_discovery_tracks
from .errors import MusicError, VoiceStateError
from .effects import AudioEffect, AudioProfile, EqualizerPreset
from .extractor import MediaExtractor
from .models import LoopMode, PlaybackSnapshot, PlaybackState, Track, TrackSource


logger = logging.getLogger(__name__)
TrackCallback = Callable[[int, Track], Awaitable[None]]
TrackEndCallback = Callable[[int, Track, int, bool], Awaitable[None]]
TrackErrorCallback = Callable[[int, Track, Exception], Awaitable[None]]
StateCallback = Callable[[int], Awaitable[None]]


async def _noop_track(_guild_id: int, _track: Track) -> None:
    return None


async def _noop_error(_guild_id: int, _track: Track, _error: Exception) -> None:
    return None


async def _noop_end(
    _guild_id: int,
    _track: Track,
    _listened_seconds: int,
    _completed: bool,
) -> None:
    return None


async def _noop_state(_guild_id: int) -> None:
    return None


class GuildPlayerSession:
    def __init__(
        self,
        bot: commands.Bot,
        guild_id: int,
        extractor: MediaExtractor,
        *,
        on_track_start: TrackCallback = _noop_track,
        on_track_end: TrackEndCallback = _noop_end,
        on_track_error: TrackErrorCallback = _noop_error,
        on_state_change: StateCallback = _noop_state,
    ) -> None:
        self.bot = bot
        self.guild_id = guild_id
        self.extractor = extractor
        self.state = PlaybackState()
        self.text_channel: Optional[discord.abc.Messageable] = None
        self.player_message: Optional[discord.Message] = None
        self.on_track_start = on_track_start
        self.on_track_end = on_track_end
        self.on_track_error = on_track_error
        self.on_state_change = on_state_change
        self.state_lock = asyncio.Lock()
        self.request_lock = asyncio.Lock()
        self.start_lock = asyncio.Lock()
        self.connection_lock = asyncio.Lock()
        self.ui_lock = asyncio.Lock()
        self._autoplay_recent: deque[str] = deque(maxlen=20)
        self._autoplay_recent_artists: deque[str] = deque(maxlen=5)
        self._radio_preset: Optional[DiscoveryPreset] = None

    async def enqueue_request(
        self,
        guild: discord.Guild,
        voice_channel: discord.abc.Connectable,
        text_channel: discord.abc.Messageable,
        query: str,
        *,
        requester_id: Optional[int],
        requester_name: Optional[str],
        source_hint: Optional[TrackSource] = None,
    ) -> list[Track]:
        # Serializing requests preserves queue order even when extractors finish at different times.
        async with self.request_lock:
            tracks = await self.extractor.extract_tracks(
                query,
                requester_id=requester_id,
                requester_name=requester_name,
                source_hint=source_hint,
            )
            await self.enqueue_tracks(
                guild,
                voice_channel,
                text_channel,
                tracks,
                position="end",
            )
            return tracks

    async def enqueue_tracks(
        self,
        guild: discord.Guild,
        voice_channel: discord.abc.Connectable,
        text_channel: discord.abc.Messageable,
        tracks: list[Track],
        *,
        position: str = "end",
    ) -> None:
        if position not in {"end", "next", "now"}:
            raise ValueError(f"Unknown queue position: {position}")
        await self.ensure_voice(guild, voice_channel)
        voice_client = guild.voice_client
        stop_current = False
        async with self.state_lock:
            self.text_channel = text_channel
            if position == "end":
                self.state.enqueue(tracks)
            else:
                self.state.enqueue_front(tracks)
                if position == "now" and self.state.current:
                    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                        self.state.skip_requested = True
                        stop_current = True
                    else:
                        # The current track is still being prepared. Invalidate its token so
                        # the late FFmpeg result is cleaned up before the new track starts.
                        self.state.invalidate(clear_queue=False)
            queue_size = len(self.state.queue)

        logger.info(
            "tracks_enqueued guild_id=%s count=%s position=%s queue_size=%s",
            self.guild_id,
            len(tracks),
            position,
            queue_size,
        )
        if stop_current and voice_client:
            voice_client.stop()
        else:
            await self.start_next(guild)

    async def ensure_voice(
        self,
        guild: discord.Guild,
        target_channel: discord.abc.Connectable,
    ) -> discord.VoiceClient:
        async with self.connection_lock:
            voice_client = guild.voice_client
            if not voice_client:
                logger.info("voice_connect guild_id=%s channel_id=%s", guild.id, target_channel.id)
                return await target_channel.connect(self_deaf=True)
            if voice_client.channel != target_channel:
                if voice_client.is_playing() or voice_client.is_paused():
                    raise VoiceStateError(
                        f"Bot đang phát nhạc trong **{voice_client.channel.name}**."
                    )
                logger.info("voice_move guild_id=%s channel_id=%s", guild.id, target_channel.id)
                await voice_client.move_to(target_channel)
            return voice_client

    async def start_next(self, guild: discord.Guild) -> None:
        async with self.start_lock:
            while True:
                voice_client = guild.voice_client
                if not voice_client:
                    return

                async with self.state_lock:
                    if (
                        self.state.current
                        or voice_client.is_playing()
                        or voice_client.is_paused()
                    ):
                        return
                    track = self.state.claim_next()
                    if not track:
                        return
                    token = self.state.generation
                    volume = self.state.volume
                    profile = self.state.audio_profile

                try:
                    audio = await self.extractor.create_audio(
                        track,
                        volume,
                        profile=profile,
                    )
                except Exception as error:
                    async with self.state_lock:
                        if token == self.state.generation and self.state.current == track:
                            self.state.finish_current(failed=True)
                    logger.warning(
                        "track_prepare_failed guild_id=%s source=%s error=%s",
                        self.guild_id,
                        track.source.value,
                        error,
                    )
                    await self._notify_error(track, error)
                    continue

                voice_client = guild.voice_client
                start_error: Optional[Exception] = None
                async with self.state_lock:
                    stale = (
                        token != self.state.generation
                        or self.state.current != track
                        or not voice_client
                    )
                    if stale:
                        audio.cleanup()
                        return

                    if isinstance(audio, discord.PCMVolumeTransformer):
                        audio.volume = self.state.volume

                    def after_playback(error: Optional[Exception]) -> None:
                        self.bot.loop.call_soon_threadsafe(
                            asyncio.create_task,
                            self._track_finished(guild.id, token, error),
                        )

                    try:
                        voice_client.play(audio, after=after_playback)
                        self.state.mark_started(speed=profile.speed)
                    except Exception as error:
                        audio.cleanup()
                        self.state.finish_current(failed=True)
                        start_error = error

                if start_error:
                    logger.warning(
                        "track_start_failed guild_id=%s source=%s error=%s",
                        self.guild_id,
                        track.source.value,
                        start_error,
                    )
                    await self._notify_error(track, start_error)
                    continue

                logger.info(
                    "track_started guild_id=%s source=%s title=%r",
                    self.guild_id,
                    track.source.value,
                    track.title,
                )
                self._autoplay_recent.append(track.url)
                self._autoplay_recent_artists.append(artist_key(track))
                await self._notify_start(track)
                return

    async def _track_finished(
        self,
        guild_id: int,
        token: int,
        error: Optional[Exception],
    ) -> None:
        async with self.state_lock:
            if token != self.state.generation:
                return
            skipped = self.state.skip_requested
            finished = self.state.current
            listened_seconds = self.state.elapsed()
            self.state.finish_current(skipped=skipped, failed=error is not None)

        if finished:
            await self._notify_end(
                finished,
                listened_seconds,
                completed=not skipped and error is None,
            )

        if error:
            logger.warning("playback_failed guild_id=%s error=%s", guild_id, error)
            if finished:
                await self._notify_error(finished, error)

        guild = self.bot.get_guild(guild_id)
        if guild:
            if finished:
                await self._fill_autoplay(finished)
            await self.start_next(guild)
            if (await self.snapshot()).current is None:
                await self._notify_state_change()

    async def pause(self, voice_client: discord.VoiceClient) -> None:
        if not voice_client.is_playing():
            raise MusicError("Không có bài nào đang phát.", code="nothing_playing")
        voice_client.pause()
        async with self.state_lock:
            self.state.mark_paused()

    async def resume(self, voice_client: discord.VoiceClient) -> None:
        if not voice_client.is_paused():
            raise MusicError("Nhạc hiện không bị tạm dừng.", code="not_paused")
        voice_client.resume()
        async with self.state_lock:
            self.state.mark_resumed()

    async def skip(self, voice_client: discord.VoiceClient) -> None:
        if not voice_client.is_playing() and not voice_client.is_paused():
            raise MusicError("Không có bài nào để bỏ qua.", code="nothing_playing")
        async with self.state_lock:
            self.state.skip_requested = True
        voice_client.stop()

    async def stop(self, voice_client: Optional[discord.VoiceClient]) -> None:
        async with self.state_lock:
            finished = self.state.current
            listened_seconds = self.state.elapsed()
            self.state.invalidate(clear_queue=True, reset_loop=True)
        if finished:
            await self._notify_end(finished, listened_seconds, completed=False)
        if not voice_client:
            return
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
        await voice_client.disconnect(force=True)
        logger.info("player_stopped guild_id=%s", self.guild_id)
        await self._notify_state_change()

    async def handle_external_disconnect(self) -> None:
        async with self.state_lock:
            finished = self.state.current
            listened_seconds = self.state.elapsed()
            self.state.invalidate(clear_queue=True, reset_loop=False)
        if finished:
            await self._notify_end(finished, listened_seconds, completed=False)
        logger.info("voice_disconnected guild_id=%s", self.guild_id)
        await self._notify_state_change()

    async def set_volume(self, level: int, voice_client: Optional[discord.VoiceClient]) -> None:
        async with self.state_lock:
            self.state.volume = level / 100
        if voice_client and isinstance(voice_client.source, discord.PCMVolumeTransformer):
            voice_client.source.volume = level / 100

    async def set_loop_mode(self, mode: LoopMode) -> None:
        async with self.state_lock:
            self.state.loop_mode = mode

    async def set_fair_queue(self, enabled: bool) -> bool:
        async with self.state_lock:
            self.state.fair_queue = enabled
            return self.state.fair_queue

    async def set_autoplay(self, enabled: bool) -> bool:
        async with self.state_lock:
            self.state.autoplay = enabled
            if not enabled:
                self._radio_preset = None
                self.state.radio_label = None
            return self.state.autoplay

    async def set_radio_policy(self, preset: DiscoveryPreset) -> None:
        async with self.state_lock:
            self._radio_preset = preset
            self.state.radio_label = preset.label

    async def _fill_autoplay(self, seed: Track) -> None:
        async with self.state_lock:
            if (
                not self.state.autoplay
                or self.state.current
                or self.state.queue
                or self.state.loop_mode is not LoopMode.OFF
            ):
                return

        preset = self._radio_preset
        query = (
            discovery_queries(preset)[len(self._autoplay_recent) % 3]
            if preset
            else " ".join(part for part in (seed.uploader, seed.title, "mix") if part)
        )
        try:
            results = await self.extractor.search_tracks(
                query,
                requester_id=None,
                requester_name="Radio" if preset else "Tự phát",
                source_hint=None if preset else seed.source,
                limit=10 if preset else 5,
            )
        except MusicError as error:
            logger.info("autoplay_search_failed guild_id=%s error=%s", self.guild_id, error)
            return
        except Exception:
            logger.exception("autoplay_search_unexpected guild_id=%s", self.guild_id)
            return

        excluded = set(self._autoplay_recent)
        excluded.add(seed.url)
        if preset:
            ranked = rank_discovery_tracks(results, preset, limit=10, artist_gap=4)
            recent_artists = set(self._autoplay_recent_artists)
            candidate = next(
                (
                    track
                    for track in ranked
                    if track.url not in excluded and artist_key(track) not in recent_artists
                ),
                None,
            )
        else:
            candidate = next((track for track in results if track.url not in excluded), None)
        if not candidate:
            logger.info("autoplay_no_candidate guild_id=%s", self.guild_id)
            return

        async with self.state_lock:
            if (
                not self.state.autoplay
                or self.state.current
                or self.state.queue
                or self.state.loop_mode is not LoopMode.OFF
            ):
                return
            self.state.enqueue([candidate])
        logger.info(
            "autoplay_enqueued guild_id=%s source=%s title=%r",
            self.guild_id,
            candidate.source.value,
            candidate.title,
        )

    async def set_effect(
        self,
        guild: discord.Guild,
        voice_client: discord.VoiceClient,
        effect: AudioEffect,
    ) -> AudioProfile:
        async with self.state_lock:
            profile = replace(self.state.audio_profile, effect=effect)
        await self._apply_audio_profile(guild, voice_client, profile)
        return profile

    async def set_equalizer(
        self,
        guild: discord.Guild,
        voice_client: discord.VoiceClient,
        equalizer: EqualizerPreset,
    ) -> AudioProfile:
        async with self.state_lock:
            profile = replace(self.state.audio_profile, equalizer=equalizer)
            processor = self._equalizer_source(voice_client)
            if processor:
                self.state.audio_profile = profile
                processor.set_preset(equalizer)
                return profile
            has_current = self.state.current is not None
        if has_current and (voice_client.is_playing() or voice_client.is_paused()):
            await self._apply_audio_profile(guild, voice_client, profile)
        else:
            async with self.state_lock:
                self.state.audio_profile = profile
        return profile

    async def reset_audio(
        self,
        guild: discord.Guild,
        voice_client: discord.VoiceClient,
    ) -> AudioProfile:
        profile = AudioProfile()
        async with self.state_lock:
            current_profile = self.state.audio_profile
        if current_profile.effect is AudioEffect.OFF:
            await self.set_equalizer(guild, voice_client, EqualizerPreset.BALANCED)
        else:
            await self._apply_audio_profile(guild, voice_client, profile)
        return profile

    @staticmethod
    def _equalizer_source(
        voice_client: discord.VoiceClient,
    ) -> Optional[DynamicEqualizerAudio]:
        source = getattr(voice_client, "source", None)
        if isinstance(source, discord.PCMVolumeTransformer):
            source = source.original
        return source if isinstance(source, DynamicEqualizerAudio) else None

    async def _apply_audio_profile(
        self,
        guild: discord.Guild,
        voice_client: discord.VoiceClient,
        profile: AudioProfile,
    ) -> None:
        async with self.start_lock:
            async with self.state_lock:
                track = self.state.current
                if not track or not (voice_client.is_playing() or voice_client.is_paused()):
                    self.state.audio_profile = profile
                    return
                generation = self.state.generation
                position = self.state.elapsed()
                volume = self.state.volume
                was_paused = voice_client.is_paused()

            audio = await self.extractor.create_audio(
                track,
                volume,
                profile=profile,
                seek_seconds=position,
            )

            async with self.state_lock:
                if generation != self.state.generation or track != self.state.current:
                    audio.cleanup()
                    return
                self.state.audio_profile = profile
                self.state.generation += 1
                token = self.state.generation
                voice_client.stop()

                if isinstance(audio, discord.PCMVolumeTransformer):
                    audio.volume = self.state.volume

                def after_playback(error: Optional[Exception]) -> None:
                    self.bot.loop.call_soon_threadsafe(
                        asyncio.create_task,
                        self._track_finished(guild.id, token, error),
                    )

                try:
                    voice_client.play(audio, after=after_playback)
                    self.state.mark_started(offset=position, speed=profile.speed)
                    if was_paused:
                        voice_client.pause()
                        self.state.mark_paused()
                except Exception:
                    audio.cleanup()
                    raise

    async def shuffle(self) -> int:
        async with self.state_lock:
            if len(self.state.queue) < 2:
                return len(self.state.queue)
            tracks = list(self.state.queue)
            random.shuffle(tracks)
            self.state.queue.clear()
            self.state.queue.extend(tracks)
            self.state.priority_count = 0
            return len(tracks)

    async def clear_queue(self) -> int:
        async with self.state_lock:
            count = len(self.state.queue)
            self.state.queue.clear()
            self.state.priority_count = 0
            return count

    async def snapshot(self) -> PlaybackSnapshot:
        async with self.state_lock:
            return self.state.snapshot()

    async def _notify_start(self, track: Track) -> None:
        try:
            await self.on_track_start(self.guild_id, track)
        except Exception:
            logger.exception("track_start_callback_failed guild_id=%s", self.guild_id)

    async def _notify_error(self, track: Track, error: Exception) -> None:
        try:
            await self.on_track_error(self.guild_id, track, error)
        except Exception:
            logger.exception("track_error_callback_failed guild_id=%s", self.guild_id)

    async def _notify_end(
        self,
        track: Track,
        listened_seconds: int,
        *,
        completed: bool,
    ) -> None:
        try:
            await self.on_track_end(
                self.guild_id,
                track,
                listened_seconds,
                completed,
            )
        except Exception:
            logger.exception("track_end_callback_failed guild_id=%s", self.guild_id)

    async def _notify_state_change(self) -> None:
        try:
            await self.on_state_change(self.guild_id)
        except Exception:
            logger.exception("state_callback_failed guild_id=%s", self.guild_id)


class MusicPlayerManager:
    def __init__(
        self,
        bot: commands.Bot,
        extractor: Optional[MediaExtractor] = None,
        *,
        on_track_start: TrackCallback = _noop_track,
        on_track_end: TrackEndCallback = _noop_end,
        on_track_error: TrackErrorCallback = _noop_error,
        on_state_change: StateCallback = _noop_state,
    ) -> None:
        self.bot = bot
        self.extractor = extractor or MediaExtractor()
        self.on_track_start = on_track_start
        self.on_track_end = on_track_end
        self.on_track_error = on_track_error
        self.on_state_change = on_state_change
        self.sessions: dict[int, GuildPlayerSession] = {}

    def session(self, guild_id: int) -> GuildPlayerSession:
        if guild_id not in self.sessions:
            self.sessions[guild_id] = GuildPlayerSession(
                self.bot,
                guild_id,
                self.extractor,
                on_track_start=self.on_track_start,
                on_track_end=self.on_track_end,
                on_track_error=self.on_track_error,
                on_state_change=self.on_state_change,
            )
        return self.sessions[guild_id]

    async def remove_guild(self, guild: discord.Guild) -> None:
        session = self.sessions.pop(guild.id, None)
        if session:
            await session.stop(guild.voice_client)

    async def close(self) -> None:
        sessions = list(self.sessions.items())
        self.sessions.clear()
        for guild_id, session in sessions:
            guild = self.bot.get_guild(guild_id)
            await session.stop(guild.voice_client if guild else None)
