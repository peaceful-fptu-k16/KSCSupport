class MusicError(Exception):
    """An expected failure that can be shown directly to a Discord user."""

    def __init__(self, message: str, *, code: str = "music_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class MusicUnavailableError(MusicError):
    def __init__(self, message: str = "Nguồn nhạc này hiện không khả dụng.") -> None:
        super().__init__(message, code="music_unavailable")


class VoiceStateError(MusicError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="voice_state")
