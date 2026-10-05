import asyncio
import logging
import math
import os
import random
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Optional

import discord
from discord.ext import commands

from .audio import CrossfadeAudio, DynamicEqualizerAudio
from .autodj import AutoDJAnalyzer, TrackAnalysis, TransitionPlan, TransitionPlanner
from .discovery import (
    DiscoveryPreset,
    artist_key,
    discovery_queries,
    matches_preset_policy,
    rank_discovery_tracks,
)
from .errors import MusicError, VoiceStateError
from .effects import AudioEffect, AudioProfile, EqualizerPreset
from .extractor import MediaExtractor
from .models import (
    AudioAnalysisSummary,
    LoopMode,
    PlaybackSnapshot,
    PlaybackState,
    Track,
    TrackSource,
)


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
        autodj_analyzer: Optional[AutoDJAnalyzer] = None,
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
        self._mix_preset: Optional[DiscoveryPreset] = None
        self.autodj_analyzer = autodj_analyzer or AutoDJAnalyzer()
        self.transition_planner = TransitionPlanner(
            float(os.getenv("DJ_CROSSFADE_SECONDS", "6"))
        )
        self._dj_source: Optional[CrossfadeAudio] = None
        self._dj_prefetch_task: Optional[asyncio.Task] = None
        self._dj_current_tempo_ratio = 1.0
        self._dj_source_offset = 0.0
        self._dj_min_playback_ratio = max(
            0.75,
            min(0.97, float(os.getenv("DJ_MIN_PLAYBACK_RATIO", "0.90"))),
        )
        self._early_eof_tolerance = max(
            5,
            min(30, int(os.getenv("DJ_EARLY_EOF_TOLERANCE_SECONDS", "15"))),
        )
        self._early_eof_retries = 0
        self._analysis_task: Optional[asyncio.Task] = None
        self._analysis_track_url: Optional[str] = None
        self._current_analysis: Optional[TrackAnalysis] = None
        self._next_analysis: Optional[TrackAnalysis] = None
        self._analysis_pending = False
        self._smart_window = max(2, min(6, int(os.getenv("DJ_SMART_REORDER_WINDOW", "4"))))
        self._smart_min_gain = max(
            0.02,
            min(0.25, float(os.getenv("DJ_SMART_REORDER_MIN_GAIN", "0.08"))),
        )

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
            should_refresh_dj = self.state.dj_mix and self.state.current is not None

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
            if should_refresh_dj:
                await self._restart_dj_prefetch(guild)

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
                    self._current_analysis = None
                    self._next_analysis = None
                    self._analysis_pending = bool(track.duration)
                    self._early_eof_retries = 0
                    token = self.state.generation
                    volume = self.state.volume
                    profile = self.state.audio_profile
                    dj_mix = (
                        self.state.dj_mix
                        and self.state.loop_mode is LoopMode.OFF
                        and bool(track.duration)
                    )

                try:
                    audio = await self.extractor.create_audio(
                        track,
                        volume,
                        profile=profile,
                        extra_filter=(
                            "dynaudnorm=f=150:g=15:p=0.95" if dj_mix else ""
                        ),
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

                    if dj_mix:
                        self._dj_current_tempo_ratio = 1.0
                        audio = self._crossfade_source(
                            audio,
                            track,
                            token,
                            profile.speed,
                        )
                        self._dj_source = audio
                    else:
                        self._dj_source = None

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
                self._schedule_current_analysis(track, token)
                await self._notify_start(track)
                if dj_mix:
                    self._schedule_dj_prefetch(guild, token)
                return

    async def _track_finished(
        self,
        guild_id: int,
        token: int,
        error: Optional[Exception],
    ) -> None:
        recover_early_eof = False
        async with self.state_lock:
            if token != self.state.generation:
                return
            skipped = self.state.skip_requested
            finished = self.state.current
            listened_seconds = self.state.elapsed()
            source_ended_early = bool(
                self._dj_source
                and self._dj_source.premature_end
                and finished
                and finished.duration
                and listened_seconds < finished.duration - self._early_eof_tolerance
            )
            recover_early_eof = bool(
                source_ended_early
                and not skipped
                and error is None
                and self._early_eof_retries < 1
            )
            if recover_early_eof:
                self._early_eof_retries += 1
                self.state.generation += 1
                token = self.state.generation
            else:
                self.state.finish_current(skipped=skipped, failed=error is not None)
                self._current_analysis = None
                self._next_analysis = None
                self._analysis_pending = False

        if recover_early_eof and finished:
            await self._cancel_dj_prefetch(clear_next=True)
            self._dj_source = None
            if await self._recover_early_eof(guild_id, finished, listened_seconds, token):
                return
            error = RuntimeError("Audio stream ended early and recovery failed")
            async with self.state_lock:
                if token != self.state.generation or self.state.current != finished:
                    return
                self.state.finish_current(failed=True)
                self._current_analysis = None
                self._next_analysis = None
                self._analysis_pending = False

        await self._cancel_dj_prefetch(clear_next=False)
        self._dj_source = None

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

    async def _recover_early_eof(
        self,
        guild_id: int,
        track: Track,
        position: int,
        token: int,
    ) -> bool:
        guild = self.bot.get_guild(guild_id)
        voice_client = guild.voice_client if guild else None
        if not guild or not voice_client:
            return False
        async with self.state_lock:
            volume = self.state.volume
            profile = self.state.audio_profile
        try:
            audio = await self.extractor.create_audio(
                track,
                volume,
                profile=profile,
                seek_seconds=position,
                extra_filter="dynaudnorm=f=150:g=15:p=0.95",
            )
        except Exception:
            logger.exception(
                "early_eof_recovery_prepare_failed guild_id=%s title=%r",
                guild_id,
                track.title,
            )
            return False

        async with self.state_lock:
            if token != self.state.generation or self.state.current != track:
                audio.cleanup()
                return False
            if isinstance(audio, discord.PCMVolumeTransformer):
                audio.volume = self.state.volume
            self._dj_current_tempo_ratio = 1.0
            wrapped = self._crossfade_source(
                audio,
                track,
                token,
                profile.speed,
                playback_offset=position,
            )
            self._dj_source = wrapped

            def after_playback(recovery_error: Optional[Exception]) -> None:
                self.bot.loop.call_soon_threadsafe(
                    asyncio.create_task,
                    self._track_finished(guild_id, token, recovery_error),
                )

            try:
                voice_client.play(wrapped, after=after_playback)
                self.state.mark_started(offset=position, speed=profile.speed)
            except Exception:
                wrapped.cleanup()
                logger.exception("early_eof_recovery_start_failed guild_id=%s", guild_id)
                return False

        logger.warning(
            "early_eof_recovered guild_id=%s position=%ss title=%r",
            guild_id,
            position,
            track.title,
        )
        self._schedule_dj_prefetch(guild, token)
        await self._notify_state_change()
        return True

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
        await self._cancel_dj_prefetch(clear_next=True)
        voice_client.stop()

    async def stop(self, voice_client: Optional[discord.VoiceClient]) -> None:
        await self._cancel_dj_prefetch(clear_next=True)
        self._dj_source = None
        async with self.state_lock:
            finished = self.state.current
            listened_seconds = self.state.elapsed()
            self.state.invalidate(clear_queue=True, reset_loop=True)
            self._current_analysis = None
            self._next_analysis = None
            self._analysis_pending = False
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
        await self._cancel_dj_prefetch(clear_next=True)
        self._dj_source = None
        async with self.state_lock:
            finished = self.state.current
            listened_seconds = self.state.elapsed()
            self.state.invalidate(clear_queue=True, reset_loop=False)
            self._current_analysis = None
            self._next_analysis = None
            self._analysis_pending = False
        if finished:
            await self._notify_end(finished, listened_seconds, completed=False)
        logger.info("voice_disconnected guild_id=%s", self.guild_id)
        await self._notify_state_change()

    async def set_volume(self, level: int, voice_client: Optional[discord.VoiceClient]) -> None:
        async with self.state_lock:
            self.state.volume = level / 100
        if voice_client:
            if isinstance(voice_client.source, discord.PCMVolumeTransformer):
                voice_client.source.volume = level / 100
            elif isinstance(voice_client.source, CrossfadeAudio):
                voice_client.source.set_volume(level / 100)

    async def set_loop_mode(self, mode: LoopMode) -> None:
        async with self.state_lock:
            self.state.loop_mode = mode
        guild = self.bot.get_guild(self.guild_id)
        if mode is not LoopMode.OFF:
            await self._cancel_dj_prefetch(clear_next=True)
        elif guild:
            self._schedule_dj_prefetch(guild, self.state.generation)

    async def set_dj_mix(self, enabled: bool) -> bool:
        async with self.state_lock:
            self.state.dj_mix = enabled
            if not enabled:
                self.state.smart_reorder = False
            generation = self.state.generation
        if not enabled:
            await self._cancel_dj_prefetch(clear_next=True)
        else:
            guild = self.bot.get_guild(self.guild_id)
            if guild:
                self._schedule_dj_prefetch(guild, generation)
        return enabled

    async def set_smart_reorder(self, enabled: bool) -> bool:
        async with self.state_lock:
            self.state.smart_reorder = enabled
            if enabled:
                self.state.dj_mix = True
        guild = self.bot.get_guild(self.guild_id)
        if guild and self.state.dj_mix:
            await self._restart_dj_prefetch(guild)
        return enabled

    async def set_fair_queue(self, enabled: bool) -> bool:
        async with self.state_lock:
            self.state.fair_queue = enabled
            if enabled:
                self.state.smart_reorder = False
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
            self._mix_preset = preset
            self.state.radio_label = preset.label

    async def set_mix_policy(self, preset: DiscoveryPreset) -> None:
        async with self.state_lock:
            self._mix_preset = preset

    def _crossfade_source(
        self,
        audio: discord.AudioSource,
        track: Track,
        token: int,
        profile_speed: float,
        playback_offset: float = 0.0,
    ) -> CrossfadeAudio:
        def on_transition(payload: tuple[Track, TransitionPlan], overlap: float) -> None:
            self.bot.loop.call_soon_threadsafe(
                asyncio.create_task,
                self._dj_promoted(token, payload[0], payload[1], overlap, profile_speed),
            )

        remaining = max(0.0, (track.duration or 0) - playback_offset)
        duration = (remaining / profile_speed) if track.duration else None
        self._dj_source_offset = max(0.0, playback_offset)
        return CrossfadeAudio(audio, duration=duration, on_transition=on_transition)

    def _schedule_dj_prefetch(self, guild: discord.Guild, token: int) -> None:
        if self._dj_prefetch_task and not self._dj_prefetch_task.done():
            return
        self._dj_prefetch_task = asyncio.create_task(
            self._prepare_dj_next(guild, token),
            name=f"autodj-prefetch-{self.guild_id}",
        )

    def _schedule_current_analysis(self, track: Track, token: int) -> None:
        if self._analysis_task and not self._analysis_task.done():
            self._analysis_task.cancel()
        self._analysis_track_url = track.url
        self._analysis_task = asyncio.create_task(
            self._analyze_current(track, token),
            name=f"audio-analysis-{self.guild_id}",
        )

    async def _analyze_current(
        self,
        track: Track,
        token: int,
    ) -> Optional[TrackAnalysis]:
        try:
            analysis = await self.autodj_analyzer.analyze(track)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("current_track_analysis_failed guild_id=%s", self.guild_id)
            analysis = None
        async with self.state_lock:
            if token != self.state.generation or self.state.current != track:
                return analysis
            self._current_analysis = analysis
            self._analysis_pending = False
        await self._notify_state_change()
        return analysis

    async def _restart_dj_prefetch(self, guild: discord.Guild) -> None:
        await self._cancel_dj_prefetch(clear_next=True)
        async with self.state_lock:
            token = self.state.generation
        self._schedule_dj_prefetch(guild, token)

    async def _prepare_dj_next(self, guild: discord.Guild, token: int) -> None:
        audio: Optional[discord.AudioSource] = None
        try:
            async with self.state_lock:
                current = self.state.current
                incoming = self.state.peek_next()
                source = self._dj_source
                if (
                    token != self.state.generation
                    or not self.state.dj_mix
                    or self.state.loop_mode is not LoopMode.OFF
                    or not current
                    or not incoming
                    or not source
                ):
                    return
                volume = self.state.volume
                profile = self.state.audio_profile
                source_offset = self._dj_source_offset
                current_analysis = self._current_analysis
                analysis_task = (
                    self._analysis_task
                    if self._analysis_track_url == current.url
                    else None
                )
                smart_candidates = (
                    tuple(list(self.state.queue)[: self._smart_window])
                    if self.state.smart_reorder
                    and not self.state.fair_queue
                    and self.state.priority_count == 0
                    and len(self.state.queue) > 1
                    else ()
                )

            if not current_analysis:
                current_awaitable = (
                    asyncio.shield(analysis_task)
                    if analysis_task
                    else self.autodj_analyzer.analyze(current)
                )
                current_analysis = await current_awaitable

            incoming_analysis: Optional[TrackAnalysis]
            if current_analysis and smart_candidates:
                candidate_analyses = await asyncio.gather(
                    *(self.autodj_analyzer.analyze(track) for track in smart_candidates)
                )
                scored = [
                    (
                        self._smart_reorder_score(
                            current_analysis,
                            candidate,
                            analysis,
                        ),
                        candidate,
                        analysis,
                    )
                    for candidate, analysis in zip(
                        smart_candidates,
                        candidate_analyses,
                    )
                    if analysis
                ]
                if scored:
                    first_score = next(
                        (score for score, track, _analysis in scored if track == incoming),
                        scored[0][0],
                    )
                    best_score, best_track, best_analysis = max(scored, key=lambda item: item[0])
                    if best_track != incoming and best_score >= first_score + self._smart_min_gain:
                        async with self.state_lock:
                            can_reorder = (
                                token == self.state.generation
                                and self.state.current == current
                                and self.state.smart_reorder
                                and not self.state.fair_queue
                                and self.state.priority_count == 0
                                and best_track in self.state.queue
                            )
                            if can_reorder:
                                self.state.queue.remove(best_track)
                                self.state.queue.appendleft(best_track)
                                incoming = best_track
                                logger.info(
                                    "smart_reorder_selected guild_id=%s score=%.3f previous=%.3f "
                                    "window=%s title=%r",
                                    self.guild_id,
                                    best_score,
                                    first_score,
                                    len(smart_candidates),
                                    best_track.title,
                                )
                    incoming_analysis = next(
                        (
                            analysis
                            for _score, candidate, analysis in scored
                            if candidate == incoming
                        ),
                        None,
                    )
                    if incoming_analysis is None:
                        incoming_analysis = await self.autodj_analyzer.analyze(incoming)
                else:
                    incoming_analysis = await self.autodj_analyzer.analyze(incoming)
            else:
                incoming_analysis = await self.autodj_analyzer.analyze(incoming)
            current_speed = max(0.1, profile.speed * self._dj_current_tempo_ratio)
            incoming_speed = max(0.1, profile.speed)
            current_for_plan = replace(
                current,
                duration=(
                    max(1, round(source.duration))
                    if source.duration
                    else None
                ),
            )
            incoming_for_plan = replace(
                incoming,
                duration=(
                    max(1, round(incoming.duration / incoming_speed))
                    if incoming.duration
                    else None
                ),
            )
            if current_analysis:
                beat_interval = max(1e-6, current_analysis.beat_interval)
                relative_beat_offset = (
                    (current_analysis.beat_offset - source_offset) % beat_interval
                ) / current_speed
                relative_downbeat_offset = (
                    (current_analysis.downbeat_offset - source_offset)
                    % max(1e-6, beat_interval * 4)
                ) / current_speed
                current_analysis = TrackAnalysis(
                    bpm=current_analysis.bpm * current_speed,
                    confidence=current_analysis.confidence,
                    loudness_db=current_analysis.loudness_db,
                    beat_offset=relative_beat_offset,
                    beat_interval=current_analysis.beat_interval / current_speed,
                    key_index=current_analysis.key_index,
                    key_mode=current_analysis.key_mode,
                    key_confidence=current_analysis.key_confidence,
                    energy=current_analysis.energy,
                    vocal_activity=current_analysis.vocal_activity,
                    intro_end=max(0.0, current_analysis.intro_end - source_offset)
                    / current_speed,
                    drop_time=max(0.0, current_analysis.drop_time - source_offset)
                    / current_speed,
                    outro_start=max(0.0, current_analysis.outro_start - source_offset)
                    / current_speed,
                    downbeat_offset=relative_downbeat_offset,
                    structure_confidence=current_analysis.structure_confidence,
                )
            if incoming_analysis:
                incoming_analysis = TrackAnalysis(
                    bpm=incoming_analysis.bpm * incoming_speed,
                    confidence=incoming_analysis.confidence,
                    loudness_db=incoming_analysis.loudness_db,
                    beat_offset=incoming_analysis.beat_offset / incoming_speed,
                    beat_interval=incoming_analysis.beat_interval / incoming_speed,
                    key_index=incoming_analysis.key_index,
                    key_mode=incoming_analysis.key_mode,
                    key_confidence=incoming_analysis.key_confidence,
                    energy=incoming_analysis.energy,
                    vocal_activity=incoming_analysis.vocal_activity,
                    intro_end=incoming_analysis.intro_end / incoming_speed,
                    drop_time=incoming_analysis.drop_time / incoming_speed,
                    outro_start=incoming_analysis.outro_start / incoming_speed,
                    downbeat_offset=incoming_analysis.downbeat_offset / incoming_speed,
                    structure_confidence=incoming_analysis.structure_confidence,
                )
            plan = self.transition_planner.plan(
                current_for_plan,
                incoming_for_plan,
                current_analysis,
                incoming_analysis,
            )
            audio = await self.extractor.create_audio(
                incoming,
                volume,
                profile=profile,
                extra_filter=plan.ffmpeg_filter,
            )

            async with self.state_lock:
                valid = (
                    token == self.state.generation
                    and self.state.current == current
                    and self.state.dj_mix
                    and self.state.peek_next() == incoming
                    and self._dj_source is source
                )
                if not valid:
                    audio.cleanup()
                    audio = None
                    return
                effective_speed = max(0.1, profile.speed * plan.tempo_ratio)
                duration = incoming.duration / effective_speed if incoming.duration else None
                attached = source.set_next(
                    audio,
                    (incoming, plan),
                    duration=duration,
                    crossfade_seconds=plan.crossfade_seconds,
                    start_at_seconds=plan.start_at_seconds,
                    mix_curve=plan.mix_curve,
                    minimum_start_ratio=self._dj_min_playback_ratio,
                )
                if attached:
                    self._next_analysis = incoming_analysis
                    audio = None
                    logger.info(
                        "autodj_transition_ready guild_id=%s mode=%s seconds=%.1f "
                        "start=%.2f bars=%s tempo=%.3f quality=%s harmonic=%.2f "
                        "energy_delta=%.2f vocal_safe=%s keys=%s>%s next=%r",
                        self.guild_id,
                        plan.mode,
                        plan.crossfade_seconds,
                        plan.start_at_seconds or 0.0,
                        plan.phrase_bars,
                        plan.tempo_ratio,
                        plan.quality_score,
                        plan.harmonic_score,
                        plan.energy_delta,
                        plan.vocal_safe,
                        current_analysis.key_label if current_analysis else "Unknown",
                        incoming_analysis.key_label if incoming_analysis else "Unknown",
                        incoming.title,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("autodj_prefetch_failed guild_id=%s", self.guild_id)
        finally:
            if audio:
                audio.cleanup()

    def _smart_reorder_score(
        self,
        current: TrackAnalysis,
        candidate: Track,
        analysis: TrackAnalysis,
    ) -> float:
        genre_match = (
            1.0
            if self._mix_preset and matches_preset_policy(candidate, self._mix_preset)
            else 0.5
        )
        popularity = min(1.0, math.log10(max(0, candidate.view_count or 0) + 10) / 7.0)
        return self.transition_planner.smart_reorder_score(
            current,
            analysis,
            genre_match=genre_match,
            popularity=popularity,
        )

    async def _dj_promoted(
        self,
        token: int,
        incoming: Track,
        plan: TransitionPlan,
        overlap: float,
        profile_speed: float,
    ) -> None:
        async with self.state_lock:
            if token != self.state.generation or not self.state.dj_mix:
                return
            finished = self.state.current
            listened_seconds = self.state.elapsed()
            speed = max(0.1, profile_speed * plan.tempo_ratio)
            if not self.state.promote(incoming, offset=overlap * speed, speed=speed):
                return
            self._dj_current_tempo_ratio = plan.tempo_ratio
            self._current_analysis = self._next_analysis
            self._next_analysis = None
            self._analysis_pending = self._current_analysis is None
            self._dj_source_offset = 0.0
            self._early_eof_retries = 0

        if finished:
            await self._notify_end(finished, listened_seconds, completed=True)
        self._autoplay_recent.append(incoming.url)
        self._autoplay_recent_artists.append(artist_key(incoming))
        logger.info(
            "autodj_transition_complete guild_id=%s mode=%s title=%r",
            self.guild_id,
            plan.mode,
            incoming.title,
        )
        await self._notify_start(incoming)
        guild = self.bot.get_guild(self.guild_id)
        if guild:
            await self._fill_autoplay(incoming, allow_current=True)
            self._schedule_dj_prefetch(guild, token)

    async def _cancel_dj_prefetch(self, *, clear_next: bool) -> None:
        task = self._dj_prefetch_task
        self._dj_prefetch_task = None
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if clear_next and self._dj_source:
            self._dj_source.clear_next()

    async def _fill_autoplay(self, seed: Track, *, allow_current: bool = False) -> None:
        async with self.state_lock:
            if (
                not self.state.autoplay
                or (self.state.current and not allow_current)
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
                or (self.state.current and not allow_current)
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
        refresh_dj = False
        async with self.state_lock:
            profile = replace(self.state.audio_profile, equalizer=equalizer)
            processor = self._equalizer_source(voice_client)
            if processor:
                self.state.audio_profile = profile
                processor.set_preset(equalizer)
                refresh_dj = self.state.dj_mix
            has_current = self.state.current is not None
        if processor:
            if refresh_dj:
                await self._restart_dj_prefetch(guild)
            return profile
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
        if isinstance(source, CrossfadeAudio):
            source = source.original
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

            await self._cancel_dj_prefetch(clear_next=True)
            audio = await self.extractor.create_audio(
                track,
                volume,
                profile=profile,
                seek_seconds=position,
                extra_filter=(
                    "dynaudnorm=f=150:g=15:p=0.95" if self.state.dj_mix else ""
                ),
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

                if self.state.dj_mix and track.duration and self.state.loop_mode is LoopMode.OFF:
                    self._dj_current_tempo_ratio = 1.0
                    audio = self._crossfade_source(
                        audio,
                        track,
                        token,
                        profile.speed,
                        playback_offset=position,
                    )
                    self._dj_source = audio
                else:
                    self._dj_source = None

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
                    elif self._dj_source:
                        self._schedule_dj_prefetch(guild, token)
                except Exception:
                    audio.cleanup()
                    raise

    async def shuffle(self) -> int:
        await self._cancel_dj_prefetch(clear_next=True)
        async with self.state_lock:
            if len(self.state.queue) < 2:
                return len(self.state.queue)
            tracks = list(self.state.queue)
            random.shuffle(tracks)
            self.state.queue.clear()
            self.state.queue.extend(tracks)
            self.state.priority_count = 0
            count = len(tracks)
        guild = self.bot.get_guild(self.guild_id)
        if guild:
            self._schedule_dj_prefetch(guild, self.state.generation)
        return count

    async def clear_queue(self) -> int:
        await self._cancel_dj_prefetch(clear_next=True)
        async with self.state_lock:
            count = len(self.state.queue)
            self.state.queue.clear()
            self.state.priority_count = 0
            return count

    async def snapshot(self) -> PlaybackSnapshot:
        async with self.state_lock:
            snapshot = self.state.snapshot()
            analysis = self._current_analysis
            summary = (
                AudioAnalysisSummary(
                    bpm=analysis.bpm,
                    key=analysis.camelot_key,
                    key_name=analysis.key_label,
                    key_confidence=analysis.key_confidence,
                    energy=analysis.energy,
                    vocal_activity=analysis.vocal_activity,
                )
                if analysis
                else None
            )
            return replace(
                snapshot,
                analysis=summary,
                analysis_pending=self._analysis_pending,
            )

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
        self.autodj_analyzer = AutoDJAnalyzer()
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
                autodj_analyzer=self.autodj_analyzer,
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
