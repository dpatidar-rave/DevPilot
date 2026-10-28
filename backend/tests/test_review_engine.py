"""Local review engine. Ollama is mocked, so these tests never open port 11434."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.models.project import Project
from app.models.review import Review
from app.services.model_gateway import CancellationToken, InferenceError, ModelGateway
from app.services.persistence import add_project
from app.services.repository import DiffLine, FileDiff
from app.services.review import ReviewService, mark_interrupted
from app.services.review_analysis import (
    DiffChunk,
    PreparedReview,
    chunk_rows,
    chunks_from_diff,
    dedupe_findings,
    interpret_response,
)

EVIDENCE = "return $this->load();"
OTHER_LINE = "LINE_ONLY_IN_THE_DIFF_NOT_THE_FINDING"


class ScriptedModel:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []
        self.model_name = "qwen2.5-coder:7b"

    def complete(self, messages: list[dict[str, str]], cancel: CancellationToken) -> str:
        self.calls.append(messages)
        if cancel.is_cancelled():
            raise InferenceError("cancelled")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if not isinstance(item, str):
            raise InferenceError("malformed")
        return item


def _chunk(text: str) -> DiffChunk:
    return DiffChunk(
        file_path="app/code/Example.php",
        scope="unstaged",
        text=text,
        line_numbers=frozenset({12, 13}),
    )


def _payload(
    evidence: str,
    *,
    line: int = 12,
    severity: str = "high",
    title: str = "Loads in a loop",
) -> str:
    return json.dumps(
        {
            "findings": [
                {
                    "category": "performance",
                    "severity": severity,
                    "confidence": 0.8,
                    "title": title,
                    "explanation": "The change loads a model where a collection would do.",
                    "evidence": evidence,
                    "file_path": "app/code/Example.php",
                    "start_line": line,
                    "end_line": line,
                    "remediation": "Load the collection once.",
                }
            ],
            "limitations": [],
        }
    )


def _prepared(chunks: list[DiffChunk] | None = None) -> PreparedReview:
    return PreparedReview(
        base="main",
        head="abc123def456",
        chunks=chunks or [],
        reviewed=["app/code/Example.php"] if chunks else [],
        skipped=[("vendor/autoload.php", "Generated directory.")],
        limitations=[],
    )


def _project(app: FastAPI) -> Project:
    now = datetime.now(UTC)
    project = Project(
        id=str(uuid4()),
        name="shop",
        path="/tmp/devpilot-review-unit",
        created_at=now,
        updated_at=now,
    )
    add_project(app.state.session_factory, project)
    return project


def _service(app: FastAPI, model: ScriptedModel, prepared: PreparedReview) -> ReviewService:
    return ReviewService(
        model,
        app.state.session_factory,
        app.state.settings,
        synchronous=True,
        collector=lambda _repo, _base, _paths, _budget: prepared,
    )


def test_chunks_split_an_oversized_diff() -> None:
    rows = [(number, f"+{number}: " + ("x" * 80)) for number in range(1, 30)]
    chunks = chunk_rows("app/code/Example.php", "unstaged", rows, 240)

    assert len(chunks) > 1
    assert all("file: app/code/Example.php" in chunk.text for chunk in chunks)
    assert all(len(chunk.text) < 1200 for chunk in chunks)
    combined = "\n".join(chunk.text for chunk in chunks)
    assert "+1:" in combined
    assert "+29:" in combined


def test_empty_diff_does_not_call_the_model(app: FastAPI) -> None:
    model = ScriptedModel([])
    project = _project(app)
    service = _service(app, model, _prepared())

    review_id = service.start(project.id, "main", ["app/code/Example.php"])
    detail = service.detail(review_id)

    assert model.calls == []
    assert detail.status == "completed"
    assert detail.finding_count == 0
    assert any("no reviewable" in note.lower() for note in detail.limitations)
    assert detail.files_skipped == 1


def test_malformed_json_becomes_a_limitation(app: FastAPI) -> None:
    text = f"file: app/code/Example.php\nscope: unstaged\n+12: {EVIDENCE}\n+13: {OTHER_LINE}"
    model = ScriptedModel(["this is not json", _payload(EVIDENCE)])
    project = _project(app)
    service = _service(app, model, _prepared([_chunk(text), _chunk(text)]))

    detail = service.detail(service.start(project.id, "main", ["app/code/Example.php"]))

    assert detail.status == "completed"
    assert len(detail.findings) == 1
    assert any("malformed" in note.lower() for note in detail.limitations)
    stored = json.dumps(detail.model_dump(mode="json"))
    assert OTHER_LINE not in stored
    assert EVIDENCE in stored


def test_schema_mismatch_and_invented_lines_are_not_stored() -> None:
    chunk = _chunk(f"file: app/code/Example.php\nscope: unstaged\n+12: {EVIDENCE}")
    findings, notes = interpret_response('{"findings": [], "extra": true}', chunk)
    assert findings == []
    assert notes

    invented = _payload("DROP TABLE customers", line=99)
    findings, notes = interpret_response(invented, chunk)
    assert findings == []
    assert any("not in the diff" in note for note in notes)

    grounded, notes = interpret_response(_payload(EVIDENCE), chunk)
    assert notes == []
    assert len(grounded) == 1
    assert grounded[0].uncertain is False
    assert grounded[0].start_line == 12


def test_duplicate_findings_collapse_to_the_higher_severity() -> None:
    chunk = _chunk(f"file: app/code/Example.php\nscope: unstaged\n+12: {EVIDENCE}")
    body = json.loads(_payload(EVIDENCE, severity="low", title="Loads in a loop"))
    higher = json.loads(_payload(EVIDENCE, severity="high", title="Same load"))
    body["findings"].append(higher["findings"][0])
    findings, _notes = interpret_response(json.dumps(body), chunk)

    kept = dedupe_findings(findings)

    assert len(kept) == 1
    assert kept[0].severity == "high"


def test_secret_and_binary_diffs_are_not_chunked() -> None:
    secret = FileDiff(
        "app/etc/config.php",
        "unstaged",
        False,
        False,
        None,
        "php",
        [DiffLine("add", "BEGIN PRIVATE KEY abc", None, 4)],
    )
    chunks, _notes, reason = chunks_from_diff(secret, 1000)
    assert chunks == []
    assert reason is not None
    assert "PRIVATE KEY" not in reason

    binary = FileDiff("app/design/logo.png", "untracked", True, False, None, None, [])
    chunks, _notes, reason = chunks_from_diff(binary, 1000)
    assert chunks == []
    assert reason == "Binary file."


def test_missing_model_timeout_and_local_chat_shape(settings: Settings) -> None:
    seen: dict[str, object] = {}

    def missing(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(404, json={"error": "model 'qwen2.5-coder:7b' not found"})

    gateway = ModelGateway(settings, transport=httpx.MockTransport(missing))
    with pytest.raises(InferenceError) as missing_error:
        gateway.complete(
            [{"role": "user", "content": "UNIQUE_PROMPT_SHOULD_NOT_LEAK"}],
            CancellationToken(),
        )

    assert missing_error.value.code == "model_missing"
    assert str(missing_error.value) == "model_missing"
    assert seen["url"] == "http://127.0.0.1:11434/api/chat"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "qwen2.5-coder:7b"
    assert body["stream"] is False
    assert "tools" not in body
    assert body["options"]["temperature"] == 0.1
    assert body["options"]["num_ctx"] == 8192

    def timed_out(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    gateway = ModelGateway(settings, transport=httpx.MockTransport(timed_out))
    with pytest.raises(InferenceError) as timeout_error:
        gateway.complete([{"role": "user", "content": "again"}], CancellationToken())
    assert timeout_error.value.code == "timeout"

    def redirect(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://example.invalid/steal"})

    gateway = ModelGateway(settings, transport=httpx.MockTransport(redirect))
    with pytest.raises(InferenceError) as redirect_error:
        gateway.complete([{"role": "user", "content": "again"}], CancellationToken())
    assert redirect_error.value.code == "unavailable"


def test_model_failure_is_stored_without_the_prompt(app: FastAPI) -> None:
    text = f"file: app/code/Example.php\nscope: unstaged\n+12: {EVIDENCE}"
    model = ScriptedModel([InferenceError("model_missing")])
    project = _project(app)
    service = _service(app, model, _prepared([_chunk(text)]))

    detail = service.detail(service.start(project.id, "main", ["app/code/Example.php"]))

    assert detail.status == "failed"
    assert detail.error_code == "model_missing"
    assert detail.findings == []
    assert "hosted" in (detail.error_message or "")
    log_text = Path(app.state.settings.log_dir, "devpilot.log").read_text(encoding="utf-8")
    assert EVIDENCE not in log_text
    assert "UNIQUE_PROMPT" not in log_text


def test_review_api_reports_ai_suggestions(app: FastAPI, client: TestClient) -> None:
    text = f"file: app/code/Example.php\nscope: unstaged\n+12: {EVIDENCE}"
    model = ScriptedModel([_payload(EVIDENCE)])
    project = _project(app)
    app.state.review_service = _service(app, model, _prepared([_chunk(text)]))

    rejected = client.post(
        "/api/reviews",
        json={
            "project_id": project.id,
            "base_ref": "main",
            "paths": ["app/code/Example.php"],
            "provider": "openai",
        },
    )
    assert rejected.status_code == 422

    response = client.post(
        "/api/reviews",
        json={"project_id": project.id, "base_ref": "main", "paths": ["app/code/Example.php"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["model"] == "qwen2.5-coder:7b"
    assert body["findings"][0]["origin"] == "ai_suggestion"
    assert body["findings"][0]["needs_human_verification"] is True
    assert body["findings"][0]["evidence_checked"] is True
    assert body["temperature"] == 0.1
    listed = client.get("/api/reviews").json()["items"]
    assert listed[0]["id"] == body["id"]


def test_a_restart_does_not_leave_a_review_running(app: FastAPI) -> None:
    now = datetime.now(UTC)
    project = _project(app)
    with app.state.session_factory() as session:
        session.add(
            Review(
                id=str(uuid4()),
                project_id=project.id,
                status="running",
                model_name="qwen2.5-coder:7b",
                context_length=8192,
                created_at=now,
                finding_count=0,
            )
        )
        session.commit()

    mark_interrupted(app.state.session_factory)
    records = app.state.review_service.list_records()

    assert records[0].status == "failed"
    assert records[0].error_code == "interrupted"
