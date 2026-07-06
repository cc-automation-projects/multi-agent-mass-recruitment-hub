"""
Реальный клиент LiveKit для голосового пайплайна.
"""

from livekit import api, rtc

from src.core.audit_logger import audit_log
from src.core.config import get_settings

_settings = get_settings()
_logger = audit_log()


class LiveKitVoiceClient:
    """
    Клиент для интеграции с LiveKit.
    Управляет подключением и обработкой аудио.
    """

    def __init__(self, host: str = None, api_key: str = None, api_secret: str = None):
        self.host = host or _settings.livekit_host
        self.port = _settings.livekit_port
        self.api_key = api_key or _settings.livekit_api_key
        self.api_secret = api_secret or _settings.livekit_api_secret
        self._room = None
        self._audio_source = None

    async def connect(self, room_name: str, participant_identity: str) -> bool:
        """Подключается к LiveKit комнате и создаёт аудиотрек."""
        try:
            room_service = api.RoomService(api_key=self.api_key, api_secret=self.api_secret)
            try:
                await room_service.get_room(room_name)
            except api.ApiError:
                await room_service.create_room(room_name)

            self._room = rtc.Room()
            token = (
                api.AccessToken(self.api_key, self.api_secret)
                .with_identity(participant_identity)
                .with_room(room_name)
                .with_grants(api.VideoGrants(room_join=True))
                .to_jwt()
            )
            await self._room.connect(f"ws://{self.host}:{self.port}", token)
            self._audio_source = rtc.AudioSource(16000, 1)
            track = rtc.LocalAudioTrack.create_audio_track("voice", self._audio_source)
            options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            await self._room.local_participant.publish_track(track, options)
            _logger.info("LiveKit connected", room=room_name, participant=participant_identity)
            return True
        except Exception as e:
            _logger.error("LiveKit connection failed", error=str(e))
            return False

    async def send_audio(self, audio_bytes: bytes) -> bool:
        """Отправляет аудио (в формате PCM 16kHz mono) в комнату."""
        if not self._audio_source:
            return False
        frame = rtc.AudioFrame(
            data=audio_bytes,
            sample_rate=16000,
            num_channels=1,
            samples_per_channel=len(audio_bytes) // 2 // 1,
        )
        await self._audio_source.capture_frame(frame)
        return True

    async def receive_audio(self) -> bytes | None:
        """Получает аудио из комнаты (заглушка – в реальности через обработчик событий)."""
        return None

    async def disconnect(self):
        if self._room:
            await self._room.disconnect()
            _logger.info("LiveKit disconnected")
