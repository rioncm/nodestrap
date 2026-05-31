"""Configuration loading and validation for Nodestrap."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

VALID_HOST_STATUSES = frozenset({"new", "completed", "retry", "failed", "skipped"})
DEFAULT_HOST_STATUS = "new"
ACCOUNT_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class ValidationIssue:
    """A human-readable config validation problem."""

    message: str


class ConfigError(Exception):
    """Raised when a config file cannot be read or parsed."""


def load_config(path: Path) -> dict[str, Any]:
    """Load a Nodestrap YAML config file."""

    try:
        import yaml
    except ModuleNotFoundError as exc:
        return _load_json_compatible_yaml(path, exc)

    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a YAML mapping.")
    return data


def write_config(path: Path, data: dict[str, Any]) -> None:
    """Write a Nodestrap YAML config file."""

    try:
        import yaml
    except ModuleNotFoundError as exc:
        _write_json_compatible_yaml(path, data)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def validate_config(data: dict[str, Any], *, keys_base: Path | None = None) -> list[ValidationIssue]:
    """Validate config structure and references."""

    issues: list[ValidationIssue] = []

    defaults = _mapping(data.get("defaults"), "defaults", issues)
    keys = _mapping(data.get("keys"), "keys", issues)
    users = _mapping(data.get("users"), "users", issues)
    hosts = data.get("hosts", [])

    if hosts is None:
        hosts = []
    if not isinstance(hosts, list):
        issues.append(ValidationIssue("hosts must be a list."))
        hosts = []

    _validate_defaults(defaults, keys, issues)
    _validate_keys(keys, keys_base, issues)
    _validate_users(users, keys, issues)
    _validate_hosts(hosts, users, issues)

    return issues


def empty_config() -> dict[str, Any]:
    """Return a minimal config skeleton."""

    return {
        "defaults": {
            "connect_user": None,
            "managed_user": None,
            "public_key": None,
            "ssh_port": 22,
            "disable_password_auth": True,
        },
        "keys": {},
        "users": {},
        "hosts": [],
    }


def set_defaults(
    data: dict[str, Any],
    *,
    connect_user: str | None = None,
    managed_user: str | None = None,
    public_key: str | None = None,
    ssh_port: int | None = None,
    disable_password_auth: bool | None = None,
) -> dict[str, Any]:
    """Update configured defaults with provided values."""

    defaults = data.setdefault("defaults", {})
    if not isinstance(defaults, dict):
        raise ConfigError("defaults must be a mapping before updating defaults.")
    if connect_user is not None:
        defaults["connect_user"] = connect_user
    if managed_user is not None:
        defaults["managed_user"] = managed_user
    if public_key is not None:
        defaults["public_key"] = public_key
    if ssh_port is not None:
        defaults["ssh_port"] = ssh_port
    if disable_password_auth is not None:
        defaults["disable_password_auth"] = disable_password_auth
    return data


def add_key(
    data: dict[str, Any],
    name: str,
    *,
    file: str,
    label: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Return config data with a public-key definition added or updated."""

    keys = data.setdefault("keys", {})
    if not isinstance(keys, dict):
        raise ConfigError("keys must be a mapping before adding a key.")
    if name in keys and not force:
        raise ConfigError(f"Key already exists: {name}")
    keys[name] = {
        "file": file,
        "label": label or name.replace("_", " "),
    }
    return data


def add_host(
    data: dict[str, Any],
    hostname: str,
    *,
    users: list[str] | None = None,
    connect_user: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Return config data with a host entry added or updated."""

    hosts = data.setdefault("hosts", [])
    if not isinstance(hosts, list):
        raise ConfigError("hosts must be a list before adding a host.")

    existing = next((host for host in hosts if isinstance(host, dict) and host.get("host") == hostname), None)
    if existing and not force:
        raise ConfigError(f"Host already exists: {hostname}")

    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    host_users = users or _default_host_users(defaults)
    entry = {
        "host": hostname,
        "status": DEFAULT_HOST_STATUS,
        "connect_user": connect_user if connect_user is not None else defaults.get("connect_user"),
        "users": host_users,
        "completed_at": None,
        "last_error": None,
    }

    if existing:
        existing.update(entry)
    else:
        hosts.append(entry)
    return data


def add_user(
    data: dict[str, Any],
    name: str,
    *,
    username: str | None = None,
    public_keys: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Return config data with a managed user definition added or updated."""

    users = data.setdefault("users", {})
    if not isinstance(users, dict):
        raise ConfigError("users must be a mapping before adding a user.")
    if name in users and not force:
        raise ConfigError(f"User already exists: {name}")

    users[name] = {
        "username": username or name,
        "public_keys": public_keys or [],
    }
    return data


def hosts_by_status(data: dict[str, Any]) -> dict[str, list[str]]:
    """Group hostnames by status."""

    grouped = {status: [] for status in sorted(VALID_HOST_STATUSES)}
    hosts = data.get("hosts", [])
    if not isinstance(hosts, list):
        return grouped
    for host in hosts:
        if not isinstance(host, dict):
            continue
        name = host.get("host")
        status = host.get("status", DEFAULT_HOST_STATUS)
        if isinstance(name, str) and isinstance(status, str):
            grouped.setdefault(status, []).append(name)
    return grouped


def selected_hosts(
    data: dict[str, Any],
    *,
    host: str | None = None,
    status: str = DEFAULT_HOST_STATUS,
) -> list[dict[str, Any]]:
    """Return host entries selected for a run."""

    hosts = data.get("hosts", [])
    if not isinstance(hosts, list):
        return []

    selected = []
    for entry in hosts:
        if not isinstance(entry, dict):
            continue
        if host is not None and entry.get("host") != host:
            continue
        if host is None and entry.get("status", DEFAULT_HOST_STATUS) != status:
            continue
        selected.append(entry)
    return selected


def _mapping(value: Any, name: str, issues: list[ValidationIssue]) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        issues.append(ValidationIssue(f"{name} must be a mapping."))
        return {}
    return value


def _validate_keys(
    keys: dict[str, Any],
    keys_base: Path | None,
    issues: list[ValidationIssue],
) -> None:
    for key_name, key_data in keys.items():
        if not isinstance(key_name, str) or not key_name:
            issues.append(ValidationIssue("key names must be non-empty strings."))
            continue
        if not isinstance(key_data, dict):
            issues.append(ValidationIssue(f"keys.{key_name} must be a mapping."))
            continue
        key_file = key_data.get("file")
        if not isinstance(key_file, str) or not key_file:
            issues.append(ValidationIssue(f"keys.{key_name}.file must be a non-empty string."))
            continue
        if keys_base is not None and not (keys_base / key_file).exists():
            issues.append(ValidationIssue(f"keys.{key_name}.file does not exist: {key_file}"))


def _validate_defaults(
    defaults: dict[str, Any],
    keys: dict[str, Any],
    issues: list[ValidationIssue],
) -> None:
    _validate_optional_account_name(defaults.get("connect_user"), "defaults.connect_user", issues)
    _validate_optional_account_name(defaults.get("managed_user"), "defaults.managed_user", issues)
    _validate_optional_port(defaults.get("ssh_port"), "defaults.ssh_port", issues)
    if "disable_password_auth" in defaults and not isinstance(defaults["disable_password_auth"], bool):
        issues.append(ValidationIssue("defaults.disable_password_auth must be a boolean."))
    public_key = defaults.get("public_key")
    if public_key is not None and public_key not in keys:
        issues.append(ValidationIssue(f"defaults.public_key references unknown key: {public_key}"))


def _validate_users(
    users: dict[str, Any],
    keys: dict[str, Any],
    issues: list[ValidationIssue],
) -> None:
    for user_name, user_data in users.items():
        if not isinstance(user_name, str) or not user_name:
            issues.append(ValidationIssue("user names must be non-empty strings."))
            continue
        if not isinstance(user_data, dict):
            issues.append(ValidationIssue(f"users.{user_name} must be a mapping."))
            continue
        username = user_data.get("username")
        if not isinstance(username, str) or not username:
            issues.append(ValidationIssue(f"users.{user_name}.username must be a non-empty string."))
        elif not _valid_account_name(username):
            issues.append(ValidationIssue(f"users.{user_name}.username is not a valid account name: {username}"))
        public_keys = user_data.get("public_keys", [])
        if not isinstance(public_keys, list):
            issues.append(ValidationIssue(f"users.{user_name}.public_keys must be a list."))
            continue
        for key_name in public_keys:
            if key_name == "prompt":
                continue
            if key_name not in keys:
                issues.append(ValidationIssue(f"users.{user_name} references unknown key: {key_name}"))


def _validate_hosts(
    hosts: list[Any],
    users: dict[str, Any],
    issues: list[ValidationIssue],
) -> None:
    seen_hosts: set[str] = set()
    for index, host_data in enumerate(hosts):
        label = f"hosts[{index}]"
        if not isinstance(host_data, dict):
            issues.append(ValidationIssue(f"{label} must be a mapping."))
            continue

        hostname = host_data.get("host")
        if not isinstance(hostname, str) or not hostname:
            issues.append(ValidationIssue(f"{label}.host must be a non-empty string."))
        elif hostname in seen_hosts:
            issues.append(ValidationIssue(f"duplicate host entry: {hostname}"))
        else:
            seen_hosts.add(hostname)

        status = host_data.get("status", DEFAULT_HOST_STATUS)
        if status not in VALID_HOST_STATUSES:
            issues.append(ValidationIssue(f"{label}.status is invalid: {status}"))

        _validate_optional_account_name(host_data.get("connect_user"), f"{label}.connect_user", issues)
        _validate_optional_port(host_data.get("ssh_port"), f"{label}.ssh_port", issues)
        if "disable_password_auth" in host_data and not isinstance(host_data["disable_password_auth"], bool):
            issues.append(ValidationIssue(f"{label}.disable_password_auth must be a boolean."))

        host_users = host_data.get("users", [])
        if not isinstance(host_users, list) or not host_users:
            issues.append(ValidationIssue(f"{label}.users must be a non-empty list."))
            continue
        for user_name in host_users:
            if user_name not in users:
                issues.append(ValidationIssue(f"{label} references unknown user: {user_name}"))


def _default_host_users(defaults: dict[str, Any]) -> list[str]:
    managed_user = defaults.get("managed_user")
    if isinstance(managed_user, str) and managed_user:
        return [managed_user]
    return []


def _valid_account_name(value: str) -> bool:
    return bool(ACCOUNT_NAME_PATTERN.fullmatch(value))


def _validate_optional_account_name(
    value: Any,
    label: str,
    issues: list[ValidationIssue],
) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value:
        issues.append(ValidationIssue(f"{label} must be a non-empty string or null."))
        return
    if not _valid_account_name(value):
        issues.append(ValidationIssue(f"{label} is not a valid account name: {value}"))


def _validate_optional_port(value: Any, label: str, issues: list[ValidationIssue]) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 65535:
        issues.append(ValidationIssue(f"{label} must be an integer between 1 and 65535."))


def _load_json_compatible_yaml(path: Path, original_error: ModuleNotFoundError) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(
            "PyYAML is required to read hand-written YAML config files. Install "
            "the project with `python -m pip install -e .`, or keep the config "
            "in JSON-compatible YAML."
        ) from original_error
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a YAML mapping.")
    return data


def _write_json_compatible_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
