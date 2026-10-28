"""Schema contracts that later phases must satisfy."""

import pytest
from pydantic import ValidationError

from app.schemas.project import ProjectCreate
from app.schemas.review import FindingContract, ReviewCreate


def test_finding_contract_flags_low_confidence_and_rejects_extras() -> None:
    with pytest.raises(ValidationError, match="uncertain"):
        FindingContract(
            file_path="app/code.py",
            start_line=10,
            end_line=12,
            severity="high",
            category="correctness",
            title="Possible bug",
            summary="The model was not sure.",
            confidence=0.4,
            uncertain=False,
        )

    accepted = FindingContract(
        file_path="app/code.py",
        start_line=10,
        end_line=12,
        severity="high",
        category="correctness",
        title="Possible bug",
        summary="Needs a person to confirm it.",
        confidence=0.4,
        uncertain=True,
    )
    assert accepted.uncertain is True

    with pytest.raises(ValidationError):
        FindingContract.model_validate(
            {
                "file_path": "app/code.py",
                "start_line": 4,
                "end_line": 2,
                "severity": "low",
                "category": "style",
                "title": "Range",
                "summary": "Lines are reversed.",
                "confidence": 0.8,
                "uncertain": True,
            }
        )


def test_review_create_has_no_provider_field() -> None:
    with pytest.raises(ValidationError):
        ReviewCreate.model_validate(
            {
                "project_id": "project-1",
                "base_ref": "main",
                "head_ref": "topic",
                "provider": "openai",
                "model": "gpt-4o",
            }
        )


def test_project_path_must_be_absolute() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(name="shop", path="relative/path")

    created = ProjectCreate(name="shop", path="/srv/shop")
    assert created.path == "/srv/shop"
