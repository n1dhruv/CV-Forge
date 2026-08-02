from datetime import datetime

from sqlalchemy import DateTime

from app.models.base import Base
from app.models.resume import JobDescription, ResumeVersion


def test_datetime_annotations_map_to_timezone_aware_columns() -> None:
    mapped_type = Base.registry.type_annotation_map[datetime]

    assert isinstance(mapped_type, DateTime)
    assert mapped_type.timezone is True


def test_resume_created_at_columns_are_timezone_aware() -> None:
    for model in (JobDescription, ResumeVersion):
        created_at_type = model.__table__.c.created_at.type

        assert isinstance(created_at_type, DateTime)
        assert created_at_type.timezone is True
