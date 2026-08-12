import asyncio
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.jobs import BackgroundJob
from app.models.resume import ResumeVersion
from app.services.latex_compiler import CompilationError, CompileDiagnostic, compile_latex
from app.services.storage import StorageService


async def compile_resume_task(
    context: dict[str, Any], resume_version_id: str, background_job_id: str, user_id: str
) -> None:
    del context
    version_id, job_id, owner_id = map(UUID, (resume_version_id, background_job_id, user_id))
    settings = get_settings()
    async with async_session_factory() as session:
        version = await session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == version_id,
                ResumeVersion.user_id == owner_id,
                ResumeVersion.status == "compiling",
            )
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id,
                BackgroundJob.user_id == owner_id,
                BackgroundJob.status == "queued",
            )
        )
        if version is None or job is None or not version.tex_source:
            return
        job.status = "running"
        await session.commit()
        try:
            pdf = await asyncio.to_thread(
                compile_latex,
                version.tex_source,
                settings.tectonic_binary_path,
                settings.latex_compile_timeout_seconds,
            )
            path = f"{owner_id}/{version_id}/resume.pdf"
            await StorageService(settings).upload(path, pdf, "application/pdf")
            version.pdf_storage_path = path
            version.status = "compiled"
            job.status = "done"
            job.error = None
            job.result = {"resume_version_id": str(version_id), "status": "compiled"}
        except CompilationError as exc:
            _record_failure(version, job, exc.diagnostic)
        except httpx.HTTPError:
            _record_failure(
                version,
                job,
                CompileDiagnostic("internal", "The compiled PDF could not be stored"),
            )
        except Exception:
            _record_failure(
                version,
                job,
                CompileDiagnostic("internal", "The resume could not be compiled"),
            )
        await session.commit()


def _record_failure(
    version: ResumeVersion, job: BackgroundJob, diagnostic: CompileDiagnostic
) -> None:
    version.pdf_storage_path = None
    version.status = "compile_failed"
    job.status = "failed"
    job.error = "Resume compilation failed"
    job.result = {
        "resume_version_id": str(version.id),
        "status": "compile_failed",
        "errors": [
            {"kind": diagnostic.kind, "message": diagnostic.message, "line": diagnostic.line}
        ],
    }
