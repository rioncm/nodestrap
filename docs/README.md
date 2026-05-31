# Nodestrap bootstrap script v2

Nodestrap is a proposed replacement for the current bootstrap scripts in this
directory.

The existing routine is useful, but it has outgrown the simplicity of a small
set of shell scripts. It currently connects to new hosts, creates or confirms a
target user, installs SSH key access, grants passwordless sudo, checks whether
the new key-based login works, and records failures in logs. The next version
needs to support multiple keys, multiple workstations, repeatable host state,
and safer retries.

## Recommendation

Build Nodestrap as a Python package with a console entry point named
`nodestrap`.

A shell script was a good fit for the original workflow, but the proposed
version needs structured configuration, interactive setup, host state updates,
per-host planning, validation, retries, logging, and careful handling of
temporary secrets. Those requirements are easier to test and maintain in Python
than in Bash.

Recommended shape:

- Python package with a CLI entry point: `nodestrap`
- Subcommands for setup, host management, user management, execution, and retry
- YAML configuration stored at `~/.config/nodestrap/nodestrap.yaml`
- Keys copied into `~/.config/nodestrap/keys/`
- Logs stored in `~/.local/state/nodestrap/logs/`
- Temporary execution plans and password material stored under a secure temp
  directory and removed at the end of a run

Shell should still be used for the remote payload when it is the simplest and
most portable option. The local orchestration, configuration, validation, and
state management should live in Python.

## Current Behavior

The current scripts in this directory do the following:

- Read hosts from `hosts.conf`
- Add or refresh SSH known-host entries
- Prompt once for the target sudo password
- Copy `bootstrap-user.sh` to each host
- Create or update a hard-coded target user
- Install one hard-coded public key
- Write a passwordless sudoers entry
- Check for a remote marker file
- Keep a per-host log only when a host fails

Known limitations:

- Several values are hard-coded, including usernames, paths, public key, marker
  names, and SSH identity paths.
- `run.sh` changes into an unrelated absolute path before reading files.
- `bootstrap-user.sh` and `bootstrap-hosts.sh` use different marker names.
- The current scripts assume one sudo password works for all hosts in a run.
- Host completion is tracked by comments in `hosts.conf` and remote marker
  files, not by structured local state.
- Existing `authorized_keys` content is overwritten instead of appended or
  managed by a recognizable marker block.
- The current process does not clearly distinguish connection user, managed
  user, SSH key, and workstation identity.

## Core Functionality

Nodestrap should:

- Connect to a remote host over SSH using an existing account.
- Confirm that the managed user exists, or create it when needed.
- Install one or more authorized SSH public keys for the managed user.
- Add an `ALL=(ALL) NOPASSWD:ALL` sudoers entry for the managed user.
- Validate sudoers syntax before leaving changes in place.
- Test key-based login for the managed user.
- Disable password SSH access only after key-based login succeeds.
- Log non-sensitive details for each host run.
- Update local host status after each run.

## Configuration

Replace `hosts.conf` with `nodestrap.yaml`.

Suggested structure:

```yaml
defaults:
  connect_user: rion
  managed_user: rion
  public_key: rion_home.pub
  ssh_port: 22
  disable_password_auth: true

keys:
  rion_home:
    file: rion_home.pub
    label: Home workstation
  rion_work:
    file: rion_work.pub
    label: Work workstation
  ansible_work:
    file: ansible_work.pub
    label: Ansible work key

users:
  rion:
    username: rion
    public_keys:
      - rion_home
  ansible:
    username: ansible
    public_keys:
      - ansible_work

hosts:
  - host: host.example.com
    status: completed
    connect_user: rion
    users:
      - rion
    completed_at: 2026-05-31T10:30:00-07:00
    last_error: null

  - host: nodeb.example.com
    status: new
    connect_user: null
    users:
      - rion
    completed_at: null
    last_error: null
```

Notes:

- `users` under each host is a list of named entries from the top-level
  `users` map.
- `public_keys` references names from the top-level `keys` map, not filenames
  directly.
- Use `completed_at` instead of `completed` so the field meaning is explicit.
- Valid host statuses should be `new`, `completed`, `retry`, `failed`, and
  `skipped`.
- Use `null` for unset values instead of empty strings.

## CLI Design

Use subcommands rather than many top-level flags. This will keep behavior clear
as the tool grows.

Recommended commands:

```text
nodestrap setup
nodestrap key add [--name NAME] PATH_TO_PUBLIC_KEY
nodestrap user add NAME [--key KEY_NAME]
nodestrap host add HOST [--user USER] [--connect-user USER] [--run]
nodestrap run [--host HOST] [--status new] [--dry-run]
nodestrap retry [HOST]
nodestrap status
nodestrap validate
```

### `nodestrap setup`

Idempotent interactive setup routine:

- Check dependencies: `ssh`, `scp`, `ssh-keygen`, `ssh-keyscan`, and a supported
  Python runtime.
- Create `~/.config/nodestrap/`.
- Create `~/.config/nodestrap/keys/`.
- Create `~/.local/state/nodestrap/logs/`.
- List each `*.pub` file in `~/.ssh` and ask whether to copy it into
  `nodestrap/keys/`.
- Confirm before overwriting an existing copied key.
- Create `nodestrap.yaml` if it does not exist.
- Ask for the default connection user.
- Ask for the default managed user.
- Ask for the default key from copied keys, or allow no default.

### `nodestrap host add HOST`

Add a new host entry to `nodestrap.yaml`.

Behavior:

- Refuse duplicate host entries unless `--force` is provided.
- Use configured defaults when available.
- Allow `--run` to add the host and run against only that host.
- Set initial status to `new`.

### `nodestrap user add NAME`

Add a managed user definition to the config.

Behavior:

- List existing key names and allow one or more keys to be associated with the
  user.
- Allow `prompt` behavior for cases where the key should be selected at run
  time.
- Preserve existing user definitions unless confirmation is given.

### `nodestrap run`

Run the bootstrap process.

Behavior:

- Validate config before connecting to hosts.
- Request the connection username if it is not configured.
- Request the connection password when password auth is required.
- Keep password material only in memory when possible.
- Select hosts by status, defaulting to `new`.
- Build an execution plan before making changes.
- Confirm ambiguous or missing host settings before execution.
- Execute the core objectives against each selected host.
- Write logs to `~/.local/state/nodestrap/logs/TIMESTAMP-HOST.log`.
- Update host status in `nodestrap.yaml`.
- Report a summary at the end.

### `nodestrap retry`

Run the process against hosts with status `retry`.

Behavior:

- `nodestrap retry` runs all retryable hosts.
- `nodestrap retry HOST` runs one host.
- Failed retry attempts should keep enough error information in `last_error` to
  explain the next action.

## Recommended Additional Functionality

- `nodestrap validate` to check YAML structure, key references, duplicate hosts,
  unknown users, missing key files, and invalid statuses.
- `nodestrap status` to show hosts grouped by status.
- `--dry-run` to print the execution plan without connecting.
- `--limit HOST` or `--host HOST` support for focused runs.
- SSH port support per host.
- Optional `ssh-keyscan` known-host management before connecting.
- Optional backup of remote files before editing:
  - `~/.ssh/authorized_keys`
  - `/etc/sudoers.d/USERNAME`
  - SSH daemon config files
- Use `visudo -cf` to validate sudoers changes.
- Prefer appending or managing a marked block in `authorized_keys` instead of
  overwriting the whole file.
- Record tool version in logs.
- Redact passwords, private key paths when requested, and other sensitive values
  from logs.

## Clarifications Needed

- Should Nodestrap create the managed user if it is missing, or only confirm and
  configure an existing user?
    - yes it should.
- Should it support multiple managed users per host in the first version?
    - lets leave a path to add that feature later
- Should password SSH be disabled globally, per user, or only for the managed
  user when the SSH server supports that distinction?
    - only for the managed user
- Which Linux distributions should be supported initially?
    - debian variants, specifically ubuntu my preferred OS
- Should the tool assume `sudo`, or should it also support direct root login for
  first bootstrap?
    - assume sudo 
- Should the connection password be reused for all hosts in one run, or prompted
  per host?
    - yes, the user can manage which hosts are added for a particular run
- Should host key trust be automatic via `ssh-keyscan`, manual, or configurable?
    - configurable with a default of ignore / don't check
- Should remote marker files still be used, or should local YAML state be the
  source of truth?
    - local yaml state
- What should happen if a host succeeds remotely but updating local YAML fails?
    - a good error for the user on the cli, they cna correct the yaml manually after verification it really succedded
- Should private keys be configured, or should Nodestrap rely on the user's SSH
  agent and normal SSH config?
    - outside of scope at this time

## First Version Scope

Recommended first implementation:

- Python package and `nodestrap` console command
- `setup`, `host add`, `user add`, `run`, `retry`, `status`, and `validate`
- One config file at `~/.config/nodestrap/nodestrap.yaml`
- Public keys copied into `~/.config/nodestrap/keys/`
- One or more managed users per host, but no roles beyond sudo access yet
- Debian/Ubuntu-compatible remote commands first
- No passwordless sudo or SSH password disablement until key login has been
  tested successfully

Defer until later:

- Non-Debian Linux support
- Rich inventory import/export
- Parallel host execution
- Plugin architecture
- Non-SSH transports
