"""
ASR (Automatic Speech Recognition) на базе faster-whisper.
Поддерживает загрузку fine‑tuned моделей.
"""

import asyncio

from faster_whisper import WhisperModel

from src.core.audit_logger import audit_log
from src.core.config import get_settings

_logger = audit_log()
_settings = get_settings()


class FasterWhisperASR:
    """
    Адаптер для faster-whisper (on‑premise).
    Модель загружается один раз при первом вызове.
    """

    def __init__(
        self, model_path: str | None = None, device: str = "cpu", compute_type: str = "int8"
    ):
        self.model_path = model_path or _settings.whisper_model_path
        self.device = device
        self.compute_type = compute_type
        self._model = None

    async def _get_model(self) -> WhisperModel:
        if self._model is None:
            loop = asyncio.get_running_loop()
            self._model = await loop.run_in_executor(
                None,
                lambda: WhisperModel(
                    self.model_path,
                    device=self.device,
                    compute_type=self.compute_type,
                ),
            )
            _logger.info("Whisper model loaded", path=self.model_path, device=self.device)
        return self._model

    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Распознаёт аудио (PCM 16kHz mono) и возвращает текст.
        """

        import numpy as np

        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        model = await self._get_model()
        loop = asyncio.get_running_loop()
        segments, info = await loop.run_in_executor(
            None,
            lambda: model.transcribe(audio_float32, language="ru", beam_size=5, vad_filter=True),
        )
        text = " ".join([seg.text for seg in segments])
        _logger.info("ASR transcription completed", text=text, language=info.language)
        return text.strip()
