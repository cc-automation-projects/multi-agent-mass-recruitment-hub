"""
Реальный синтез речи через Silero TTS v5.
"""

import asyncio

import torch

from src.core.audit_logger import audit_log
from src.core.config import get_settings

_logger = audit_log()
_settings = get_settings()


class SileroTTS:
    """Адаптер для Silero TTS v5 (русский язык)."""

    def __init__(self, device: str = "cpu", language: str = "ru", speaker: str = "aidar"):
        self.device = device
        self.language = language
        self.speaker = speaker
        self._model = None
        self._sample_rate = 48000

    async def _load_model(self):
        if self._model is not None:
            return
        loop = asyncio.get_running_loop()
        self._model = await loop.run_in_executor(
            None,
            self._load_model_sync,
        )
        _logger.info("Silero TTS model loaded", device=self.device, speaker=self.speaker)

    def _load_model_sync(self):
        import torch

        device = torch.device(self.device)
        model, example_text, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language=self.language,
            speaker=self.speaker,
        )
        model.to(device)
        return model

    async def synthesize(self, text: str, sample_rate: int = 24000) -> bytes:
        """
        Синтезирует речь из текста и возвращает PCM аудио (16kHz, mono).
        """
        await self._load_model()
        loop = asyncio.get_running_loop()
        audio_numpy = await loop.run_in_executor(
            None,
            self._synthesize_sync,
            text,
        )
        audio_int16 = (audio_numpy * 32767).astype("int16")
        audio_bytes = audio_int16.tobytes()
        _logger.info("TTS synthesis completed", text_preview=text[:50], length=len(audio_bytes))
        return audio_bytes

    def _synthesize_sync(self, text: str):
        with torch.no_grad():
            audio = self._model.apply_tts(
                text=text,
                speaker=self.speaker,
                sample_rate=self._sample_rate,
            )
        if audio.ndim > 1:
            audio = audio.mean(axis=0)
        if self._sample_rate != 16000:
            import torchaudio.functional as functional

            audio = functional.resample(torch.from_numpy(audio), self._sample_rate, 16000).numpy()
        return audio
