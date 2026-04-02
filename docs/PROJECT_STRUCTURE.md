# Project Structure

This workspace mirrors the cleaned-up Kingfisher-style layout while keeping Icon Restore as the application that lives inside it.

## Main areas

- `src/folder_restorer/`
  Main Icon Restore application code.
- `src/icon_restore_builder/`
  Build, version, and publish helpers for the project.
- `tools/`
  Secondary Python entrypoints for builder-related helpers.
- `scripts/`
  PowerShell helpers for backups and environment setup.
- `docs/`
  Human-facing documentation and release notes.
- `Images/`
  Shared visual assets and application icons.
- `configs/`
  Versioning and builder configuration.

## Root entrypoints

These root files are intentionally small wrappers or primary entrypoints:

- `icon_restore.py`
- `exe_builder.py`

## Canonical utility entrypoints

- `tools/builder_control_panel.py`
- `scripts/daily_backupper.ps1`
- `scripts/github_publish_token.ps1`
- `scripts/backup_planned_changes.ps1`

## Build assets

- `icon_restore.spec`

## Runtime-generated folders

These are operational folders and should not be treated as source:

- `build/`
- `dist/`
- `Daily Backups/`
