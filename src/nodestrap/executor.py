"""Execution orchestration for Nodestrap host plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Protocol

from nodestrap.payload import render_password_disable_payload, render_remote_payload
from nodestrap.plan import HostPlan
from nodestrap.ssh import build_key_login_test_command, build_remote_payload_command


@dataclass(frozen=True)
class CommandResult:
    """Result returned by a command runner."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    """Interface for command execution."""

    def run(self, argv: tuple[str, ...], *, input_text: str | None = None) -> CommandResult:
        """Run a command and return its result."""


class SubprocessRunner:
    """Command runner backed by subprocess."""

    def run(self, argv: tuple[str, ...], *, input_text: str | None = None) -> CommandResult:
        completed = subprocess.run(
            argv,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


@dataclass(frozen=True)
class UserExecutionResult:
    """Result for one managed user on a host."""

    username: str
    key_login_verified: bool
    password_auth_disabled: bool


@dataclass(frozen=True)
class HostExecutionResult:
    """Result for one host plan execution."""

    host: str
    succeeded: bool
    status: str
    message: str
    completed_at: datetime | None
    users: tuple[UserExecutionResult, ...]


def execute_host_plan(
    plan: HostPlan,
    *,
    runner: CommandRunner,
    log_dir: Path | None = None,
    sudo_password: str | None = None,
) -> HostExecutionResult:
    """Execute one host plan with an injected command runner."""

    log_lines = [f"host={plan.host}", f"started_at={_now().isoformat()}"]
    bootstrap = _run_payload(plan, render_remote_payload(plan), runner, sudo_password=sudo_password)
    log_lines.extend(_summarize_result("bootstrap", bootstrap))
    if bootstrap.returncode != 0:
        _write_log(log_dir, plan.host, log_lines)
        return HostExecutionResult(
            host=plan.host,
            succeeded=False,
            status="retry",
            message=_failure_message("bootstrap failed", bootstrap),
            completed_at=None,
            users=(),
        )

    user_results = []
    for user in plan.managed_users:
        login_check = runner.run(build_key_login_test_command(plan, user.username).argv)
        log_lines.extend(_summarize_result(f"key_login:{user.username}", login_check))
        if login_check.returncode != 0:
            _write_log(log_dir, plan.host, log_lines)
            return HostExecutionResult(
                host=plan.host,
                succeeded=False,
                status="retry",
                message=_failure_message(f"key login failed for {user.username}", login_check),
                completed_at=None,
                users=tuple(user_results),
            )

        password_disabled = False
        if plan.disable_password_auth:
            disable = _run_payload(
                plan,
                render_password_disable_payload(user),
                runner,
                sudo_password=sudo_password,
            )
            log_lines.extend(_summarize_result(f"disable_password:{user.username}", disable))
            if disable.returncode != 0:
                _write_log(log_dir, plan.host, log_lines)
                return HostExecutionResult(
                    host=plan.host,
                    succeeded=False,
                    status="retry",
                    message=_failure_message(f"password SSH disable failed for {user.username}", disable),
                    completed_at=None,
                    users=tuple(user_results),
                )
            password_disabled = True

        user_results.append(
            UserExecutionResult(
                username=user.username,
                key_login_verified=True,
                password_auth_disabled=password_disabled,
            )
        )

    completed_at = _now()
    log_lines.append(f"completed_at={completed_at.isoformat()}")
    _write_log(log_dir, plan.host, log_lines)
    return HostExecutionResult(
        host=plan.host,
        succeeded=True,
        status="completed",
        message="completed",
        completed_at=completed_at,
        users=tuple(user_results),
    )


def _run_payload(
    plan: HostPlan,
    payload: str,
    runner: CommandRunner,
    *,
    sudo_password: str | None,
) -> CommandResult:
    command = build_remote_payload_command(plan, sudo_password=sudo_password is not None)
    input_text = payload if sudo_password is None else f"{sudo_password}\n{payload}"
    return runner.run(command.argv, input_text=input_text)


def _summarize_result(label: str, result: CommandResult) -> list[str]:
    lines = [f"{label}.returncode={result.returncode}"]
    if result.stdout:
        lines.append(f"{label}.stdout={_redact(result.stdout).strip()}")
    if result.stderr:
        lines.append(f"{label}.stderr={_redact(result.stderr).strip()}")
    return lines


def _failure_message(prefix: str, result: CommandResult) -> str:
    detail = result.stderr.strip() or result.stdout.strip()
    if not detail:
        return prefix
    return f"{prefix}: {_redact(detail)}"


def _redact(value: str) -> str:
    redacted = []
    for line in value.splitlines():
        if "password" in line.lower():
            redacted.append("[redacted]")
        else:
            redacted.append(line)
    return "\n".join(redacted)


def _write_log(log_dir: Path | None, host: str, lines: list[str]) -> None:
    if log_dir is None:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_host = "".join(char if char.isalnum() or char in ".-" else "_" for char in host)
    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    (log_dir / f"{stamp}-{safe_host}.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _now() -> datetime:
    return datetime.now(timezone.utc)
