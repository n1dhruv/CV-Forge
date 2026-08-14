from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.models.user import User
from app.api.profile import read_profile, update_profile
from app.schemas.profile import ProfileRead, ProfileUpdate
from app.schemas.skill_bank import ItemCreate, ItemUpdate


def test_profile_read_falls_back_to_authenticated_email() -> None:
    user = User(id=uuid4(), email="auth@example.com", contact_email=None)

    assert ProfileRead.from_user(user).contact_email == "auth@example.com"


def test_profile_update_trims_values_allows_clearing_and_rejects_non_web_links() -> None:
    update = ProfileUpdate.model_validate(
        {"full_name": "  Ada Lovelace  ", "github_url": None, "linkedin_url": " https://linkedin.com/in/ada "}
    )

    assert update.full_name == "Ada Lovelace"
    assert update.github_url is None
    assert update.linkedin_url == "https://linkedin.com/in/ada"
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"github_url": "ftp://example.com/ada"})


async def test_profile_route_updates_only_the_authenticated_user() -> None:
    user = User(id=uuid4(), email="auth@example.com", full_name="Old")
    session = AsyncMock()

    updated = await update_profile(
        ProfileUpdate.model_validate({"full_name": " Ada Lovelace "}), session, user
    )

    assert updated.full_name == "Ada Lovelace"
    assert (await read_profile(user)).contact_email == "auth@example.com"
    session.commit.assert_awaited_once()


def test_skill_categories_are_normalized_and_limited_to_skill_items() -> None:
    skill = ItemCreate.model_validate(
        {"type": "skill", "title": "Python", "skill_category": " Languages "}
    )
    experience = ItemCreate.model_validate(
        {"type": "experience", "title": "Engineer", "skill_category": "Ignored"}
    )

    assert skill.skill_category == "Languages"
    assert experience.skill_category is None
    assert ItemUpdate.model_validate({"skill_category": " "}).skill_category is None
