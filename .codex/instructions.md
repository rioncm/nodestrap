# Codex Instructions for Nodestrap

## Repository Orientation

- Treat `docs/README.md` as the current working spec.
- Treat `bootstrap-v1/` as read-only reference material unless the user
  explicitly asks to edit it.
- Do not assume old hard-coded values from `bootstrap-v1/` are acceptable in new
  code.
- Prefer adding new implementation files outside `bootstrap-v1/`.

## Implementation Preferences

- Build Nodestrap as a modern Python package with a console script named
  `nodestrap`.
- Prefer simple, testable modules for config loading, validation, host state,
  command planning, SSH execution, and CLI commands.
- Use structured YAML parsing/writing rather than ad hoc text edits.
- Preserve user config comments only if the chosen YAML library supports it
  cleanly; correctness is more important than comment preservation.
- Keep password and secret material out of logs and persistent files.
- Validate local config before making network or remote changes.
- Validate remote sudoers changes with `visudo -cf` before leaving them in
  place.
- Prefer managing a marked block in `authorized_keys` over replacing the whole
  file.

## Testing and Verification

- Add focused tests for config validation, state transitions, CLI parsing, and
  execution-plan generation as those pieces are implemented.
- Avoid tests that require real SSH hosts by default; isolate SSH behavior
  behind interfaces that can be faked.
- For commands that would touch real hosts, provide dry-run or plan-only paths
  where practical.

## Safety Rules

- Never log passwords, private keys, full secret-bearing commands, or temporary
  secret file contents.
- Avoid writing sudo passwords to disk. If a temporary remote secret file is
  unavoidable, set restrictive permissions and remove it during cleanup.
- Do not disable password SSH access until managed-user key login has been
  verified successfully.
- Surface clear CLI errors when remote success happens but local YAML state
  cannot be updated, so the user can verify and repair manually.
