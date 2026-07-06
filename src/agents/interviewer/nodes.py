"""Узлы графа Agent-Interviewer с обработкой ошибок и метриками, с интеграцией голосового пайплайна."""

import os
from typing import Any

from src.agents.interviewer.prosody import analyze_audio, estimate_confidence
from src.agents.interviewer.video_analyzer import analyze_video
from src.core.audit_logger import audit_log
from src.core.metrics import (
    human_review_required,
    interviewer_audio_duration_seconds,
    interviewer_sessions,
    pipeline_duration_seconds,
)
from src.core.models import InterviewResult
from src.core.state import AgentState
from src.voice.pipeline import VoicePipeline

_logger = audit_log()
_voice_pipeline = None  # будет инициализирован при первом вызове


def _get_voice_pipeline():
    global _voice_pipeline
    if _voice_pipeline is None:
        _voice_pipeline = VoicePipeline()
    return _voice_pipeline


async def prepare_questions(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        _logger.info(
            "questions_prepared",
            candidate_id=candidate.id,
            action="interview_started",
        )
        return state
    except Exception as e:
        _logger.error("prepare_questions_failed", error=str(e))
        return {"error": f"prepare_questions: {str(e)}", "requires_human_review": True}


async def conduct_interview(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        iteration_count = state["iteration_count"] + 1
        interviewer_sessions.labels(outcome="conducted").inc()
        with pipeline_duration_seconds.labels(agent_stage="interviewer_conduct").time():
            # Здесь вместо создания dummy‑аудио мы бы реально запускали голосовой диалог.
            # Для заглушки: эмулируем получение аудио от кандидата.
            session_id = f"iv_{candidate.id}_{iteration_count}"
            # Имитация входящего аудио (в production – из LiveKit)
            dummy_audio = b"dummy_audio_from_candidate"
            pipeline = _get_voice_pipeline()
            response_audio = await pipeline.process_audio(session_id, dummy_audio)
            _logger.info(
                "voice_pipeline_processed",
                candidate_id=candidate.id,
                session_id=session_id,
                audio_length=len(response_audio) if response_audio else 0,
            )

        _logger.info(
            "interview_conducted",
            candidate_id=candidate.id,
            iteration=iteration_count,
        )
        # Сохраняем dummy‑аудио для просодии (в реальности аудио будет из пайплайна)
        audio_path = f"audio/{candidate.id}.wav"
        os.makedirs("audio", exist_ok=True)
        with open(audio_path, "wb") as f:
            f.write(b"dummy audio data for prosody")

        return {
            "iteration_count": iteration_count,
            "_audio_path": audio_path,
        }
    except Exception as e:
        _logger.error("conduct_interview_failed", error=str(e))
        return {"error": f"conduct_interview: {str(e)}", "requires_human_review": True}


async def analyze_prosody_node(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        audio_path = state.get("_audio_path")
        if not audio_path or not os.path.exists(audio_path):
            _logger.warning("audio_missing_for_prosody", candidate_id=candidate.id)
            return {"_prosody": None}

        with interviewer_audio_duration_seconds.time():
            prosody = await analyze_audio(audio_path)
        if prosody:
            prosody.confidence = estimate_confidence(prosody)
            _logger.info(
                "prosody_analyzed",
                candidate_id=candidate.id,
                tone=prosody.tone,
                speech_rate=prosody.speech_rate,
                confidence=prosody.confidence,
            )
        else:
            _logger.warning("prosody_analysis_failed", candidate_id=candidate.id)

        return {"_prosody": prosody}
    except Exception as e:
        _logger.error("analyze_prosody_failed", error=str(e))
        return {"error": f"analyze_prosody: {str(e)}", "requires_human_review": True}


async def analyze_results(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        prosody = state.get("_prosody")

        overall_score = 0.7 if prosody else 0.5
        recommendation = "pass" if overall_score > 0.6 else "review"

        interview_result = InterviewResult(
            candidate_id=candidate.id,
            overall_score=overall_score,
            motivation_score=0.7,
            communication_score=0.7,
            consistency_score=0.7,
            prosody=prosody,
            recommendation=recommendation,
        )

        _logger.info(
            "results_analyzed",
            candidate_id=candidate.id,
            overall_score=overall_score,
            recommendation=recommendation,
        )

        return {
            "interview_result": interview_result,
            "current_step": "analyze_results",
        }
    except Exception as e:
        _logger.error("analyze_results_failed", error=str(e))
        return {"error": f"analyze_results: {str(e)}", "requires_human_review": True}


async def analyze_video_node(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        video_path = state.get("_video_path")
        if not video_path:
            _logger.info("no_video_for_analysis", candidate_id=candidate.id)
            return {}

        video_result = await analyze_video(video_path)
        if video_result:
            _logger.info(
                "video_analyzed",
                candidate_id=candidate.id,
                emotion=video_result.emotion,
                attention=video_result.attention_score,
                leadership=video_result.leadership_potential,
            )
            state["_video_analysis"] = {
                "emotion": video_result.emotion,
                "attention_score": video_result.attention_score,
                "leadership_potential": video_result.leadership_potential,
            }
        return {}
    except Exception as e:
        _logger.error("video_analysis_failed", error=str(e))
        return {"error": f"video_analysis: {str(e)}", "requires_human_review": True}


async def human_review_interview(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        human_review_required.labels(stage="interviewer").inc()
        _logger.info(
            "interview_human_review",
            candidate_id=candidate.id,
            decision="pending",
        )
        return {
            "current_step": "human_review_interview",
            "requires_human_review": True,
        }
    except Exception as e:
        _logger.error("human_review_interview_failed", error=str(e))
        return {"error": f"human_review_interview: {str(e)}", "requires_human_review": True}
