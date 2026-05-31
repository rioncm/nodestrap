"""Execution-plan generation for Nodestrap runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PublicKeyPlan:
    """Public key material that will be installed for a managed user."""

    name: str
    file: str
    value: str


@dataclass(frozen=True)
class ManagedUserPlan:
    """Planned user state for one host."""

    name: str
    username: str
    public_keys: tuple[PublicKeyPlan, ...]


@dataclass(frozen=True)
class HostPlan:
    """Planned work for one host."""

    host: str
    connect_user: str | None
    users: tuple[str, ...]
    managed_users: tuple[ManagedUserPlan, ...]
    ssh_port: int
    disable_password_auth: bool


def build_host_plans(
    hosts: list[dict[str, Any]],
    defaults: dict[str, Any] | None = None,
    *,
    config: dict[str, Any] | None = None,
    keys_base: Path | None = None,
) -> list[HostPlan]:
    """Build deterministic host plans from selected config entries."""

    defaults = defaults or {}
    plans: list[HostPlan] = []
    for host in hosts:
        users = host.get("users", [])
        ssh_port = host.get("ssh_port", defaults.get("ssh_port", 22))
        disable_password_auth = host.get(
            "disable_password_auth",
            defaults.get("disable_password_auth", True),
        )
        plans.append(
            HostPlan(
                host=host["host"],
                connect_user=host.get("connect_user") or defaults.get("connect_user"),
                users=tuple(users),
                managed_users=_managed_user_plans(tuple(users), config, keys_base),
                ssh_port=int(ssh_port),
                disable_password_auth=bool(disable_password_auth),
            )
        )
    return plans


def _managed_user_plans(
    user_names: tuple[str, ...],
    config: dict[str, Any] | None,
    keys_base: Path | None,
) -> tuple[ManagedUserPlan, ...]:
    if not config:
        return ()

    users = config.get("users", {})
    keys = config.get("keys", {})
    if not isinstance(users, dict) or not isinstance(keys, dict):
        return ()

    plans = []
    for name in user_names:
        user_data = users.get(name, {})
        if not isinstance(user_data, dict):
            continue
        username = user_data.get("username", name)
        key_plans = []
        for key_name in user_data.get("public_keys", []):
            if key_name == "prompt":
                continue
            key_data = keys.get(key_name, {})
            if not isinstance(key_data, dict):
                continue
            key_file = key_data.get("file")
            if not isinstance(key_file, str):
                continue
            key_plans.append(
                PublicKeyPlan(
                    name=key_name,
                    file=key_file,
                    value=_read_key(keys_base, key_file),
                )
            )
        plans.append(
            ManagedUserPlan(
                name=name,
                username=str(username),
                public_keys=tuple(key_plans),
            )
        )
    return tuple(plans)


def _read_key(keys_base: Path | None, key_file: str) -> str:
    if keys_base is None:
        return ""
    return (keys_base / key_file).read_text(encoding="utf-8").strip()
