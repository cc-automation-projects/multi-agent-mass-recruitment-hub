"""
Реальный анализ видео: детекция лиц, распознавание эмоций, оценка внимания и лидерского потенциала.
Использует OpenCV и DeepFace.
"""

import asyncio
import os

from src.agents.interviewer.face_utils import (
    analyze_emotions_async,
    estimate_attention,
    estimate_leadership_potential,
    extract_frames,
)
from src.core.audit_logger import audit_log

_logger = audit_log()


class VideoAnalysisResult:
    def __init__(self, emotion: str, attention_score: float, leadership_potential: float):
        self.emotion = emotion
        self.attention_score = attention_score
        self.leadership_potential = leadership_potential


async def analyze_video(video_path: str, sample_rate: int = 5) -> VideoAnalysisResult | None:
    """
    Анализирует видеофайл и возвращает результат анализа.
    sample_rate – частота извлечения кадров (каждый N-й кадр).
    """
    if not os.path.exists(video_path):
        _logger.warning("video_file_not_found", path=video_path)
        return None

    _logger.info("video_analysis_start", path=video_path)

    frames = await asyncio.get_running_loop().run_in_executor(
        None, extract_frames, video_path, sample_rate
    )
    if not frames:
        _logger.warning("no_frames_extracted", path=video_path)
        return None

    emotion_results = await analyze_emotions_async(frames)

    attention = estimate_attention(emotion_results)
    leadership = estimate_leadership_potential(emotion_results)

    emotion_counts = {}
    for r in emotion_results:
        emotion = r["emotion"]
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    dominant_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"

    _logger.info(
        "video_analysis_completed",
        path=video_path,
        dominant_emotion=dominant_emotion,
        attention=attention,
        leadership=leadership,
    )

    return VideoAnalysisResult(
        emotion=dominant_emotion,
        attention_score=attention,
        leadership_potential=leadership,
    )
