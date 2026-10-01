import logging
from typing import TYPE_CHECKING

import discord

from ..effects import AudioEffect, EqualizerPreset
from ..errors import MusicError
from .player import require_control_voice

if TYPE_CHECKING:
    from .player import PlayerUI


logger = logging.getLogger(__name__)


EFFECT_META = {
    AudioEffect.OFF: ("Tắt", "Âm thanh nguyên bản", "🔈"),
    AudioEffect.BASS_BOOST: ("Bass Boost", "Tăng lực dải trầm", "🔊"),
    AudioEffect.SLOW_REVERB: ("Slow + Reverb", "Chậm và vang nhẹ", "🌙"),
    AudioEffect.AUDIO_8D: ("8D Audio", "Âm thanh di chuyển hai bên", "🌌"),
    AudioEffect.NIGHTCORE: ("Nightcore", "Nhanh và cao hơn", "⚡"),
    AudioEffect.VAPORWAVE: ("Vaporwave", "Chậm, trầm và hoài cổ", "📼"),
    AudioEffect.REVERB: ("Reverb", "Không gian vang mềm", "🏛️"),
}

EQ_META = {
    EqualizerPreset.BALANCED: ("Cân bằng", "Giữ nguyên phổ âm", "🟣"),
    EqualizerPreset.BASS: ("Bass mạnh", "Nhấn dải 64–125 Hz", "💜"),
    EqualizerPreset.CHILL: ("Chill", "Trầm ấm, treble dịu", "🩵"),
    EqualizerPreset.VOCAL: ("Vocal", "Làm rõ giọng hát", "💗"),
    EqualizerPreset.GAMING: ("Gaming", "Rõ bass và chi tiết", "💚"),
    EqualizerPreset.ACOUSTIC: ("Acoustic", "Ấm và tự nhiên", "🍑"),
    EqualizerPreset.EDM: ("EDM", "Bass và treble giàu năng lượng", "⚡"),
}


class EffectSelect(discord.ui.Select):
    def __init__(self, parent: "AudioSettingsView", current: AudioEffect) -> None:
        options = [
            discord.SelectOption(
                label=label,
                description=description,
                emoji=emoji,
                value=effect.value,
                default=effect is current,
            )
            for effect, (label, description, emoji) in EFFECT_META.items()
        ]
        super().__init__(placeholder="✨ Chọn hiệu ứng", options=options, row=0)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.parent_view.apply_effect(interaction, AudioEffect(self.values[0]))


class EqualizerSelect(discord.ui.Select):
    def __init__(self, parent: "AudioSettingsView", current: EqualizerPreset) -> None:
        options = [
            discord.SelectOption(
                label=label,
                description=description,
                emoji=emoji,
                value=preset.value,
                default=preset is current,
            )
            for preset, (label, description, emoji) in EQ_META.items()
        ]
        super().__init__(placeholder="🎚️ Chọn equalizer", options=options, row=1)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.parent_view.apply_equalizer(interaction, EqualizerPreset(self.values[0]))


class AudioSettingsView(discord.ui.View):
    def __init__(
        self,
        ui: "PlayerUI",
        guild_id: int,
        owner_id: int,
        effect: AudioEffect,
        equalizer: EqualizerPreset,
    ) -> None:
        super().__init__(timeout=300)
        self.ui = ui
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.effect = effect
        self.equalizer = equalizer
        self.add_item(EffectSelect(self, effect))
        self.add_item(EqualizerSelect(self, equalizer))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Bảng âm thanh này thuộc người dùng khác.", ephemeral=True)
        return False

    def embed(self) -> discord.Embed:
        effect_label = EFFECT_META[self.effect][0]
        eq_label = EQ_META[self.equalizer][0]
        active = self.effect is not AudioEffect.OFF or self.equalizer is not EqualizerPreset.BALANCED
        embed = discord.Embed(
            title="🎚️ ÂM THANH NÂNG CAO",
            description=(
                "Preset được áp dụng cho bài hiện tại và các bài tiếp theo."
                if active
                else "Âm thanh đang ở trạng thái nguyên bản."
            ),
            color=0xA78BFA if active else 0x7DD3FC,
        )
        embed.add_field(name="✨ Hiệu ứng", value=effect_label, inline=True)
        embed.add_field(name="🎚️ Equalizer", value=eq_label, inline=True)
        embed.add_field(
            name="Trạng thái",
            value="ĐANG BẬT" if active else "CÂN BẰNG",
            inline=True,
        )
        embed.set_footer(text="KSC Music · FFmpeg audio processing")
        return embed

    async def _prepare(self, interaction: discord.Interaction):
        session = await self.ui.bind_interaction(interaction)
        voice = await require_control_voice(interaction)
        await interaction.response.defer(ephemeral=True)
        return session, voice

    async def apply_effect(
        self,
        interaction: discord.Interaction,
        effect: AudioEffect,
    ) -> None:
        try:
            session, voice = await self._prepare(interaction)
            profile = await session.set_effect(interaction.guild, voice, effect)
            embed, view = await audio_payload(self.ui, self.guild_id, self.owner_id)
            await interaction.edit_original_response(embed=embed, view=view)
            self.effect = profile.effect
        except MusicError as error:
            await self._send_error(interaction, error.message)
        except Exception:
            logger.exception("effect_apply_failed guild_id=%s", interaction.guild_id)
            await self._send_error(interaction, "Không thể áp dụng hiệu ứng lúc này.")

    async def apply_equalizer(
        self,
        interaction: discord.Interaction,
        equalizer: EqualizerPreset,
    ) -> None:
        try:
            session, voice = await self._prepare(interaction)
            profile = await session.set_equalizer(interaction.guild, voice, equalizer)
            embed, view = await audio_payload(self.ui, self.guild_id, self.owner_id)
            await interaction.edit_original_response(embed=embed, view=view)
            self.equalizer = profile.equalizer
        except MusicError as error:
            await self._send_error(interaction, error.message)
        except Exception:
            logger.exception("equalizer_apply_failed guild_id=%s", interaction.guild_id)
            await self._send_error(interaction, "Không thể áp dụng equalizer lúc này.")

    @discord.ui.button(label="Reset", emoji="↩️", style=discord.ButtonStyle.danger, row=2)
    async def reset(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session, voice = await self._prepare(interaction)
            await session.reset_audio(interaction.guild, voice)
            embed, view = await audio_payload(self.ui, self.guild_id, self.owner_id)
            await interaction.edit_original_response(embed=embed, view=view)
        except MusicError as error:
            await self._send_error(interaction, error.message)
        except Exception:
            logger.exception("audio_reset_failed guild_id=%s", interaction.guild_id)
            await self._send_error(interaction, "Không thể đặt lại âm thanh lúc này.")

    @staticmethod
    async def _send_error(interaction: discord.Interaction, message: str) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def audio_payload(
    ui: "PlayerUI",
    guild_id: int,
    owner_id: int,
) -> tuple[discord.Embed, AudioSettingsView]:
    profile = (await ui.manager.session(guild_id).snapshot()).audio_profile
    view = AudioSettingsView(
        ui,
        guild_id,
        owner_id,
        profile.effect,
        profile.equalizer,
    )
    return view.embed(), view
