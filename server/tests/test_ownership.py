from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.models.user import User
from app.services.skill_bank import get_bullet, get_item


async def test_item_lookup_always_filters_current_user():
    session = AsyncMock()
    session.scalar.return_value = None
    user = User(id=uuid4(), clerk_user_id="user_a", email="a@example.com")
    await get_item(session, user, uuid4())
    sql = str(session.scalar.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "skill_bank_items.user_id" in sql


async def test_bullet_lookup_joins_parent_and_filters_current_user():
    session = AsyncMock()
    session.scalar.return_value = None
    user = User(id=uuid4(), clerk_user_id="user_a", email="a@example.com")
    await get_bullet(session, user, uuid4())
    sql = str(session.scalar.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "JOIN skill_bank_items" in sql
    assert "skill_bank_items.user_id" in sql
