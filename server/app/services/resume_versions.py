from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import BackgroundJob
from app.models.resume import JobDescription, ResumeBulletSelection, ResumeVersion
from app.models.skill_bank import BulletPoint, SkillBankItem


class InvalidResumeVersionStateError(Exception):
    pass


class InvalidBulletSelectionError(Exception):
    pass


STABLE_SOURCE_STATUSES = {"assembled", "compiled", "compile_failed"}


def _root_id(version: ResumeVersion, by_id: dict[UUID, ResumeVersion]) -> UUID:
    seen: set[UUID] = set()
    while version.parent_version_id in by_id and version.id not in seen:
        seen.add(version.id)
        version = by_id[version.parent_version_id]
    return version.id


async def list_families(
    session: AsyncSession, user_id: UUID
) -> list[tuple[ResumeVersion, list[ResumeVersion]]]:
    versions = list(
        (
            await session.scalars(
                select(ResumeVersion)
                .where(ResumeVersion.user_id == user_id)
                .order_by(ResumeVersion.created_at.desc())
            )
        ).all()
    )
    by_id = {version.id: version for version in versions}
    grouped: dict[UUID, list[ResumeVersion]] = {}
    for version in versions:
        grouped.setdefault(_root_id(version, by_id), []).append(version)
    return [
        (by_id[root_id], sorted(rows, key=lambda row: row.created_at, reverse=True))
        for root_id, rows in grouped.items()
    ]


async def update_metadata(
    session: AsyncSession,
    user_id: UUID,
    version_id: UUID,
    name: str | None,
    version_label: str | None,
) -> ResumeVersion | None:
    versions = list(
        (await session.scalars(select(ResumeVersion).where(ResumeVersion.user_id == user_id))).all()
    )
    by_id = {version.id: version for version in versions}
    version = by_id.get(version_id)
    if version is None:
        return None
    if name is not None:
        root_id = _root_id(version, by_id)
        for row in versions:
            if _root_id(row, by_id) == root_id:
                row.name = name
    if version_label is not None:
        version.version_label = version_label
    await session.commit()
    await session.refresh(version)
    return version


async def create(session: AsyncSession, user_id: UUID, jd_id: UUID) -> ResumeVersion | None:
    jd = await session.scalar(
        select(JobDescription).where(
            JobDescription.id == jd_id,
            JobDescription.user_id == user_id,
            JobDescription.status == "done",
        )
    )
    if jd is None:
        return None
    version = ResumeVersion(user_id=user_id, jd_id=jd_id, status="draft")
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version


async def get_owned(
    session: AsyncSession, user_id: UUID, version_id: UUID, *, lock: bool = False
) -> ResumeVersion | None:
    query = select(ResumeVersion).where(
        ResumeVersion.id == version_id, ResumeVersion.user_id == user_id
    )
    return await session.scalar(query.with_for_update() if lock else query)


async def queue_rewrite(
    session: AsyncSession, user_id: UUID, version_id: UUID, bullet_ids: list[UUID]
) -> tuple[ResumeVersion, BackgroundJob] | None:
    version = await get_owned(session, user_id, version_id, lock=True)
    if version is None:
        return None
    if version.status != "draft":
        raise InvalidResumeVersionStateError

    owned_ids = set(
        (
            await session.scalars(
                select(BulletPoint.id)
                .join(SkillBankItem, SkillBankItem.id == BulletPoint.item_id)
                .where(BulletPoint.id.in_(bullet_ids), SkillBankItem.user_id == user_id)
            )
        ).all()
    )
    if owned_ids != set(bullet_ids):
        raise InvalidBulletSelectionError

    job = BackgroundJob(
        user_id=user_id,
        job_type="rewrite",
        status="queued",
        result={
            "resume_version_id": str(version_id),
            "bullet_point_ids": [str(i) for i in bullet_ids],
        },
    )
    version.status = "rewriting"
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return version, job


async def fail_enqueue(session: AsyncSession, version: ResumeVersion, job: BackgroundJob) -> None:
    version.status = "draft"
    job.status = "failed"
    job.error = "Unable to enqueue rewrite — try again"
    await session.commit()


async def queue_assembly(
    session: AsyncSession, user_id: UUID, version_id: UUID
) -> tuple[ResumeVersion, BackgroundJob, bool] | None:
    version = await get_owned(session, user_id, version_id, lock=True)
    if version is None:
        return None
    if version.status == "assembling":
        job = await session.scalar(
            select(BackgroundJob)
            .where(
                BackgroundJob.user_id == user_id,
                BackgroundJob.job_type == "resume_assemble",
                BackgroundJob.status.in_(("queued", "running")),
                BackgroundJob.result["resume_version_id"].astext == str(version_id),
            )
            .order_by(BackgroundJob.created_at.desc())
        )
        if job is not None:
            return version, job, False
    if version.status != "finalized":
        raise InvalidResumeVersionStateError
    job = BackgroundJob(
        user_id=user_id,
        job_type="resume_assemble",
        status="queued",
        result={"resume_version_id": str(version_id)},
    )
    version.status = "assembling"
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return version, job, True


async def queue_compile(
    session: AsyncSession, user_id: UUID, version_id: UUID
) -> tuple[ResumeVersion, BackgroundJob, bool] | None:
    version = await get_owned(session, user_id, version_id, lock=True)
    if version is None:
        return None
    if version.status == "compiling":
        job = await session.scalar(
            select(BackgroundJob)
            .where(
                BackgroundJob.user_id == user_id,
                BackgroundJob.job_type == "resume_compile",
                BackgroundJob.status.in_(("queued", "running")),
                BackgroundJob.result["resume_version_id"].astext == str(version_id),
            )
            .order_by(BackgroundJob.created_at.desc())
        )
        if job is not None:
            return version, job, False
    if version.status not in STABLE_SOURCE_STATUSES or not (version.tex_source or "").strip():
        raise InvalidResumeVersionStateError
    previous_status = version.status
    job = BackgroundJob(
        user_id=user_id,
        job_type="resume_compile",
        status="queued",
        result={"resume_version_id": str(version_id), "previous_status": previous_status},
    )
    version.status = "compiling"
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return version, job, True


async def fail_operation_enqueue(
    session: AsyncSession, version: ResumeVersion, job: BackgroundJob, stable_status: str
) -> None:
    version.status = stable_status
    job.status = "failed"
    job.error = "Unable to enqueue operation — try again"
    await session.commit()


async def update_tex(
    session: AsyncSession, user_id: UUID, version_id: UUID, tex_source: str
) -> ResumeVersion | None:
    version = await get_owned(session, user_id, version_id, lock=True)
    if version is None:
        return None
    if version.status not in STABLE_SOURCE_STATUSES:
        raise InvalidResumeVersionStateError
    version.tex_source = tex_source
    version.pdf_storage_path = None
    version.status = "assembled"
    await session.commit()
    await session.refresh(version)
    return version


async def create_snapshot(
    session: AsyncSession, user_id: UUID, version_id: UUID
) -> ResumeVersion | None:
    version = await get_owned(session, user_id, version_id, lock=True)
    if version is None:
        return None
    if version.status not in STABLE_SOURCE_STATUSES:
        raise InvalidResumeVersionStateError
    clone = ResumeVersion(
        user_id=user_id,
        jd_id=version.jd_id,
        tex_source=version.tex_source,
        pdf_storage_path=version.pdf_storage_path,
        ats_score=version.ats_score,
        parent_version_id=version.id,
        status=version.status,
        name=version.name,
        version_label=f"{version.version_label} Copy"[:80],
        selected_skills=version.selected_skills,
    )
    session.add(clone)
    await session.commit()
    await session.refresh(clone)
    return clone


async def history(
    session: AsyncSession, user_id: UUID, version_id: UUID
) -> list[ResumeVersion] | None:
    versions: list[ResumeVersion] = []
    seen: set[UUID] = set()
    current_id: UUID | None = version_id
    while current_id is not None and current_id not in seen:
        seen.add(current_id)
        version = await session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == current_id, ResumeVersion.user_id == user_id
            )
        )
        if version is None:
            return None if not versions else list(reversed(versions))
        versions.append(version)
        current_id = version.parent_version_id
    return list(reversed(versions))


async def list_bullets(
    session: AsyncSession, user_id: UUID, version_id: UUID
) -> list[ResumeBulletSelection] | None:
    if await get_owned(session, user_id, version_id) is None:
        return None
    return list(
        (
            await session.scalars(
                select(ResumeBulletSelection)
                .where(ResumeBulletSelection.resume_version_id == version_id)
                .order_by(ResumeBulletSelection.section_order, ResumeBulletSelection.id)
            )
        ).all()
    )


async def get_selection_owned(
    session: AsyncSession, user_id: UUID, selection_id: UUID
) -> tuple[ResumeBulletSelection, ResumeVersion] | None:
    row = (
        await session.execute(
            select(ResumeBulletSelection, ResumeVersion)
            .join(ResumeVersion, ResumeVersion.id == ResumeBulletSelection.resume_version_id)
            .where(ResumeBulletSelection.id == selection_id, ResumeVersion.user_id == user_id)
            .with_for_update()
        )
    ).one_or_none()
    return row if row else None


async def finalize(
    session: AsyncSession, user_id: UUID, version_id: UUID
) -> tuple[ResumeVersion, list[UUID]] | None:
    version = await get_owned(session, user_id, version_id, lock=True)
    if version is None:
        return None
    if version.status != "reviewing":
        raise InvalidResumeVersionStateError
    selections = list(
        (
            await session.scalars(
                select(ResumeBulletSelection).where(
                    ResumeBulletSelection.resume_version_id == version_id
                )
            )
        ).all()
    )
    unresolved = [selection.id for selection in selections if not selection.resolved]
    if not selections or unresolved:
        return version, unresolved
    version.status = "finalized"
    await session.commit()
    return version, []
