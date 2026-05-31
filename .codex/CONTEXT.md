# Nodestrap Project Context

Nodestrap is a fresh Python project intended to replace the old host bootstrap
shell scripts in `bootstrap-v1/`.

## Current Project State

- This repository is newly initialized and currently contains planning docs plus
  the old implementation for reference.
- `docs/README.md` is the working product/design document for Nodestrap v2.
  Treat it as the source of truth for expected behavior until a root `README.md`
  exists.
- `docs/packaging_goals.md` records the packaging goal: after a successful v1,
  publish to PyPI through GitHub automations.
- `bootstrap-v1/` contains the previous shell-based codebase. It is reference
  material only and is intentionally ignored by git.

## Product Direction

Nodestrap should become a Python package with a console command named
`nodestrap`.

The intended first version includes:

- A package/CLI entry point named `nodestrap`.
- Subcommands: `setup`, `key add`, `user add`, `host add`, `run`, `retry`,
  `status`, and `validate`.
- YAML configuration at `~/.config/nodestrap/nodestrap.yaml`.
- Public keys copied into `~/.config/nodestrap/keys/`.
- Logs written under `~/.local/state/nodestrap/logs/`.
- Debian/Ubuntu-compatible remote bootstrap behavior first.
- Local YAML as the source of truth for host status.

## Important Requirements

- Use Python for local orchestration, configuration, validation, state updates,
  retries, and logging.
- Use shell only for the remote payload when it is the simplest portable option.
- Support one or more public keys per managed user.
- Leave a clear path to multiple managed users per host, even if early
  implementation keeps behavior simple.
- Create the managed user when missing.
- Assume the connection path uses `sudo`; direct root bootstrap is out of scope.
- Disable password SSH access only for the managed user, and only after
  key-based login succeeds.
- Rely on the user's normal SSH configuration and SSH agent for private keys;
  private-key configuration is out of scope for now.
- Host key trust should be configurable, defaulting to ignore/no automatic
  known-host checks.

## Reference Implementation Notes

The old scripts in `bootstrap-v1/`:

- Read hosts from `hosts.conf`.
- Prompt once for a target sudo password.
- Copy and run `bootstrap-user.sh` on each host.
- Create/update a hard-coded `rion` user.
- Install one hard-coded public key.
- Grant passwordless sudo.
- Check remote marker files.
- Log failed host runs.

Known old-script limitations to avoid carrying forward:

- Hard-coded usernames, paths, public keys, marker names, and SSH identity
  paths.
- `run.sh` changes into an unrelated absolute path before reading files.
- Marker names differ between scripts.
- Existing `authorized_keys` is overwritten instead of safely appended or
  managed with a marked block.
- Host completion is tracked through comments and remote marker files rather
  than structured local state.
- Connection user, managed user, SSH key, and workstation identity are not
  clearly separated.
