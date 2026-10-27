"""Local model policy, chunking, schema checks, and review isolation."""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.benchmark import load_cases
from app.benchmark.score import CaseOutcome, finding_matches, score
from app.config import Settings
from app.main import create_app
from app.security.loopback import LocalOnlyError, assert_loopback_http_url
from app.services.model.errors import InferenceBusy, ModelMissingError
from app.services.model.inference import InferenceRequest, ModelOptions
from app.services.model.ollama import OllamaClient
from app.services.model.ollama_inference import OllamaInference
from app.services.model.policy import (
    ModelNameRejected,
    assert_local_model_name,
    is_large_model,
    setup_instruction,
)
from app.services.review.chunks import chunk_unified_diff
from app.services.review.engine import ReviewEngine
from app.services.review.schema import validate_model_output

_TOKEN = "UNIQUE_SOURCE_TOKEN_9f3c"
_DIFF = """diff --git a/app/code/Vendor/Module/Model/Example.php b/app/code/Vendor/Module/Model/Example.php
index 1111111..2222222 100644
--- a/app/code/Vendor/Module/Model/Example.php
+++ b/app/code/Vendor/Module/Model/Example.php
@@ -8,6 +8,8 @@ class Example
     public function create(array $data)
     {
+        $before = 1;
+        $object = \\Magento\\Framework\\App\\ObjectManager::getInstance()->create(Product::class);
+        $after = 2;
         return $data;
     }
 }
"""


def _options() -> ModelOptions:
    return ModelOptions(
        model="qwen2.5-coder:7b",
        context_length=8192,
        temperature=0.1,
        max_output_tokens=1800,
        timeout_seconds=120,
        endpoint="http://127.0.0.1:11434",
    )


def test_defaults_and_cloud_names_are_rejected() -> None:
    settings = Settings(
        host="127.0.0.1",
        port=8000,
        database_url="sqlite:///:memory:",
        ollama_base_url="http://127.0.0.1:11434",
    )
    assert settings.model_name == "qwen2.5-coder:7b"
    assert settings.context_length == 8192
    assert settings.temperature == 0.1
    assert settings.max_output_tokens == 1800
    assert settings.ollama_timeout_seconds == 120
    with pytest.raises(ValidationError):
        Settings(model_name="gpt-4o", database_url="sqlite:///:memory:")
    with pytest.raises(ValidationError):
        Settings(model_name="claude-3", database_url="sqlite:///:memory:")
    with pytest.raises(ModelNameRejected):
        assert_local_model_name("http://example.com/model")
    allowed = Settings(model_name="qwen2.5-coder:20b", database_url="sqlite:///:memory:")
    assert is_large_model(allowed.model_name) is True
    assert is_large_model("qwen2.5-coder:7b") is False
    with pytest.raises(ValidationError):
        Settings(context_length=9000, database_url="sqlite:///:memory:")
    with pytest.raises(ValidationError):
        Settings(max_output_tokens=2000, database_url="sqlite:///:memory:")
    with pytest.raises(ValidationError):
        Settings(temperature=1.5, database_url="sqlite:///:memory:")


def test_endpoint_must_resolve_to_loopback() -> None:
    def public(_host: str) -> list[str]:
        return ["203.0.113.10"]

    def mixed(_host: str) -> list[str]:
        return ["127.0.0.1", "203.0.113.10"]

    def local(_host: str) -> list[str]:
        return ["127.0.0.1"]

    with pytest.raises(LocalOnlyError):
        assert_loopback_http_url("http://models.example:11434", resolve=public)
    with pytest.raises(LocalOnlyError):
        assert_loopback_http_url("http://models.example:11434", resolve=mixed)
    assert assert_loopback_http_url("http://models.example:11434", resolve=local) == "http://127.0.0.1:11434"


def test_chunks_keep_path_ranges_and_context() -> None:
    packed = chunk_unified_diff(_DIFF, max_chars=20000)
    assert packed.truncated is False
    assert len(packed.chunks) == 1
    chunk = packed.chunks[0]
    assert chunk.path == "app/code/Vendor/Module/Model/Example.php"
    assert 10 in chunk.changed_lines
    assert 12 in chunk.changed_lines
    assert "return $data;" in chunk.text
    assert any(item.start <= 10 <= item.end for item in chunk.ranges)

    split = chunk_unified_diff(_DIFF, max_chars=280)
    assert len(split.chunks) > 1
    assert all(chunk.path.endswith("Example.php") for chunk in split.chunks)
    assert all(len(chunk.text) <= 800 for chunk in split.chunks)
    assert any("return $data;" in chunk.text or "$before" in chunk.text for chunk in split.chunks)


def test_schema_flags_uncertain_findings_and_drops_invalid_output() -> None:
    packed = chunk_unified_diff(_DIFF, max_chars=20000)
    chunk = packed.chunks[0]
    raw = json.dumps(
        {
            "findings": [
                {
                    "path": chunk.path,
                    "line_start": 9,
                    "line_end": 11,
                    "severity": "high",
                    "category": "object-manager",
                    "summary": "Direct ObjectManager use.",
                    "confidence": "high",
                },
                {
                    "path": chunk.path,
                    "line_start": 9,
                    "line_end": 9,
                    "severity": "low",
                    "category": "style",
                    "summary": "Maybe a naming issue.",
                    "confidence": "low",
                },
                {
                    "path": "other.php",
                    "line_start": 400,
                    "line_end": 401,
                    "severity": "high",
                    "category": "object-manager",
                    "summary": "Outside the diff.",
                    "confidence": "high",
                },
                {"summary": "not a finding"},
            ]
        }
    )
    validated = validate_model_output(raw, chunk)
    assert len(validated.findings) == 3
    assert validated.findings[0].uncertain is False
    assert validated.findings[1].uncertain is True
    assert validated.findings[2].uncertain is True
    assert validated.errors
    broken = validate_model_output("not json and not a finding", chunk)
    assert broken.findings == ()
    assert broken.errors
    assert _TOKEN not in broken.errors[0]


class _FakeInference:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prepared = 0
        self.calls = 0

    def prepare(self, options: ModelOptions) -> None:
        self.prepared += 1
        assert options.model == "qwen2.5-coder:7b"

    def complete(self, request: InferenceRequest, cancel_event: threading.Event) -> str:
        self.calls += 1
        assert "ObjectManager" in request.prompt
        return self.text


def test_engine_uses_the_inference_protocol(caplog: pytest.LogCaptureFixture) -> None:
    packed = chunk_unified_diff(_DIFF, max_chars=20000)
    payload = json.dumps(
        {
            "findings": [
                {
                    "path": packed.chunks[0].path,
                    "line_start": 9,
                    "line_end": 11,
                    "severity": "critical",
                    "category": "object-manager",
                    "summary": "ObjectManager is used in a model.",
                    "confidence": "high",
                }
            ]
        }
    )
    client = _FakeInference(payload)
    engine = ReviewEngine(client)
    caplog.set_level(logging.DEBUG)
    result = engine.review_diff(_DIFF, _options(), threading.Event())
    assert client.prepared == 1
    assert client.calls == 1
    assert result.contacted_model is True
    assert result.findings[0].uncertain is False
    assert "ObjectManager::getInstance" not in caplog.text
    assert payload not in caplog.text

    idle = _FakeInference(payload)
    empty = engine_with(idle).review_diff("", _options(), threading.Event())
    assert idle.prepared == 0
    assert empty.contacted_model is False


def engine_with(client: _FakeInference) -> ReviewEngine:
    return ReviewEngine(client)


def test_review_engine_does_not_import_ollama() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "services" / "review"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "import httpx" not in text
        assert "ollama" not in text


def test_one_inference_at_a_time_and_no_model_download() -> None:
    started = threading.Event()
    release = threading.Event()
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}]})
        if request.url.path == "/api/generate":
            started.set()
            assert release.wait(2)
            return httpx.Response(200, json={"response": "{}"})
        raise AssertionError(request.url.path)

    inference = OllamaInference(OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler)))
    inference.prepare(_options())
    errors: list[BaseException] = []

    def hold() -> None:
        try:
            inference.complete(InferenceRequest(prompt="hold", options=_options()), threading.Event())
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    worker = threading.Thread(target=hold)
    worker.start()
    assert started.wait(2)
    with pytest.raises(InferenceBusy):
        inference.complete(InferenceRequest(prompt="second", options=_options()), threading.Event())
    release.set()
    worker.join(2)
    assert errors == []
    assert "/api/pull" not in paths

    def missing(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "other:7b"}]})
        if request.url.path == "/api/pull":
            return httpx.Response(200, json={"status": "pulled"})
        raise AssertionError(request.url.path)

    absent = OllamaInference(OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(missing)))
    with pytest.raises(ModelMissingError) as caught:
        absent.prepare(_options())
    assert "ollama pull qwen2.5-coder:7b" in caught.value.setup_instruction
    assert "does not download" in setup_instruction("qwen2.5-coder:7b").lower()
    assert "/api/pull" not in paths


def test_benchmark_scores_known_cases() -> None:
    cases = load_cases()
    assert [item.case_id for item in cases] == [
        "object-manager",
        "load-in-loop",
        "comment-wording",
        "local-rename",
    ]
    outcomes = (
        CaseOutcome("object-manager", "defect", True, 1, 0, None, 1.2),
        CaseOutcome("load-in-loop", "defect", False, 0, 1, None, 1.0),
        CaseOutcome("comment-wording", "harmless", False, 1, 0, None, 0.5),
        CaseOutcome("local-rename", "harmless", False, 0, 1, None, 0.25),
    )
    report = score("qwen2.5-coder:7b", cases, outcomes)
    assert report.detection_rate == 0.5
    assert report.false_positive_rate == 0.5
    assert report.response_time_seconds == 2.95
    assert report.errors == ()
    assert finding_matches("object-manager", "Uses ObjectManager", ("object manager",)) is True


def test_large_model_is_refused_before_any_request(database_url: str) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        raise AssertionError("Ollama was contacted")

    settings = Settings(model_name="qwen2.5-coder:20b", database_url=database_url)
    application = create_app(
        settings=settings,
        ollama=OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler)),
    )
    client = TestClient(application)
    refused = client.post(
        "/api/reviews/start",
        json={"path": "/tmp/unused", "approved": True, "confirm_large_model": False},
    )
    assert refused.status_code == 400
    assert "16 GB" in refused.json()["message"]
    assert calls == []
    status = client.get("/api/system/status")
    assert status.json()["model"]["large_model"] is True
    assert status.json()["model"]["availability"] == "not_checked"
    assert calls == []


def test_review_sends_a_bounded_diff_and_hides_source(database_url: str, tmp_path: Path) -> None:
    _commit_change(tmp_path)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}]})
        if request.url.path != "/api/generate":
            raise AssertionError(request.url.path)
        body = json.loads(request.content.decode("utf-8"))
        assert body["keep_alive"] == "10m"
        assert body["options"]["temperature"] == 0.1
        assert body["options"]["num_ctx"] == 8192
        assert body["options"]["num_predict"] == 1800
        assert _TOKEN in body["prompt"]
        path = body["prompt"].split("File: ", 1)[1].split(". Changed", 1)[0]
        finding = {
            "findings": [
                {
                    "path": path,
                    "line_start": 1,
                    "line_end": 80,
                    "severity": "high",
                    "category": "object-manager",
                    "summary": "Reported ObjectManager use.",
                    "confidence": "high",
                }
            ]
        }
        return httpx.Response(200, json={"response": json.dumps(finding)})

    application = create_app(
        ollama=OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    )
    assert "devpilot.sqlite" in database_url
    client = TestClient(application)
    started = client.post(
        "/api/reviews/start",
        json={"path": str(tmp_path), "approved": True, "confirm_large_model": False},
    )
    assert started.status_code == 200
    job_id = started.json()["id"]
    body = _wait_for_job(client, job_id)
    assert body["status"] == "completed"
    assert _TOKEN not in json.dumps(body)
    assert body["findings"][0]["uncertain"] is False
    assert "not treated as defects" in body["message"]
    assert "/api/pull" not in calls
    assert calls.count("/api/generate") == 1


def test_missing_model_returns_setup_text(database_url: str, tmp_path: Path) -> None:
    _commit_change(tmp_path)
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        raise AssertionError(request.url.path)

    application = create_app(
        ollama=OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    )
    assert database_url
    client = TestClient(application)
    started = client.post(
        "/api/reviews/start",
        json={"path": str(tmp_path), "approved": True},
    )
    body = _wait_for_job(client, started.json()["id"])
    assert body["status"] == "failed"
    assert "ollama pull qwen2.5-coder:7b" in body["setup_instruction"]
    assert "/api/pull" not in paths
    assert "/api/generate" not in paths


def _wait_for_job(client: TestClient, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    body: dict[str, object] = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/reviews/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload, dict)
        body = payload
        if body.get("status") != "running":
            return body
        time.sleep(0.05)
    raise AssertionError("review did not finish")


def _commit_change(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "devpilot@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "DevPilot"], cwd=tmp_path, check=True)
    source = tmp_path / "Example.php"
    source.write_text("<?php\nclass Example {}\n", encoding="utf-8")
    subprocess.run(["git", "add", "Example.php"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    source.write_text(
        f"<?php\nclass Example {{\n    public function create() {{\n        return '{_TOKEN}';\n    }}\n}}\n",
        encoding="utf-8",
    )
