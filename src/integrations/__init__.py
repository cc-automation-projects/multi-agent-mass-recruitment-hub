"""Integrations with external job boards (hh.ru, Avito, etc.)."""

from src.integrations.job_boards import fetch_resumes_from_avito, fetch_resumes_from_hh

__all__ = ["fetch_resumes_from_hh", "fetch_resumes_from_avito"]
