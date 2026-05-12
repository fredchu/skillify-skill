"""Receipt storage for content-bound cross-modal evaluation results.

Receipts are named with the first eight hex characters of the evaluated
``SKILL.md`` file's SHA-256 digest. When that file changes, the current digest
changes too, so callers can treat a missing current receipt as a stale result.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import platformdirs


SCHEMA_VERSION = "v1"


def compute_sha8(file_path: Path) -> str:
    """Return the first eight hex characters of the file's SHA-256 digest."""

    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return digest[:8]


def receipt_filename(skill_slug: str, sha8: str) -> str:
    """Return the JSON receipt filename for ``skill_slug`` and ``sha8``."""

    return f"{skill_slug}-{sha8}.json"


def receipt_dir() -> Path:
    """Return and create the default receipt directory under the user cache."""

    path = Path(platformdirs.user_cache_dir("skillify")) / "eval-receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_receipt(
    skill_slug: str,
    skill_path: Path,
    eval_data: dict[str, Any],
    base_dir: Path | None = None,
) -> Path:
    """Write a content-bound evaluation receipt and return its path.

    Args:
        skill_slug: Stable slug identifying the evaluated skill.
        skill_path: Path to the evaluated skill file.
        eval_data: Caller-provided evaluation data stored under the ``eval``
            envelope key without validation or transformation.
        base_dir: Optional receipt directory override. When omitted, the
            platform-specific user cache receipt directory is used.

    Returns:
        The path of the receipt JSON file written.
    """

    sha8 = compute_sha8(skill_path)
    target_dir = _target_dir(base_dir)
    target_path = target_dir / receipt_filename(skill_slug, sha8)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "skill_slug": skill_slug,
        "skill_sha8": sha8,
        "eval": eval_data,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    target_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target_path


def find_current_receipt(
    skill_slug: str,
    skill_path: Path,
    base_dir: Path | None = None,
) -> Path | None:
    """Return the receipt path matching the current skill digest, if present.

    A ``None`` return means there is no receipt for the file's current SHA-8,
    which callers can use as the staleness signal.
    """

    sha8 = compute_sha8(skill_path)
    candidate = _target_dir(base_dir) / receipt_filename(skill_slug, sha8)
    if candidate.exists():
        return candidate
    return None


def list_receipts(
    skill_slug: str,
    base_dir: Path | None = None,
) -> list[Path]:
    """Return all receipts for ``skill_slug``, sorted by mtime descending."""

    target_dir = _target_dir(base_dir)
    return sorted(
        target_dir.glob(f"{skill_slug}-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _target_dir(base_dir: Path | None) -> Path:
    if base_dir is None:
        return receipt_dir()

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir
