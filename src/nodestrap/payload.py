"""Remote shell payload rendering for Nodestrap."""

from __future__ import annotations

import shlex

from nodestrap.plan import HostPlan, ManagedUserPlan

AUTHORIZED_KEYS_BEGIN = "# BEGIN managed by nodestrap"
AUTHORIZED_KEYS_END = "# END managed by nodestrap"


def render_remote_payload(plan: HostPlan) -> str:
    """Render the pre-verification Debian/Ubuntu bootstrap shell payload."""

    lines = [
        "#!/bin/sh",
        "set -eu",
        "",
    ]
    for user in plan.managed_users:
        lines.extend(_render_user(user))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_password_disable_payload(user: ManagedUserPlan) -> str:
    """Render the post-key-verification payload for disabling password SSH."""

    username = shlex.quote(user.username)
    sshd_dropin = shlex.quote(f"/etc/ssh/sshd_config.d/90-nodestrap-{user.username}.conf")
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            "if [ -d /etc/ssh/sshd_config.d ]; then",
            "  tmp_sshd=$(mktemp)",
            f"  printf 'Match User %s\\n    PasswordAuthentication no\\n' {username} > \"$tmp_sshd\"",
            f"  install -m 644 \"$tmp_sshd\" {sshd_dropin}",
            f"  if ! sshd -t; then rm -f {sshd_dropin} \"$tmp_sshd\"; exit 1; fi",
            "  rm -f \"$tmp_sshd\"",
            "fi",
            "",
        ]
    )


def describe_plan_steps(plan: HostPlan) -> list[str]:
    """Describe remote actions without exposing secret material."""

    steps = []
    for user in plan.managed_users:
        steps.extend(
            [
                f"ensure user {user.username} exists",
                f"install {len(user.public_keys)} public key(s) for {user.username}",
                f"grant passwordless sudo to {user.username} after visudo validation",
                f"test key-based login for {user.username}",
            ]
        )
        if plan.disable_password_auth:
            steps.append(f"disable password SSH for {user.username} after key login succeeds")
    return steps


def _render_user(user: ManagedUserPlan) -> list[str]:
    username = shlex.quote(user.username)
    sudoers_path = shlex.quote(f"/etc/sudoers.d/{user.username}")
    home_ssh = shlex.quote(f"/home/{user.username}/.ssh")
    auth_keys_path = shlex.quote(f"/home/{user.username}/.ssh/authorized_keys")
    authorized_keys = "\n".join(key.value for key in user.public_keys)
    marked_keys = f"{AUTHORIZED_KEYS_BEGIN}\n{authorized_keys}\n{AUTHORIZED_KEYS_END}"

    lines = [
        f"if ! id -u {username} >/dev/null 2>&1; then",
        f"  adduser --disabled-password --gecos '' {username}",
        "fi",
        f"usermod -aG sudo {username}",
        f"install -d -m 700 -o {username} -g {username} {home_ssh}",
        f"auth_keys={auth_keys_path}",
        "tmp_auth_keys=$(mktemp)",
        "touch \"$auth_keys\"",
        "awk '",
        f"  $0 == {shlex.quote(AUTHORIZED_KEYS_BEGIN)} {{ skip = 1; next }}",
        f"  $0 == {shlex.quote(AUTHORIZED_KEYS_END)} {{ skip = 0; next }}",
        "  skip != 1 { print }",
        "' \"$auth_keys\" > \"$tmp_auth_keys\"",
        f"cat >> \"$tmp_auth_keys\" <<'NODESTRAP_KEYS_{user.name}'",
        marked_keys,
        f"NODESTRAP_KEYS_{user.name}",
        "install -m 600 -o " + username + " -g " + username + " \"$tmp_auth_keys\" \"$auth_keys\"",
        "rm -f \"$tmp_auth_keys\"",
        f"tmp_sudoers=$(mktemp)",
        f"printf '%s ALL=(ALL) NOPASSWD:ALL\\n' {username} > \"$tmp_sudoers\"",
        "visudo -cf \"$tmp_sudoers\"",
        f"install -m 440 \"$tmp_sudoers\" {sudoers_path}",
        "rm -f \"$tmp_sudoers\"",
    ]
    return lines
