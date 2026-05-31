"""Command-line interface for Nodestrap."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from nodestrap import __version__
from nodestrap.config import (
    ConfigError,
    add_host,
    add_user,
    empty_config,
    hosts_by_status,
    load_config,
    selected_hosts,
    validate_config,
    write_config,
)
from nodestrap.paths import config_path, logs_dir
from nodestrap.plan import build_host_plans


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nodestrap")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        type=Path,
        default=config_path(),
        help="Path to nodestrap.yaml.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser("setup", help="Create Nodestrap config and state directories.")
    setup.set_defaults(func=cmd_setup)

    key = subparsers.add_parser("key", help="Manage public keys.")
    key_subparsers = key.add_subparsers(dest="key_command", required=True)
    key_add = key_subparsers.add_parser("add", help="Copy a public key into Nodestrap config.")
    key_add.add_argument("path", type=Path)
    key_add.add_argument("--name")
    key_add.set_defaults(func=cmd_key_add)

    user = subparsers.add_parser("user", help="Manage user definitions.")
    user_subparsers = user.add_subparsers(dest="user_command", required=True)
    user_add = user_subparsers.add_parser("add", help="Add a managed user definition.")
    user_add.add_argument("name")
    user_add.add_argument("--username")
    user_add.add_argument("--key", action="append", dest="keys", default=[])
    user_add.add_argument("--force", action="store_true")
    user_add.set_defaults(func=cmd_user_add)

    host = subparsers.add_parser("host", help="Manage hosts.")
    host_subparsers = host.add_subparsers(dest="host_command", required=True)
    host_add = host_subparsers.add_parser("add", help="Add a host.")
    host_add.add_argument("host")
    host_add.add_argument("--user", action="append", dest="users")
    host_add.add_argument("--connect-user")
    host_add.add_argument("--force", action="store_true")
    host_add.add_argument("--run", action="store_true")
    host_add.set_defaults(func=cmd_host_add)

    run = subparsers.add_parser("run", help="Run bootstrap against selected hosts.")
    run.add_argument("--host")
    run.add_argument("--status", default="new")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(func=cmd_run)

    retry = subparsers.add_parser("retry", help="Run hosts with retry status.")
    retry.add_argument("host", nargs="?")
    retry.add_argument("--dry-run", action="store_true")
    retry.set_defaults(func=cmd_retry)

    status = subparsers.add_parser("status", help="Show hosts grouped by status.")
    status.set_defaults(func=cmd_status)

    validate = subparsers.add_parser("validate", help="Validate nodestrap.yaml.")
    validate.set_defaults(func=cmd_validate)

    return parser


def cmd_setup(args: argparse.Namespace) -> int:
    args.config.parent.mkdir(parents=True, exist_ok=True)
    config_keys_dir = args.config.parent / "keys"
    config_keys_dir.mkdir(parents=True, exist_ok=True)
    log_dir = logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    if not args.config.exists():
        write_config(args.config, empty_config())
        print(f"created {args.config}")
    else:
        print(f"exists {args.config}")
    print(f"created {config_keys_dir}")
    print(f"created {log_dir}")
    return 0


def cmd_key_add(args: argparse.Namespace) -> int:
    data = _load_or_empty(args.config)
    source = args.path
    if not source.exists():
        raise ConfigError(f"Public key not found: {source}")
    name = args.name or source.stem
    destination_dir = args.config.parent / "keys"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    shutil.copyfile(source, destination)
    data.setdefault("keys", {})[name] = {
        "file": source.name,
        "label": name.replace("_", " "),
    }
    write_config(args.config, data)
    print(f"added key {name}: {destination}")
    return 0


def cmd_user_add(args: argparse.Namespace) -> int:
    data = _load_or_empty(args.config)
    add_user(
        data,
        args.name,
        username=args.username,
        public_keys=args.keys,
        force=args.force,
    )
    write_config(args.config, data)
    print(f"added user {args.name}")
    return 0


def cmd_host_add(args: argparse.Namespace) -> int:
    data = _load_or_empty(args.config)
    add_host(
        data,
        args.host,
        users=args.users,
        connect_user=args.connect_user,
        force=args.force,
    )
    write_config(args.config, data)
    print(f"added host {args.host}")
    if args.run:
        return _run(args.config, host=args.host, status="new", dry_run=True)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("error: remote execution is not implemented yet; use --dry-run", file=sys.stderr)
        return 2
    return _run(args.config, host=args.host, status=args.status, dry_run=args.dry_run)


def cmd_retry(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("error: remote execution is not implemented yet; use --dry-run", file=sys.stderr)
        return 2
    return _run(args.config, host=args.host, status="retry", dry_run=args.dry_run)


def cmd_status(args: argparse.Namespace) -> int:
    data = load_config(args.config)
    for status, hosts in hosts_by_status(data).items():
        print(f"{status}: {len(hosts)}")
        for hostname in hosts:
            print(f"  {hostname}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    data = load_config(args.config)
    issues = validate_config(data, keys_base=args.config.parent / "keys")
    if issues:
        for issue in issues:
            print(f"error: {issue.message}", file=sys.stderr)
        return 1
    print("config valid")
    return 0


def _run(config: Path, *, host: str | None, status: str, dry_run: bool) -> int:
    data = load_config(config)
    issues = validate_config(data, keys_base=config.parent / "keys")
    if issues:
        for issue in issues:
            print(f"error: {issue.message}", file=sys.stderr)
        return 1

    selected = selected_hosts(data, host=host, status=status)
    plans = build_host_plans(selected, data.get("defaults"))
    if dry_run:
        print(f"dry run: {len(plans)} host(s) selected")
        for plan in plans:
            users = ", ".join(plan.users)
            print(
                f"- {plan.host} "
                f"connect_user={plan.connect_user or '<unset>'} "
                f"users={users or '<unset>'} "
                f"port={plan.ssh_port} "
                f"disable_password_auth={str(plan.disable_password_auth).lower()}"
            )
    return 0


def _load_or_empty(path: Path) -> dict:
    if path.exists():
        return load_config(path)
    return empty_config()


if __name__ == "__main__":
    raise SystemExit(main())
