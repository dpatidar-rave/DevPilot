"""Detect a Magento root from composer.json and app/etc/di.xml.

Versions are returned only when the file states an exact version. A range such
as ^2.4 is not reported as the installed version.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_COMPOSER_LIMIT = 1_000_000
_LOCK_LIMIT = 8_000_000
_PRODUCT_PACKAGES = (
    "magento/product-enterprise-edition",
    "magento/product-community-edition",
    "magento/magento2-base",
)
_EXACT_VERSION = re.compile(r"v?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.]+)?")
_RANGE_MARKERS = ("^", "~", "*", ">", "<", "|", " ")


@dataclass(frozen=True)
class MagentoInfo:
    detected: bool
    edition: str | None
    magento_version: str | None
    php_version: str | None


def detect_magento(repo: Path) -> MagentoInfo:
    composer_path = repo / "composer.json"
    di_path = repo / "app" / "etc" / "di.xml"
    composer = _read_json(composer_path, _COMPOSER_LIMIT)
    if composer is None or not _regular_file(di_path):
        return MagentoInfo(False, None, None, None)
    require = composer.get("require")
    if not isinstance(require, dict):
        return MagentoInfo(False, None, None, None)
    magento_names = [
        key for key in require if isinstance(key, str) and key.startswith("magento/")
    ]
    if not magento_names:
        return MagentoInfo(False, None, None, None)
    edition = _edition(require)
    lock = _read_json(repo / "composer.lock", _LOCK_LIMIT)
    version = _product_version(lock, require)
    php_version = _php_version(lock)
    return MagentoInfo(True, edition, version, php_version)


def _edition(require: dict[object, object]) -> str | None:
    if "magento/product-enterprise-edition" in require:
        return "Adobe Commerce"
    if (
        "magento/product-community-edition" in require
        or "magento/magento2-base" in require
    ):
        return "Magento Open Source"
    return None


def _product_version(lock: dict[str, object] | None, require: dict[object, object]) -> str | None:
    if lock is not None:
        for package in _packages(lock):
            name = package.get("name")
            if name in _PRODUCT_PACKAGES:
                found = exact_version(package.get("version"))
                if found is not None:
                    return found
    for name in _PRODUCT_PACKAGES:
        found = exact_version(require.get(name))
        if found is not None:
            return found
    return None


def _php_version(lock: dict[str, object] | None) -> str | None:
    if lock is None:
        return None
    platform = lock.get("platform")
    if not isinstance(platform, dict):
        return None
    return exact_version(platform.get("php"))


def _packages(lock: dict[str, object]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for key in ("packages", "packages-dev"):
        rows = lock.get(key)
        if not isinstance(rows, list):
            continue
        found.extend(row for row in rows if isinstance(row, dict))
    return found


def exact_version(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith("dev-") or any(marker in text for marker in _RANGE_MARKERS):
        return None
    if _EXACT_VERSION.fullmatch(text) is None:
        return None
    return text[1:] if text.startswith("v") else text


def _read_json(path: Path, limit: int) -> dict[str, object] | None:
    if not _regular_file(path):
        return None
    try:
        if path.stat().st_size > limit:
            return None
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _regular_file(path: Path) -> bool:
    try:
        return path.is_file() and not path.is_symlink()
    except OSError:
        return False
