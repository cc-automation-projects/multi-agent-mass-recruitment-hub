"""
Service for importing resumes from external job boards and creating candidates.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit_logger import audit_log
from src.core.models import Candidate, ScreeningStatus
from src.integrations import fetch_resumes_from_avito, fetch_resumes_from_hh

_logger = audit_log()


class ResumeImportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def import_from_hh(self, query: str, per_page: int = 10) -> int:
        resumes = await fetch_resumes_from_hh(query, per_page)
        count = 0
        for resume in resumes:
            candidate = Candidate(
                id=f"hh_{resume['phone']}",
                name=resume["name"],
                phone=resume["phone"],
                consent_152fz=resume.get("consent_152fz", True),
                resume_text=resume.get("resume_text"),
                source="hh",
                screening_status=ScreeningStatus.PENDING,
            )
            self.session.add(candidate)
            count += 1
        await self.session.commit()
        _logger.info("imported_from_hh", count=count, query=query)
        return count

    async def import_from_avito(self, query: str, limit: int = 10) -> int:
        resumes = await fetch_resumes_from_avito(query, limit)
        count = 0
        for resume in resumes:
            candidate = Candidate(
                id=f"avito_{resume['phone']}",
                name=resume["name"],
                phone=resume["phone"],
                consent_152fz=resume.get("consent_152fz", True),
                resume_text=resume.get("resume_text"),
                source="avito",
                screening_status=ScreeningStatus.PENDING,
            )
            self.session.add(candidate)
            count += 1
        await self.session.commit()
        _logger.info("imported_from_avito", count=count, query=query)
        return count
