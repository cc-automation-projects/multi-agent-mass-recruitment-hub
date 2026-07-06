"""
Propensity Dialer ML-модель (CatBoost) с загрузкой из MLflow и извлечением признаков.
"""

from datetime import datetime
from typing import Any

import numpy as np
from mlflow.tracking import MlflowClient

from src.core.audit_logger import audit_log
from src.core.config import get_settings
from src.core.metrics import propensity_prediction_duration, propensity_score
from src.core.models import Candidate

_settings = get_settings()
_logger = audit_log()

MODEL_PATH = "models/propensity_dialer/model.cbm"

_model: Any | None = None


def _get_model() -> Any | None:
    global _model
    if _model is not None:
        return _model

    if _settings.mlflow_enabled:
        try:
            import mlflow

            mlflow.set_tracking_uri(_settings.mlflow_tracking_uri)
            client = MlflowClient()
            versions = client.search_model_versions(f"name='{_settings.mlflow_model_name}'")
            prod_version = None
            for v in versions:
                if v.current_stage == _settings.mlflow_model_stage:
                    prod_version = v
                    break
            if prod_version:
                model_uri = f"models:/{_settings.mlflow_model_name}/{_settings.mlflow_model_stage}"
                _model = mlflow.catboost.load_model(model_uri)
                _logger.info(
                    "mlflow_model_loaded",
                    model_name=_settings.mlflow_model_name,
                    stage=_settings.mlflow_model_stage,
                )
                return _model
            else:
                _logger.warning("No production model in MLflow, falling back to local")
        except Exception as e:
            _logger.error("MLflow load failed", error=str(e))

    try:
        import catboost as cb

        _model = cb.CatBoostClassifier()
        _model.load_model(MODEL_PATH)
        _logger.info("local_model_loaded", path=MODEL_PATH)
        return _model
    except Exception as e:
        _logger.error("local_model_load_failed", error=str(e))
        return None


def extract_features(candidate: Candidate, call_time: datetime) -> np.ndarray:
    hour = call_time.hour / 24.0
    day_of_week = call_time.weekday() / 7.0

    prev_attempts = 0.0

    if candidate.source in ("hh", "avito", "jobru"):
        segment = 0.8
    elif candidate.resume_text and len(candidate.resume_text) > 200:
        segment = 0.7
    else:
        segment = 0.5

    skill_match = 0.6
    experience_years = 2.0

    features = np.array(
        [hour, day_of_week, prev_attempts, segment, skill_match, experience_years]
    ).reshape(1, -1)
    return features


async def predict_propensity(candidate: Candidate, call_time: datetime) -> float:
    model = _get_model()
    if model is None:
        _logger.warning("propensity_model_unavailable, returning default 0.5")
        return 0.5

    features = extract_features(candidate, call_time)
    with propensity_prediction_duration.time():
        proba = model.predict_proba(features)[0, 1]

    propensity_score.labels(model_version="propensity_dialer").set(proba)

    _logger.info(
        "propensity_predicted",
        candidate_id=candidate.id,
        score=round(proba, 4),
        hour=call_time.hour,
        day=call_time.weekday(),
    )
    return float(proba)


async def reload_model():
    global _model
    _model = None
    _logger.info("model_cache_cleared_for_reload")
