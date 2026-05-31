"""Local host-state updates for Nodestrap config data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from nodestrap.config import ConfigError


def mark_host_completed(
    data: dict[str, Any],
    hostname: str,
    *,
    completed_at: datetime,
) -> dict[str, Any]:
    """Mark a host completed after remote work succeeds."""

    host = _find_host(data, hostname)
    host["status"] = "completed"
    host["completed_at"] = completed_at.isoformat()
    host["last_error"] = None
    return data


def mark_host_failed(
    data: dict[str, Any],
    hostname: str,
    *,
    error: str,
    retryable: bool = True,
) -> dict[str, Any]:
    """Mark a host failed or retryable with a non-sensitive error summary."""

    host = _find_host(data, hostname)
    host["status"] = "retry" if retryable else "failed"
    host["completed_at"] = None
    host["last_error"] = error
    return data


def _find_host(data: dict[str, Any], hostname: str) -> dict[str, Any]:
    hosts = data.get("hosts", [])
    if not isinstance(hosts, list):
        raise ConfigError("hosts must be a list before updating host state.")
    for host in hosts:
        if isinstance(host, dict) and host.get("host") == hostname:
            return host
    raise ConfigError(f"Host not found: {hostname}")

