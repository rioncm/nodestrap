"""Public-key helpers for Nodestrap."""

from __future__ import annotations

from pathlib import Path

from nodestrap.config import ConfigError

SUPPORTED_PUBLIC_KEY_PREFIXES = (
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
)


def read_public_key(path: Path) -> str:
    """Read and lightly validate an OpenSSH public key file."""

    if not path.exists():
        raise ConfigError(f"Public key not found: {path}")
    if not path.is_file():
        raise ConfigError(f"Public key path is not a file: {path}")

    value = path.read_text(encoding="utf-8").strip()
    lines = [line for line in value.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ConfigError(f"Public key must contain exactly one key line: {path}")

    parts = lines[0].split()
    if len(parts) < 2:
        raise ConfigError(f"Public key is not in OpenSSH format: {path}")
    if parts[0] not in SUPPORTED_PUBLIC_KEY_PREFIXES:
        raise ConfigError(f"Unsupported public key type {parts[0]} in {path}")
    return lines[0]


def key_name_from_path(path: Path) -> str:
    """Return a stable config key name for a public-key path."""

    name = path.stem
    if name.endswith(".pub"):
        name = name[:-4]
    return name.replace("-", "_").replace(".", "_")


def discover_public_keys(ssh_dir: Path) -> list[Path]:
    """Find public-key files in an SSH directory."""

    if not ssh_dir.exists():
        return []
    return sorted(path for path in ssh_dir.glob("*.pub") if path.is_file())
