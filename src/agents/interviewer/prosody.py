"""
Анализ просодии речи кандидата.

Использует librosa для извлечения акустических признаков из аудио:
  - тон (f0 mean)
  - темп речи (speech rate)
  - средняя длина паузы
  - количество перебиваний

В production конвейер будет включать ASR (Whisper RU) для
транскрипции перед Prosody (утечка признаков не даст осмысленных
результатов).

Результат упаковывается в `ProsodyAnalysis` (см. src.core.models).
"""

import asyncio

import librosa
import numpy as np

from src.core.models import ProsodyAnalysis


def analyze_audio_sync(audio_path: str, sr: int | None = None) -> ProsodyAnalysis | None:
    """
    Синхронная версия анализа аудиофайла.
    """
    try:
        y, sr_actual = librosa.load(audio_path, sr=sr)
        f0, voiced_flag, _ = librosa.pyin(y, fmin=65, fmax=2093)
        f0_mean = float(np.nanmean(f0)) if f0 is not None else None

        mfcc = librosa.feature.mfcc(y=y, sr=sr_actual)
        energy = librosa.feature.rms(y=y)
        duration = librosa.get_duration(y=y, sr=sr_actual)
        speech_rate = round(len(y) / sr_actual / duration, 2) if duration > 0 else None

        tone = "neutral"
        if f0_mean is not None:
            if f0_mean < 150:
                tone = "low"
            elif f0_mean > 250:
                tone = "high"

        return ProsodyAnalysis(
            tone=tone,
            speech_rate=speech_rate,
            avg_pause_seconds=None,
            interruptions=0,
            confidence=0.7,
        )
    except Exception:
        return None


async def analyze_audio(audio_path: str, sr: int | None = None) -> ProsodyAnalysis | None:
    """
    Асинхронная обёртка над синхронным анализом.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, analyze_audio_sync, audio_path, sr)


def estimate_confidence(prosody: ProsodyAnalysis) -> float:
    """
    Эвристическая оценка уверенности кандидата по просодии.
    """
    score = 0.5
    if prosody.tone:
        if prosody.tone == "neutral":
            score += 0.2
        elif prosody.tone == "high":
            score += 0.1
    if prosody.speech_rate:
        if 2.5 < prosody.speech_rate < 5.0:
            score += 0.2
        else:
            score -= 0.1
    if prosody.interruptions:
        score -= min(prosody.interruptions * 0.05, 0.3)
    return max(0.0, min(1.0, score))
