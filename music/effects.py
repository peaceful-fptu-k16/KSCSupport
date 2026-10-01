from dataclasses import dataclass
from enum import Enum


class AudioEffect(str, Enum):
    OFF = "off"
    BASS_BOOST = "bass_boost"
    SLOW_REVERB = "slow_reverb"
    AUDIO_8D = "8d"
    NIGHTCORE = "nightcore"
    VAPORWAVE = "vaporwave"
    REVERB = "reverb"

    @property
    def label(self) -> str:
        return {
            self.OFF: "Tắt",
            self.BASS_BOOST: "Bass Boost",
            self.SLOW_REVERB: "Slow + Reverb",
            self.AUDIO_8D: "8D Audio",
            self.NIGHTCORE: "Nightcore",
            self.VAPORWAVE: "Vaporwave",
            self.REVERB: "Reverb",
        }[self]

    @classmethod
    def parse(cls, value: str) -> "AudioEffect":
        normalized = value.lower().strip().replace("-", "_").replace(" ", "_")
        aliases = {
            "bass": "bass_boost",
            "slow": "slow_reverb",
            "slowreverb": "slow_reverb",
            "audio8d": "8d",
            "none": "off",
            "tat": "off",
        }
        return cls(aliases.get(normalized, normalized))


class EqualizerPreset(str, Enum):
    BALANCED = "balanced"
    BASS = "bass"
    CHILL = "chill"
    VOCAL = "vocal"
    GAMING = "gaming"
    ACOUSTIC = "acoustic"
    EDM = "edm"

    @property
    def label(self) -> str:
        return {
            self.BALANCED: "Cân bằng",
            self.BASS: "Bass mạnh",
            self.CHILL: "Chill",
            self.VOCAL: "Vocal",
            self.GAMING: "Gaming",
            self.ACOUSTIC: "Acoustic",
            self.EDM: "EDM",
        }[self]

    @classmethod
    def parse(cls, value: str) -> "EqualizerPreset":
        normalized = value.lower().strip().replace("-", "_").replace(" ", "_")
        aliases = {
            "flat": "balanced",
            "canbang": "balanced",
            "voice": "vocal",
        }
        return cls(aliases.get(normalized, normalized))


EFFECT_FILTERS = {
    AudioEffect.OFF: "",
    AudioEffect.BASS_BOOST: "bass=g=8:f=110:w=0.6",
    AudioEffect.SLOW_REVERB: "atempo=0.9,aecho=0.8:0.85:60:0.25",
    AudioEffect.AUDIO_8D: "apulsator=hz=0.12:amount=0.75",
    AudioEffect.NIGHTCORE: "asetrate=48000*1.15,aresample=48000",
    AudioEffect.VAPORWAVE: "asetrate=48000*0.85,aresample=48000,aecho=0.8:0.82:55:0.2",
    AudioEffect.REVERB: "aecho=0.8:0.88:60:0.35",
}

EQUALIZER_FILTERS = {
    EqualizerPreset.BALANCED: "",
    EqualizerPreset.BASS: "equalizer=f=64:t=q:w=1:g=6,equalizer=f=125:t=q:w=1:g=4",
    EqualizerPreset.CHILL: "equalizer=f=125:t=q:w=1:g=3,equalizer=f=4000:t=q:w=1:g=-2",
    EqualizerPreset.VOCAL: "equalizer=f=250:t=q:w=1:g=-2,equalizer=f=2500:t=q:w=1:g=4",
    EqualizerPreset.GAMING: "equalizer=f=120:t=q:w=1:g=3,equalizer=f=3500:t=q:w=1:g=3",
    EqualizerPreset.ACOUSTIC: "equalizer=f=250:t=q:w=1:g=2,equalizer=f=2200:t=q:w=1:g=3",
    EqualizerPreset.EDM: "equalizer=f=64:t=q:w=1:g=5,equalizer=f=1000:t=q:w=1:g=-2,equalizer=f=8000:t=q:w=1:g=4",
}

EQUALIZER_BANDS = {
    EqualizerPreset.BALANCED: (),
    EqualizerPreset.BASS: ((64.0, 6.0), (125.0, 4.0)),
    EqualizerPreset.CHILL: ((125.0, 3.0), (4000.0, -2.0)),
    EqualizerPreset.VOCAL: ((250.0, -2.0), (2500.0, 4.0)),
    EqualizerPreset.GAMING: ((120.0, 3.0), (3500.0, 3.0)),
    EqualizerPreset.ACOUSTIC: ((250.0, 2.0), (2200.0, 3.0)),
    EqualizerPreset.EDM: ((64.0, 5.0), (1000.0, -2.0), (8000.0, 4.0)),
}


@dataclass(frozen=True, slots=True)
class AudioProfile:
    effect: AudioEffect = AudioEffect.OFF
    equalizer: EqualizerPreset = EqualizerPreset.BALANCED

    @property
    def filter_chain(self) -> str:
        filters = [
            item
            for item in (EFFECT_FILTERS[self.effect], EQUALIZER_FILTERS[self.equalizer])
            if item
        ]
        if filters:
            filters.append("alimiter=limit=0.95")
        return ",".join(filters)

    @property
    def ffmpeg_filter_chain(self) -> str:
        effect_filter = EFFECT_FILTERS[self.effect]
        if not effect_filter:
            return ""
        return f"{effect_filter},alimiter=limit=0.95"

    @property
    def speed(self) -> float:
        return {
            AudioEffect.SLOW_REVERB: 0.9,
            AudioEffect.NIGHTCORE: 1.15,
            AudioEffect.VAPORWAVE: 0.85,
        }.get(self.effect, 1.0)

    @property
    def active(self) -> bool:
        return self.effect is not AudioEffect.OFF or self.equalizer is not EqualizerPreset.BALANCED
