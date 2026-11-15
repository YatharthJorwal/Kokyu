"""Shared test helpers for the kernel modules app.py was split into (D-062)."""
from __future__ import annotations

from typing import Any

import ambient
import app
import boot
import session
import turns

# Each binds CONFIG at import, so a test's config has to reach every one of them.
_READS_CONFIG = (app, boot, session, turns, ambient)


def set_config(monkeypatch: Any, cfg: Any) -> None:
    """Every kernel module that reads CONFIG sees `cfg` for this test."""
    for module in _READS_CONFIG:
        monkeypatch.setattr(module, "CONFIG", cfg)
