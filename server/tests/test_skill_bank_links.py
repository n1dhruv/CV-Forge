import pytest
from pydantic import ValidationError

from app.schemas.skill_bank import ItemCreate


def link(label: str, url: str) -> dict[str, str]:
    return {"label": label, "url": url}


def test_project_accepts_up_to_two_optional_named_links() -> None:
    item = ItemCreate(
        type="project",
        title="CV Forge",
        links=[
            link("Live", "https://example.test"),
            link("GitHub", "https://github.com/example/cv-forge"),
        ],
    )

    assert [row.label for row in item.links] == ["Live", "GitHub"]


def test_project_rejects_more_than_two_links() -> None:
    with pytest.raises(ValidationError, match="at most 2 links"):
        ItemCreate(
            type="project",
            title="CV Forge",
            links=[link(str(index), f"https://example.test/{index}") for index in range(3)],
        )


def test_certificate_accepts_one_link_and_rejects_two() -> None:
    assert ItemCreate(
        type="certification",
        title="Cloud certificate",
        links=[link("Credential", "https://example.test/credential")],
    ).links

    with pytest.raises(ValidationError, match="at most 1 link"):
        ItemCreate(
            type="certification",
            title="Cloud certificate",
            links=[
                link("Credential", "https://example.test/credential"),
                link("Other", "https://example.test/other"),
            ],
        )


@pytest.mark.parametrize(
    "payload",
    [
        link("", "https://example.test"),
        link("Live", "javascript:alert(1)"),
    ],
)
def test_named_links_require_a_label_and_http_url(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        ItemCreate(type="project", title="CV Forge", links=[payload])


def test_non_linkable_items_reject_links() -> None:
    with pytest.raises(ValidationError, match="only projects and certifications"):
        ItemCreate(
            type="experience",
            title="Engineer",
            links=[link("Company", "https://example.test")],
        )
