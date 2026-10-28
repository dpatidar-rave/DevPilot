"""Release readiness rules. These tests do not call Ollama or a real Magento repository."""

import os
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.quality import QualityCheckRun
from app.models.review import Review, ReviewFinding
from app.services.release_assessment import (
    HUMAN_KEYS,
    AssessmentInput,
    ChecklistInput,
    DecisionInput,
    Entry,
    FindingInput,
    ModelInput,
    QualityInput,
    build_assessment,
    dump_json,
    render_markdown,
)

CRITICAL = FindingInput("f1", "critical", "Missing authorization", "Controller.php", "security")
HIGH = FindingInput("f2", "high", "Unscoped cache tag", "Model.php", "cache_indexers")
_STAMP = datetime(2026, 10, 27, 18, 0, tzinfo=UTC)


def test_unresolved_critical_finding_blocks_and_is_not_passed() -> None:
    report = build_assessment(replace(_ready(), findings=(CRITICAL,)))

    assert report.readiness == "blocked"
    assert any(
        "Unresolved critical finding: Missing authorization" in item.text
        for item in report.blockers
    )
    assert not any("Missing authorization" in item.text for item in report.passed)


def test_high_finding_without_a_disposition_blocks() -> None:
    report = build_assessment(replace(_ready(), findings=(HIGH,)))

    assert report.readiness == "blocked"
    assert any("needs a disposition: Unscoped cache tag" in item.text for item in report.blockers)


def test_dismissed_high_finding_is_a_disposition() -> None:
    report = build_assessment(
        replace(
            _ready(),
            findings=(HIGH,),
            decisions=(DecisionInput("f2", "dismissed", "", ""),),
        )
    )

    assert report.readiness == "ready_for_human_approval"
    assert not any("Unscoped cache tag" in item.text for item in report.blockers)


def test_valid_critical_waiver_is_not_a_pass() -> None:
    report = build_assessment(
        replace(
            _ready(),
            findings=(CRITICAL,),
            decisions=(DecisionInput("f1", "waived", "Accepted for this release.", "lead"),),
        )
    )

    assert report.readiness == "needs_review"
    assert report.waivers[0].text == "critical: Missing authorization"
    assert report.waivers[0].reason == "Accepted for this release."
    assert report.waivers[0].reviewer == "lead"
    assert not any("Missing authorization" in item.text for item in report.passed)
    assert "Critical and high-severity findings" not in _texts(report.passed)


def test_waiver_without_a_reviewer_still_blocks() -> None:
    report = build_assessment(
        replace(
            _ready(),
            findings=(CRITICAL,),
            decisions=(DecisionInput("f1", "waived", "Accepted for this release.", ""),),
        )
    )

    assert report.readiness == "blocked"
    assert any(
        "cannot be waived without a reason and a reviewer" in item.text for item in report.blockers
    )
    assert report.waivers == ()


def test_missing_phpunit_is_not_passed() -> None:
    report = build_assessment(replace(_base(), checklist=_humans()))

    assert report.readiness == "blocked"
    assert "Automated tests" not in _texts(report.passed)
    assert any("Automated tests" in item.text for item in report.missing)
    assert any("No PHPUnit result" in row.evidence for row in report.checklist)


def test_failed_and_timed_out_tests_block() -> None:
    failed = build_assessment(replace(_ready(), quality=(QualityInput("phpunit", "fail"),)))
    timed_out = build_assessment(replace(_ready(), quality=(QualityInput("phpunit", "timed_out"),)))

    assert failed.readiness == "blocked"
    assert timed_out.readiness == "blocked"
    assert "Automated tests" not in _texts(failed.passed)
    assert "Automated tests" not in _texts(timed_out.passed)
    assert any("PHPUnit result is fail" in row.evidence for row in failed.checklist)


def test_a_recorded_pass_does_not_override_a_failed_test() -> None:
    checklist = _humans() + (
        ChecklistInput("automated_tests", "passed", "I looked at the suite.", "lead"),
    )
    report = build_assessment(
        replace(_ready(), checklist=checklist, quality=(QualityInput("phpunit", "fail"),))
    )

    assert report.readiness == "blocked"
    assert "Automated tests" not in _texts(report.passed)


def test_pending_required_check_is_not_passed() -> None:
    checklist = tuple(item for item in _humans() if item.key != "rollback_plan")
    report = build_assessment(replace(_ready(), checklist=checklist))

    assert report.readiness == "blocked"
    assert "Rollback plan" not in _texts(report.passed)
    assert any("Rollback plan" in item.text for item in report.missing)


def test_not_applicable_is_not_a_pass() -> None:
    checklist = tuple(
        ChecklistInput("database_changes", "not_applicable", "No schema change.", "lead")
        if item.key == "database_changes"
        else item
        for item in _humans()
    )
    report = build_assessment(replace(_ready(), checklist=checklist))

    assert report.readiness == "needs_review"
    assert "Database schema and data patches" not in _texts(report.passed)
    assert any("not applicable" in item.text for item in report.warnings)


def test_failed_phpcs_blocks_even_when_the_checklist_is_complete() -> None:
    report = build_assessment(
        replace(_ready(), quality=(QualityInput("phpunit", "pass"), QualityInput("phpcs", "fail")))
    )

    assert report.readiness == "blocked"
    assert any(
        "Failed mandatory quality check: PHP_CodeSniffer" in item.text for item in report.blockers
    )
    assert not any("PHP_CodeSniffer passed" in item.text for item in report.passed)


def test_skipped_phpstan_is_missing_evidence() -> None:
    report = build_assessment(
        replace(
            _ready(),
            quality=(QualityInput("phpunit", "pass"), QualityInput("phpstan", "skipped")),
        )
    )

    assert report.readiness == "needs_review"
    assert any("PHPStan was skipped" in item.text for item in report.missing)
    assert not any("PHPStan passed" in item.text for item in report.passed)


def test_a_completed_review_alone_cannot_make_a_release_ready() -> None:
    report = build_assessment(_base())

    assert report.readiness == "blocked"
    assert "does not approve the release" in report.statement


def test_complete_evidence_is_ready_for_a_person_to_decide() -> None:
    report = build_assessment(_ready())

    assert report.readiness == "ready_for_human_approval"
    assert report.blockers == ()
    assert report.waivers == ()
    assert "does not approve the release" in report.statement
    assert "does not approve the release" in render_markdown(report)


def test_the_same_inputs_render_the_same_report() -> None:
    first = build_assessment(_ready())
    second = build_assessment(_ready())

    assert first == second
    assert render_markdown(first) == render_markdown(second)
    assert dump_json(first) == dump_json(second)
    assert "qwen2.5-coder:7b" in dump_json(first)
    assert "a" * 40 in dump_json(first)


def test_api_rejects_a_waiver_without_a_reviewer_and_exports_one_snapshot(
    app: FastAPI,
    client: TestClient,
    tmp_path: Path,
) -> None:
    project_id, review_id, finding_id = _stored_review(app, client, tmp_path, with_finding=True)
    rejected = client.put(
        f"/api/reviews/{review_id}/findings/{finding_id}/decision",
        json={"decision": "waived", "reason": "Accepted for this release.", "reviewer": "  "},
    )
    assert rejected.status_code == 422

    preview = client.get(
        f"/api/projects/{project_id}/release-assessment",
        params={"review_id": review_id},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["readiness"] == "blocked"
    assert body["waivers"] == []
    assert "Automated tests" not in body["passed"]
    assert any("Unresolved critical finding" in item for item in body["blockers"])

    group = client.put(
        f"/api/reviews/{review_id}/checklist/critical_high",
        json={"status": "waived", "reason": "Skip them.", "reviewer": "lead"},
    )
    assert group.status_code == 422

    saved = client.put(
        f"/api/reviews/{review_id}/findings/{finding_id}/decision",
        json={"decision": "waived", "reason": "Accepted for this release.", "reviewer": "lead"},
    )
    assert saved.status_code == 200
    waived = saved.json()
    assert waived["readiness"] != "ready_for_human_approval"
    assert waived["waivers"][0]["reviewer"] == "lead"
    assert not any("Missing authorization" in item for item in waived["passed"])

    created = client.post(
        "/api/release-reports",
        json={"project_id": project_id, "review_id": review_id, "readiness": "ready"},
    )
    assert created.status_code == 422
    created = client.post(
        "/api/release-reports",
        json={"project_id": project_id, "review_id": review_id},
    )
    assert created.status_code == 201
    stored = created.json()
    assert stored["status"] == "draft"
    assert stored["readiness"] == "blocked"
    report_id = stored["id"]
    markdown = [
        client.get(f"/api/release-reports/{report_id}/markdown").text,
        client.get(f"/api/release-reports/{report_id}/markdown").text,
    ]
    payload = [
        client.get(f"/api/release-reports/{report_id}/json").text,
        client.get(f"/api/release-reports/{report_id}/json").text,
    ]
    assert markdown[0] == markdown[1]
    assert payload[0] == payload[1]
    assert "Accepted for this release." in markdown[0]
    assert "lead" in markdown[0]
    assert stored["model"]["name"] == "qwen2.5-coder:7b"
    assert stored["head_sha"]
    assert stored["repository_head_sha"]


def test_failed_phpunit_blocks_through_the_api(
    app: FastAPI,
    client: TestClient,
    tmp_path: Path,
) -> None:
    project_id, review_id, _finding_id = _stored_review(app, client, tmp_path, with_finding=False)
    now = datetime.now(UTC)
    with app.state.session_factory() as session:
        session.add(
            QualityCheckRun(
                id=str(uuid4()),
                project_id=project_id,
                review_id=review_id,
                status="completed",
                created_at=now,
                tool="phpunit",
                result="fail",
                exit_code=1,
            )
        )
        session.commit()

    preview = client.get(
        f"/api/projects/{project_id}/release-assessment",
        params={"review_id": review_id},
    )
    body = preview.json()
    assert preview.status_code == 200
    assert body["readiness"] == "blocked"
    assert "Automated tests" not in body["passed"]
    assert any(row["evidence"] == "PHPUnit result is fail." for row in body["checklist"])


def test_complete_api_report_stays_a_draft_for_a_person(
    app: FastAPI,
    client: TestClient,
    tmp_path: Path,
) -> None:
    project_id, review_id, _finding_id = _stored_review(app, client, tmp_path, with_finding=False)
    now = datetime.now(UTC)
    with app.state.session_factory() as session:
        session.add(
            QualityCheckRun(
                id=str(uuid4()),
                project_id=project_id,
                review_id=review_id,
                status="completed",
                created_at=now,
                tool="phpunit",
                result="pass",
                exit_code=0,
            )
        )
        session.commit()
    for key in sorted(HUMAN_KEYS):
        saved = client.put(
            f"/api/reviews/{review_id}/checklist/{key}",
            json={"status": "passed", "reason": "Checked for this release.", "reviewer": "lead"},
        )
        assert saved.status_code == 200

    created = client.post(
        "/api/release-reports",
        json={"project_id": project_id, "review_id": review_id},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["readiness"] == "ready_for_human_approval"
    assert "does not approve the release" in body["statement"]
    assert body["waivers"] == []
    listed = client.get("/api/release-reports")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["readiness"] == "ready_for_human_approval"
    assert listed.json()["items"][0]["status"] == "draft"


def _base() -> AssessmentInput:
    return AssessmentInput(
        project_id="p",
        project_name="Fixture",
        review_id="r",
        review_status="completed",
        base_ref="main",
        head_sha="a" * 40,
        repository_head_sha="b" * 40,
        dirty=False,
        generated_at=_STAMP,
        model=ModelInput("qwen2.5-coder:7b", 8192, 0.1, 1800, 180),
    )


def _humans() -> tuple[ChecklistInput, ...]:
    return tuple(
        ChecklistInput(key, "passed", "Checked for this release.", "lead")
        for key in sorted(HUMAN_KEYS)
    )


def _ready() -> AssessmentInput:
    return replace(_base(), checklist=_humans(), quality=(QualityInput("phpunit", "pass"),))


def _texts(entries: tuple[Entry, ...]) -> list[str]:
    return [entry.text for entry in entries]


def _stored_review(
    app: FastAPI,
    client: TestClient,
    tmp_path: Path,
    *,
    with_finding: bool,
) -> tuple[str, str, str]:
    repo = tmp_path / "repo"
    env = _git_env(tmp_path / "template")
    _init(repo, env)
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, env, "add", "README.md")
    _git(repo, env, "commit", "-m", "initial")
    registered = client.post(
        "/api/projects",
        json={"path": str(repo.resolve()), "name": "Release fixture"},
    )
    assert registered.status_code == 201
    project_id = registered.json()["id"]
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    review_id = str(uuid4())
    finding_id = str(uuid4())
    now = datetime.now(UTC)
    with app.state.session_factory() as session:
        session.add(
            Review(
                id=review_id,
                project_id=project_id,
                status="completed",
                base_ref="main",
                head_ref=sha,
                model_name="qwen2.5-coder:7b",
                context_length=8192,
                temperature=0.1,
                max_output_tokens=1800,
                timeout_seconds=180,
                created_at=now,
                finding_count=1 if with_finding else 0,
            )
        )
        if with_finding:
            session.add(
                ReviewFinding(
                    id=finding_id,
                    review_id=review_id,
                    file_path="Controller.php",
                    start_line=10,
                    end_line=12,
                    severity="critical",
                    category="security",
                    title="Missing authorization",
                    summary="The action does not check authorization.",
                    confidence=0.8,
                    uncertain=True,
                    validation_status="uncertain",
                    created_at=now,
                )
            )
        session.commit()
    return project_id, review_id, finding_id


def _init(repo: Path, env: dict[str, str]) -> None:
    repo.mkdir()
    _git(repo, env, "init", "-b", "main")


def _git(repo: Path, env: dict[str, str], *args: str) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr.decode("utf-8", errors="replace"))


def _git_env(template: Path) -> dict[str, str]:
    template.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "DevPilot Test",
            "GIT_AUTHOR_EMAIL": "devpilot@localhost",
            "GIT_COMMITTER_NAME": "DevPilot Test",
            "GIT_COMMITTER_EMAIL": "devpilot@localhost",
            "GIT_TEMPLATE_DIR": str(template),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
    )
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return env
