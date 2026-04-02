import json
import os


def get_settings_file_path() -> str:
    return os.path.join("configs", "version_settings.json")


def load_settings(settings_file_path: str | None = None) -> dict:
    settings_file_path = settings_file_path or get_settings_file_path()
    if os.path.exists(settings_file_path):
        with open(settings_file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    return {
        "version": "1.00.00",
        "release_notes": "Initial release",
    }


def save_settings(settings: dict, settings_file_path: str | None = None) -> None:
    settings_file_path = settings_file_path or get_settings_file_path()
    os.makedirs(os.path.dirname(settings_file_path) or ".", exist_ok=True)
    with open(settings_file_path, "w", encoding="utf-8") as file:
        json.dump(settings, file, indent=4)


def _parse_version(version_str: str) -> tuple[int, int, int]:
    parts = str(version_str).strip().split(".")
    while len(parts) < 3:
        parts.append("0")
    parts = parts[:3]
    try:
        major = int(parts[0])
    except ValueError:
        major = 1
    try:
        minor = int(parts[1])
    except ValueError:
        minor = 0
    try:
        patch = int(parts[2])
    except ValueError:
        patch = 0
    return major, minor, patch


def format_version(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor:02d}.{patch:02d}"


def increment_version(settings: dict) -> dict:
    major, minor, patch = _parse_version(settings.get("version", "1.00.00"))
    patch += 1
    if patch >= 100:
        patch = 0
        minor += 1
    if minor >= 100:
        minor = 0
        major += 1
    new_version = format_version(major, minor, patch)
    settings["version"] = new_version
    settings["release_notes"] = f"Version {new_version}:\n- Your release notes here"
    return settings
