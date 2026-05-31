"""Execution-plan generation for Nodestrap runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HostPlan:
    """Planned work for one host."""

    host: str
    connect_user: str | None
    users: tuple[str, ...]
    ssh_port: int
    disable_password_auth: bool


def build_host_plans(hosts: list[dict[str, Any]], defaults: dict[str, Any] | None = None) -> list[HostPlan]:
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
                ssh_port=int(ssh_port),
                disable_password_auth=bool(disable_password_auth),
            )
        )
    return plans

