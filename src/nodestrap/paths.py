"""Default filesystem paths used by Nodestrap."""

from __future__ import annotations

from pathlib import Path


def config_dir(home: Path | None = None) -> Path:
    root = home or Path.home()
    return root / ".config" / "nodestrap"


def config_path(home: Path | None = None) -> Path:
    return config_dir(home) / "nodestrap.yaml"


def keys_dir(home: Path | None = None) -> Path:
    return config_dir(home) / "keys"


def state_dir(home: Path | None = None) -> Path:
    root = home or Path.home()
    return root / ".local" / "state" / "nodestrap"


def logs_dir(home: Path | None = None) -> Path:
    return state_dir(home) / "logs"

