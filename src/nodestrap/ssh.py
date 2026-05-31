"""SSH command construction for Nodestrap."""

from __future__ import annotations

from dataclasses import dataclass

from nodestrap.plan import HostPlan


@dataclass(frozen=True)
class SshCommand:
    """A command ready for subprocess execution."""

    argv: tuple[str, ...]


def ssh_target(plan: HostPlan, *, user: str | None = None) -> str:
    """Return the SSH target string for a host plan."""

    connect_user = user if user is not None else plan.connect_user
    if connect_user:
        return f"{connect_user}@{plan.host}"
    return plan.host


def build_ssh_command(
    plan: HostPlan,
    remote_command: str,
    *,
    batch_mode: bool = False,
    user: str | None = None,
) -> SshCommand:
    """Build an ssh command without invoking it."""

    argv = ["ssh", "-p", str(plan.ssh_port)]
    if batch_mode:
        argv.extend(["-o", "BatchMode=yes"])
    argv.extend([ssh_target(plan, user=user), remote_command])
    return SshCommand(tuple(argv))


def build_scp_command(
    plan: HostPlan,
    source: str,
    destination: str,
    *,
    user: str | None = None,
) -> SshCommand:
    """Build an scp command without invoking it."""

    argv = [
        "scp",
        "-P",
        str(plan.ssh_port),
        source,
        f"{ssh_target(plan, user=user)}:{destination}",
    ]
    return SshCommand(tuple(argv))


def build_key_login_test_command(plan: HostPlan, username: str) -> SshCommand:
    """Build the key-login check for a managed user."""

    return build_ssh_command(
        plan,
        "true",
        batch_mode=True,
        user=username,
    )


def build_remote_payload_command(plan: HostPlan, *, sudo_password: bool = False) -> SshCommand:
    """Build the command that receives and runs a shell payload over SSH."""

    sudo = "sudo -S -p '' sh -s" if sudo_password else "sudo -n sh -s"
    return build_ssh_command(plan, sudo)


def build_remote_cleanup_command(plan: HostPlan) -> SshCommand:
    """Build a conservative cleanup command for temporary Nodestrap files."""

    return build_ssh_command(plan, "rm -f /tmp/nodestrap-bootstrap.sh /tmp/nodestrap-disable-password.sh")
