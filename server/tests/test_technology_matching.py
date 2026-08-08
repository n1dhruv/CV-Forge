from app.services.technology_matching import (
    infer_legacy_named_technologies,
    technology_keyword_score,
)


def test_unknown_technology_is_matched_without_a_catalog_entry() -> None:
    score, evidence = technology_keyword_score(
        ["NATS"], "Operated NATS JetStream in production", "any"
    )

    assert score == 1.0
    assert evidence == ["NATS"]


def test_format_variants_are_generated_dynamically() -> None:
    assert technology_keyword_score(["ClickHouse"], "Scaled Click House clusters", "any")[0] == 1.0
    assert technology_keyword_score(["Kubernetes"], "Deployed services to K8s", "any")[0] == 1.0
    assert (
        technology_keyword_score(["Amazon Web Services"], "Built production systems on AWS", "any")[
            0
        ]
        == 1.0
    )


def test_all_mode_requires_evidence_for_every_named_technology() -> None:
    score, evidence = technology_keyword_score(
        ["Docker", "Kubernetes"], "Containerized services with Docker", "all"
    )

    assert score < 0.85
    assert evidence == ["Docker"]


def test_legacy_fallback_detects_unknown_names_without_gating_concepts() -> None:
    assert infer_legacy_named_technologies("Experience with NATS") == ["NATS"]
    assert infer_legacy_named_technologies("Led cross-functional projects") == []
