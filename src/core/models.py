"""
Модели данных для MassRecruitHub.
... (остальной комментарий)
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ScreeningStatus(str, Enum):  # noqa: UP042
    PENDING = "pending"
    SCREENING = "screening"
    PASSED = "passed"
    REJECTED = "rejected"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class BiometryConsentLog(BaseModel):
    id: int
    candidate_id: str
    consent_given: bool = True
    audio_hash: str
    timestamp: datetime
    ip_address: str | None = None
    user_agent: str | None = None


class Candidate(BaseModel):
    id: str = Field(description="Уникальный идентификатор кандидата")
    name: str = Field(description="ФИО кандидата (подлежит маскированию)")
    phone: str = Field(description="Номер телефона (маскируется)")
    consent_152fz: bool = Field(
        default=False, description="Согласие на обработку ПДн согласно 152-ФЗ"
    )
    consent_biometry: bool = Field(
        default=False, description="Отдельное согласие на обработку голосовой биометрии"
    )
    resume_text: str | None = Field(
        default=None, description="Текст резюме (маскируется перед RAG)"
    )
    screening_status: ScreeningStatus = Field(default=ScreeningStatus.PENDING)
    notes: str | None = Field(default=None)
    source: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def validate_consent(self) -> "Candidate":
        if self.screening_status != ScreeningStatus.PENDING and not self.consent_152fz:
            raise ValueError("consent_152fz must be True before any screening can proceed")
        return self

    async def mask_pii(self) -> "Candidate":
        """
        Возвращает копию кандидата с замаскированными ПДн через Presidio.
        """
        from src.services.hr_integrations import anonymize_pdn

        masked = self.model_copy(deep=True)
        if self.name:
            masked_name = await anonymize_pdn(self.name)
            masked.name = masked_name if masked_name != self.name else "[PERSON]"
        if self.phone:
            masked_phone = await anonymize_pdn(self.phone)
            masked.phone = masked_phone if masked_phone != self.phone else "+7 XXX XXX XX XX"
        if self.resume_text:
            masked.resume_text = await anonymize_pdn(self.resume_text)
        return masked


class ProsodyAnalysis(BaseModel):
    tone: str | None = Field(default=None)
    speech_rate: float | None = Field(default=None)
    avg_pause_seconds: float | None = Field(default=None)
    interruptions: int = Field(default=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class CampaignStatus(str, Enum):  # noqa: UP042
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class Campaign(BaseModel):
    id: str = Field(description="Уникальный идентификатор кампании")
    name: str = Field(description="Название кампании")
    description: str | None = Field(default=None)
    candidate_ids: list[str] = Field(default_factory=list)
    status: CampaignStatus = Field(default=CampaignStatus.DRAFT)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class VideoAnalysis(BaseModel):
    emotion: str = Field(default="neutral")
    attention_score: float = Field(default=0.0, ge=0.0, le=1.0)
    leadership_potential: float = Field(default=0.0, ge=0.0, le=1.0)


class UserRole(str, Enum):  # noqa: UP042
    ADMIN = "admin"
    HR = "hr"
    SUPERVISOR = "supervisor"


class User(BaseModel):
    id: str = Field(description="Уникальный идентификатор пользователя")
    username: str = Field(description="Логин")
    email: str = Field(description="Email")
    hashed_password: str = Field(description="Хэш пароля (bcrypt)")
    role: UserRole = Field(default=UserRole.HR)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class InterviewResult(BaseModel):
    candidate_id: str
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    motivation_score: float | None = Field(default=None)
    communication_score: float | None = Field(default=None)
    consistency_score: float | None = Field(default=None)
    prosody: ProsodyAnalysis | None = Field(default=None)
    recommendation: str | None = Field(default=None)
    interview_date: datetime = Field(default_factory=datetime.utcnow)
    transcript: str | None = Field(default=None)
