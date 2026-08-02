from datetime import datetime

from sqlalchemy import DateTime

import app.models  # noqa: F401 -- register every model with Base.metadata
from app.models.base import Base


def test_datetime_annotations_map_to_timezone_aware_columns() -> None:
    mapped_type = Base.registry.type_annotation_map[datetime]

    assert isinstance(mapped_type, DateTime)
    assert mapped_type.timezone is True


def test_all_datetime_columns_are_timezone_aware() -> None:
    datetime_columns = {
        (table.name, column.name): column.type
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, DateTime)
    }
    expected_integration_columns = {
        ("github_repos", "created_at"),
        ("github_repos", "last_synced_at"),
        ("leetcode_stats", "last_synced_at"),
    }

    assert expected_integration_columns <= datetime_columns.keys()
    assert [
        name for name, column_type in datetime_columns.items() if not column_type.timezone
    ] == []
