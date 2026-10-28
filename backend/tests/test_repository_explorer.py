"""Git discovery uses temporary repositories and never a client checkout."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

SECRET = "super-secret-db-password"
GENERATED = "GENERATED_VENDOR_MARKER"


def test_invalid_paths_and_non_git_directories(client: TestClient, tmp_path: Path) -> None:
    relative = client.post("/api/projects", json={"path": "repos/shop"})
    assert relative.status_code == 422
    assert "absolute" in relative.text

    missing = client.post("/api/projects", json={"path": str(tmp_path / "missing")})
    assert missing.status_code == 400
    assert missing.json()["detail"] == "That path does not exist."

    plain_file = tmp_path / "notes.txt"
    plain_file.write_text("notes", encoding="utf-8")
    not_dir = client.post("/api/projects", json={"path": str(plain_file)})
    assert not_dir.status_code == 400
    assert "directory" in not_dir.json()["detail"]

    folder = tmp_path / "plain"
    folder.mkdir()
    not_git = client.post("/api/projects", json={"path": str(folder)})
    assert not_git.status_code == 400
    assert "not a Git working tree" in not_git.json()["detail"]

    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".git").write_text("gitdir: /tmp/elsewhere\n", encoding="utf-8")
    git_file = client.post("/api/projects", json={"path": str(linked)})
    assert git_file.status_code == 400
    assert "not a Git working tree" in git_file.json()["detail"]


def test_detached_head_uncommitted_changes_and_unusual_names(
    client: TestClient,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "shop"
    env = _git_env(tmp_path / "template")
    _init(repo, env)
    (repo / "base.php").write_text("base\n", encoding="utf-8")
    _git(repo, env, "add", "base.php")
    _git(repo, env, "commit", "-m", "base")
    _git(repo, env, "switch", "-c", "feature")
    (repo / "feature.php").write_text("feature\n", encoding="utf-8")
    (repo / "vendor").mkdir()
    (repo / "vendor" / "autoload.php").write_text(f"<?php // {GENERATED}\n", encoding="utf-8")
    _git(repo, env, "add", "feature.php", "vendor/autoload.php")
    _git(repo, env, "commit", "-m", "feature")
    (repo / "base.php").write_text("changed\n", encoding="utf-8")
    (repo / "staged.php").write_text("staged\n", encoding="utf-8")
    _git(repo, env, "add", "staged.php")
    (repo / "untracked.php").write_text("untracked\n", encoding="utf-8")
    (repo / "odd\nname.php").write_text("<?php echo 1;\n", encoding="utf-8")
    (repo / "quote'name.php").write_text("quoted\n", encoding="utf-8")
    (repo / "--weird.php").write_text("dashed\n", encoding="utf-8")
    env_dir = repo / "app" / "etc"
    env_dir.mkdir(parents=True)
    secret_file = f"<?php return ['password' => '{SECRET}'];\n"
    (env_dir / "env.php").write_text(secret_file, encoding="utf-8")
    (repo / ".env").write_text(f"DB_PASSWORD={SECRET}\n", encoding="utf-8")

    before = _snapshot(repo)
    registered = _register(client, repo)
    assert registered["branch"] == "feature"
    assert registered["detached"] is False
    assert registered["head_subject"] == "feature"
    assert registered["branches"] == ["feature", "main"]
    assert registered["dirty"] is True
    assert registered["uncommitted_warning"]
    assert "will not commit" in registered["uncommitted_warning"]

    changes = client.get(f"/api/projects/{registered['id']}/changes", params={"base": "main"})
    assert changes.status_code == 200, changes.text
    body = changes.json()
    assert _paths(body["committed"]) == {"feature.php", "vendor/autoload.php"}
    assert _paths(body["unstaged"]) == {"base.php"}
    assert _paths(body["staged"]) == {"staged.php"}
    assert {
        "untracked.php",
        "odd\nname.php",
        "quote'name.php",
        "--weird.php",
        "app/etc/env.php",
        ".env",
    } <= _paths(body["untracked"])
    vendor = next(item for item in body["committed"] if item["path"] == "vendor/autoload.php")
    assert vendor["skipped"] == "generated"
    secret = next(item for item in body["untracked"] if item["path"] == "app/etc/env.php")
    assert secret["skipped"] == "sensitive"
    assert body["uncommitted_warning"]

    feature_diff = _diff(client, registered["id"], "committed", "feature.php", "main")
    added = [line for line in feature_diff["lines"] if line["kind"] == "add"]
    assert any("feature" in line["text"] for line in added)
    base_diff = _diff(client, registered["id"], "unstaged", "base.php", "main")
    assert any(line["kind"] == "delete" for line in base_diff["lines"])
    assert any(line["kind"] == "add" and line["text"] == "changed" for line in base_diff["lines"])
    odd = _diff(client, registered["id"], "untracked", "odd\nname.php", "main")
    assert odd["lines"][0]["kind"] == "add"
    weird = _diff(client, registered["id"], "untracked", "--weird.php", "main")
    assert "dashed" in weird["lines"][0]["text"]
    hidden = _diff(client, registered["id"], "untracked", "app/etc/env.php", "main")
    assert hidden["skipped"] == "sensitive"
    assert hidden["lines"] == []
    assert SECRET not in json.dumps(hidden)
    generated = _diff(client, registered["id"], "committed", "vendor/autoload.php", "main")
    assert generated["skipped"] == "generated"
    assert GENERATED not in json.dumps(generated)

    outside = client.get(
        f"/api/projects/{registered['id']}/diff",
        params={"scope": "untracked", "path": "../outside.php", "base": "main"},
    )
    assert outside.status_code == 422
    saved = client.put(
        f"/api/projects/{registered['id']}/selection",
        json={"base": "main", "paths": ["feature.php", "odd\nname.php", "feature.php"]},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["paths"] == ["feature.php", "odd\nname.php"]
    rejected = client.put(
        f"/api/projects/{registered['id']}/selection",
        json={"base": "main", "paths": ["vendor/autoload.php"]},
    )
    assert rejected.status_code == 422
    again = client.get(f"/api/projects/{registered['id']}/changes", params={"base": "main"})
    assert again.json()["selected_paths"] == ["feature.php", "odd\nname.php"]

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["branch"] == "feature"
    duplicate = client.post("/api/projects", json={"path": str(repo)})
    assert duplicate.status_code == 409
    assert _snapshot(repo) == before

    _git(repo, env, "checkout", "--detach")
    detail = client.get(f"/api/projects/{registered['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["detached"] is True
    assert detail.json()["branch"] is None
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        env=env,
        text=True,
    ).strip()
    assert detail.json()["head_sha"] == sha[:12]


def test_aliases_and_external_diff_are_not_executed(client: TestClient, tmp_path: Path) -> None:
    repo = tmp_path / "guard"
    env = _git_env(tmp_path / "template-guard")
    _init(repo, env)
    (repo / "file.php").write_text("one\n", encoding="utf-8")
    _git(repo, env, "add", "file.php")
    _git(repo, env, "commit", "-m", "one")
    (repo / "file.php").write_text("two\n", encoding="utf-8")
    marker = tmp_path / "side-effect"
    script = tmp_path / "ext-diff.sh"
    script.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
    script.chmod(0o755)
    _git(repo, env, "config", "alias.diff", f"!touch {marker}")
    _git(repo, env, "config", "diff.external", str(script))
    registered = _register(client, repo)
    diff = _diff(client, registered["id"], "unstaged", "file.php", "main")
    assert any(line["text"] == "two" for line in diff["lines"])
    assert not marker.exists()


def test_magento_versions_are_reported_only_when_exact(client: TestClient, tmp_path: Path) -> None:
    repo = tmp_path / "magento"
    env = _git_env(tmp_path / "template-magento")
    _init(repo, env)
    (repo / "composer.json").write_text(
        json.dumps(
            {
                "require": {
                    "php": "^8.2",
                    "magento/product-community-edition": "^2.4",
                }
            }
        ),
        encoding="utf-8",
    )
    (repo / "app" / "etc").mkdir(parents=True)
    (repo / "app" / "etc" / "di.xml").write_text("<config/>", encoding="utf-8")
    (repo / "composer.lock").write_text(
        json.dumps(
            {
                "packages": [
                    {"name": "magento/product-community-edition", "version": "2.4.7-p3"}
                ],
                "platform": {"php": "8.2.27"},
            }
        ),
        encoding="utf-8",
    )
    _git(repo, env, "add", "-A")
    _git(repo, env, "commit", "-m", "magento")
    detected = _register(client, repo)
    assert detected["magento"]["detected"] is True
    assert detected["magento"]["edition"] == "Magento Open Source"
    assert detected["magento"]["magento_version"] == "2.4.7-p3"
    assert detected["magento"]["php_version"] == "8.2.27"
    assert "^2.4" not in json.dumps(detected["magento"])
    assert "^8.2" not in json.dumps(detected["magento"])

    (repo / "composer.lock").write_text(
        json.dumps({"packages": [], "platform": {"php": "^8.2"}}),
        encoding="utf-8",
    )
    ranged = client.get(f"/api/projects/{detected['id']}")
    assert ranged.json()["magento"]["magento_version"] is None
    assert ranged.json()["magento"]["php_version"] is None

    other = tmp_path / "library"
    other_env = _git_env(tmp_path / "template-library")
    _init(other, other_env)
    (other / "composer.json").write_text(
        json.dumps({"require": {"php": "8.3.1"}}),
        encoding="utf-8",
    )
    (other / "app" / "etc").mkdir(parents=True)
    (other / "app" / "etc" / "di.xml").write_text("<config/>", encoding="utf-8")
    _git(other, other_env, "add", "-A")
    _git(other, other_env, "commit", "-m", "library")
    plain = _register(client, other)
    assert plain["magento"]["detected"] is False
    assert plain["magento"]["magento_version"] is None
    assert plain["magento"]["php_version"] is None


def test_directory_browser_lists_directories_only(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "browse"
    (root / "projects").mkdir(parents=True)
    (root / "notes.txt").write_text("hidden", encoding="utf-8")
    (root / ".ssh").mkdir()
    response = client.get("/api/browse", params={"path": str(root)})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["directories"] == ["projects"]
    assert "notes.txt" not in body["directories"]
    assert ".ssh" not in body["directories"]


def _register(client: TestClient, repo: Path) -> dict[str, object]:
    response = client.post("/api/projects", json={"path": str(repo)})
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def _diff(
    client: TestClient,
    project_id: object,
    scope: str,
    path: str,
    base: str,
) -> dict[str, object]:
    response = client.get(
        f"/api/projects/{project_id}/diff",
        params={"scope": scope, "path": path, "base": base},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def _paths(items: list[dict[str, str]]) -> set[str]:
    return {item["path"] for item in items}


def _snapshot(repo: Path) -> tuple[bytes, bytes, str]:
    index = (repo / ".git" / "index").read_bytes()
    head = (repo / ".git" / "HEAD").read_bytes()
    worktree = (repo / "base.php").read_text(encoding="utf-8")
    return index, head, worktree


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
