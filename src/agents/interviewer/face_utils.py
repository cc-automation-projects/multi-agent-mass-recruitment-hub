"""
Вспомогательные функции для анализа видео: извлечение кадров, детекция лиц, работа с DeepFace.
"""

import asyncio

import cv2
import numpy as np
from deepface import DeepFace


def extract_frames(video_path: str, sample_rate: int = 5) -> list[np.ndarray]:
    """
    Извлекает кадры из видео с заданной частотой (каждый sample_rate-й кадр).
    Возвращает список кадров (RGB).
    """
    cap = cv2.VideoCapture(video_path)
    frames = []
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % sample_rate == 0:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame_rgb)
        frame_count += 1
    cap.release()
    return frames


async def analyze_emotions_async(frames: list[np.ndarray]) -> list[dict]:
    """
    Асинхронно анализирует эмоции на кадрах с использованием DeepFace.
    Запускает анализ в отдельном потоке (т.к. DeepFace синхронный и тяжёлый).
    """
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, _analyze_emotions_sync, frames)
    return results


def _analyze_emotions_sync(frames: list[np.ndarray]) -> list[dict]:
    """
    Синхронный анализ эмоций.
    """
    results = []
    for frame in frames:
        try:
            analysis = DeepFace.analyze(
                img_path=frame, actions=["emotion"], enforce_detection=False
            )
            if isinstance(analysis, list):
                analysis = analysis[0]
            results.append(
                {
                    "emotion": analysis["dominant_emotion"],
                    "confidence": analysis["emotion"][analysis["dominant_emotion"]] / 100.0,
                }
            )
        except Exception:
            results.append({"emotion": "unknown", "confidence": 0.0})
    return results


def estimate_attention(emotions: list[dict]) -> float:
    """
    Оценивает внимание по частоте обнаружения лица и уверенности.
    Возвращает оценку от 0 до 1.
    """
    if not emotions:
        return 0.0
    detected = sum(1 for e in emotions if e["emotion"] != "unknown")
    avg_confidence = sum(e["confidence"] for e in emotions if e["emotion"] != "unknown") / max(
        detected, 1
    )
    return (detected / len(emotions)) * avg_confidence


def estimate_leadership_potential(emotions: list[dict]) -> float:
    """
    Эвристическая оценка лидерского потенциала на основе доминирующих эмоций.
    Лидерские качества ассоциируются с уверенностью, спокойствием, редкими негативными эмоциями.
    """
    if not emotions:
        return 0.5
    emotion_weights = {
        "neutral": 0.8,
        "happy": 0.9,
        "sad": 0.3,
        "angry": 0.4,
        "fear": 0.2,
        "surprise": 0.6,
        "disgust": 0.2,
        "unknown": 0.4,
    }
    scores = []
    for e in emotions:
        weight = emotion_weights.get(e["emotion"], 0.5)
        scores.append(weight * e["confidence"])
    return sum(scores) / len(scores)
