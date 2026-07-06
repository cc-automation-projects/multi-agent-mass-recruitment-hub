"""
Конфигурация приложения MassRecruitHub.

Загружает переменные окружения через pydantic-settings.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        frozen=True,
    )

    # --- Vector Storage ---
    qdrant_url: HttpUrl = Field(default="http://localhost:6333")
    qdrant_api_key: str | None = Field(default=None)

    # --- Session Cache ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Primary Database ---
    database_url: str = Field(
        default="postgresql+psycopg2://user:password@localhost:5432/massrecruithub"
    )
    database_pool_size: int = Field(default=20, ge=1)
    database_max_overflow: int = Field(default=40, ge=0)

    # --- LLM Inference ---
    llm_endpoint: HttpUrl = Field(default="https://llm.api.yandex.cloud/v1")
    llm_model: str = Field(default="yandexgpt/latest")
    llm_api_key: str | None = Field(default=None)

    # --- vLLM ---
    vllm_base_url: str = Field(default="http://localhost:8000/v1")
    vllm_model: str = Field(default="Qwen/Qwen2.5-7B-Instruct")
    vllm_tensor_parallel_size: int = Field(default=1)
    vllm_gpu_memory_utilization: float = Field(default=0.8)

    # --- ASR (faster-whisper) ---
    whisper_model_path: str = Field(default="models/whisper-large-v3-ru-phone")
    whisper_device: Literal["cpu", "cuda"] = Field(default="cpu")
    whisper_compute_type: Literal["int8", "float16", "float32"] = Field(default="int8")

    # --- TTS ---
    silero_tts_model_path: str = Field(default="models/silero_v5")
    silero_speaker: str = Field(
        default="ru_v5", description="Speaker for Silero TTS: ru_v5, ru_v4, etc."
    )

    # --- Telephony ---
    freeswitch_host: str = Field(default="localhost")
    freeswitch_port: int = Field(default=8021, ge=1, le=65535)  # ESL default port
    freeswitch_password: str = Field(default="ClueCon")
    freeswitch_gateway: str = Field(default="sofia/gateway/provider/")

    livekit_host: str = Field(default="localhost")
    livekit_port: int = Field(default=7880, ge=1, le=65535)
    livekit_api_key: str = Field(default="dev_key")
    livekit_api_secret: str = Field(default="dev_secret")

    # --- Messengers ---
    max_api_key: str | None = Field(default=None)
    max_api_endpoint: str | None = Field(default="https://api.max.ru/v1/messages")
    telegram_bot_token: str | None = Field(default=None)
    telegram_webhook_url: str | None = Field(
        default=None, description="Webhook URL for Telegram bot (if using webhook)"
    )
    vk_api_token: str | None = Field(default=None)

    # --- Job Boards API ---
    hh_api_token: str | None = Field(
        default=None, description="API token for hh.ru vacancies search"
    )
    hh_access_token: str | None = Field(
        default=None, description="OAuth token for hh.ru resumes endpoint"
    )
    avito_api_token: str | None = Field(default=None)

    # --- Email (SMTP) ---
    smtp_host: str | None = Field(default=None)
    smtp_port: int | None = Field(default=None)
    smtp_user: str | None = Field(default=None)
    smtp_password: str | None = Field(default=None)

    # --- Memory ---
    mem0_api_key: str | None = Field(default=None)

    # --- MLflow ---
    mlflow_tracking_uri: str = Field(default="http://localhost:5000")
    mlflow_experiment_name: str = Field(default="mass-recruit-hub")
    mlflow_enabled: bool = Field(default=False, description="Enable MLflow model registry loading")
    mlflow_model_name: str = Field(
        default="propensity_dialer",
        description="Model name in MLflow Model Registry",
    )
    mlflow_model_stage: str = Field(
        default="Production",
        description="Model stage in MLflow Model Registry",
    )

    # --- Semantic Cache ---
    semantic_cache_ttl: int = Field(default=3600, ge=0)
    semantic_cache_similarity_threshold: float = Field(default=0.95, ge=0.0, le=1.0)

    # --- Compliance & Audit ---
    consent_required: bool = Field(default=True)
    audit_log_retention_days: int = Field(default=1095)
    audit_json_logging: bool = Field(default=True)
    audit_log_path: str | None = Field(default=None)

    # --- Deletion ---
    soft_delete_audit: bool = Field(
        default=True,
        description="Mark audit logs as deleted instead of physical removal",
    )

    # --- Google Calendar ---
    google_calendar_credentials_path: str | None = Field(default=None)
    google_calendar_token_path: str | None = Field(default=None)
    google_calendar_scopes: str = Field(default="https://www.googleapis.com/auth/calendar.readonly")
    google_calendar_default_id: str = Field(default="primary")

    # --- Yandex Calendar ---
    yandex_calendar_access_token: str | None = Field(default=None)
    yandex_calendar_default_id: str | None = Field(default=None)

    # --- General Calendar ---
    calendar_provider: Literal["google", "yandex"] = Field(default="google")

    # --- RPA (1С onboarding) ---
    rpa_webhook_url: str | None = Field(default=None)
    rpa_callback_url: str | None = Field(default=None)

    # --- Presidio ---
    presidio_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    presidio_supported_entities: str = Field(default="PERSON,PHONE,EMAIL,PASSPORT,SNILS,ADDRESS")
    presidio_language: str = Field(default="ru")

    # --- Fairness Audit ---
    fairness_disparate_impact_threshold: float = Field(
        default=0.8, description="Minimum acceptable disparate impact (0.8 = 80%)"
    )
    fairness_false_rejection_rate_threshold: float = Field(
        default=0.02, description="Maximum acceptable false rejection rate (2%)"
    )
    fairness_months_back: int = Field(
        default=1, description="Number of months of historical data to consider for fairness audit"
    )

    # --- JWT Authentication ---
    jwt_secret_key: str = Field(default="your-secret-key-change-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30, ge=1)

    # --- Runtime ---
    environment: Literal["development", "staging", "production"] = Field(default="development")


@lru_cache
def get_settings() -> Settings:
    return Settings()
