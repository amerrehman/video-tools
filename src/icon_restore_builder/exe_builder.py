import glob
import json
import os
import shutil
import stat
import subprocess
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Optional

import PyInstaller.__main__

from .deployment_settings import (
    DEFAULT_GITHUB_RELEASE_DIR,
    DEFAULT_GITHUB_TOKEN_ENV_VAR,
    DEFAULT_GITHUB_UPDATES_BRANCH,
    DEFAULT_GITHUB_UPDATES_REPO,
    DEFAULT_RELEASE_DOWNLOAD_BASE_URL,
)
from .version import increment_version, load_settings, save_settings


class ExeBuilder:
    def __init__(self, project_dir: str, spec_filename: str = "icon_restore.spec"):
        self.project_dir = os.path.abspath(project_dir)
        self.spec_file = os.path.join(self.project_dir, spec_filename)
        self.build_path = os.path.join(self.project_dir, "build")
        self.dist_path = os.path.join(self.project_dir, "dist")
        self.config_path = os.path.join(self.project_dir, "configs", "exe_builder_config.json")
        self.release_root = self._resolve_release_root()
        self.version_settings_path = os.path.join(self.project_dir, "configs", "version_settings.json")

        if not os.path.exists(self.spec_file):
            raise FileNotFoundError(f"Spec file not found: {self.spec_file}")

    def _resolve_release_root(self) -> str:
        preferred_root = os.path.normpath(r"C:\Users\Amer\Documents\Video Tools Build\Icon Restore")
        project_norm = os.path.normcase(os.path.normpath(self.project_dir))
        onedrive_norm = os.path.normcase(os.path.normpath(r"C:\Users\Amer\OneDrive"))

        if project_norm.startswith(onedrive_norm):
            os.makedirs(preferred_root, exist_ok=True)
            return preferred_root

        fallback = os.path.join(self.dist_path, DEFAULT_GITHUB_RELEASE_DIR)
        os.makedirs(fallback, exist_ok=True)
        return fallback

    def _load_builder_config(self) -> dict:
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _github_token(self) -> str:
        token_path = os.path.join(self.project_dir, "github_token.txt")
        if os.path.exists(token_path):
            try:
                with open(token_path, "r", encoding="utf-8") as file:
                    token = file.read().strip()
                if token:
                    return token
            except OSError:
                pass
        return str(os.environ.get(DEFAULT_GITHUB_TOKEN_ENV_VAR, "") or "").strip()

    @staticmethod
    def _remove_readonly(func, path, _):
        try:
            os.chmod(path, stat.S_IWRITE)
        except Exception:
            pass
        func(path)

    def safe_rmtree(self, path: str, retries: int = 5, delay: float = 1.0) -> None:
        for index in range(retries):
            try:
                if os.path.exists(path):
                    shutil.rmtree(path, onerror=self._remove_readonly)
                return
            except PermissionError:
                print(f"[Cleanup] PermissionError deleting {path}, retrying ({index + 1}/{retries})...")
                time.sleep(delay)

    def remove_path(self, path: str, retries: int = 5, delay: float = 1.0) -> None:
        if not os.path.exists(path):
            return
        if os.path.isdir(path):
            self.safe_rmtree(path, retries=retries, delay=delay)
            return
        for index in range(retries):
            try:
                os.chmod(path, stat.S_IWRITE)
            except Exception:
                pass
            try:
                os.remove(path)
                return
            except PermissionError:
                print(f"[Cleanup] PermissionError deleting file {path}, retrying ({index + 1}/{retries})...")
                time.sleep(delay)
            except FileNotFoundError:
                return

    def _try_taskkill(self, exe_name: str) -> None:
        try:
            subprocess.run(["taskkill", "/IM", exe_name, "/F", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, shell=False)
        except Exception:
            pass

    def _preclear_dist_exes(self, retries: int = 5, delay: float = 0.8) -> None:
        if not os.path.isdir(self.dist_path):
            return
        exe_paths = glob.glob(os.path.join(self.dist_path, "*.exe"))
        for path in exe_paths:
            self._try_taskkill(os.path.basename(path))
            for _index in range(retries):
                try:
                    if os.path.exists(path):
                        os.chmod(path, stat.S_IWRITE)
                        os.remove(path)
                    break
                except PermissionError:
                    time.sleep(delay)

    def clean_build_only(self) -> None:
        self.safe_rmtree(self.build_path)

    def clean_dist_only(self) -> None:
        self.safe_rmtree(self.dist_path)

    def clean_pycache(self) -> None:
        for root, dirs, _files in os.walk(self.project_dir):
            for directory in dirs:
                if directory == "__pycache__":
                    self.safe_rmtree(os.path.join(root, directory))

    def build(self, spec_file: str, extra_pyinstaller_args: Optional[list] = None) -> None:
        args = ["--clean"]
        if extra_pyinstaller_args:
            args.extend(extra_pyinstaller_args)
        args.append(spec_file)
        PyInstaller.__main__.run(args)

    def _find_built_exe(self) -> Optional[str]:
        if not os.path.isdir(self.dist_path):
            return None
        exe_paths = sorted(Path(self.dist_path).glob("*.exe"))
        if not exe_paths:
            return None
        return str(exe_paths[0])

    def _versioned_release_dir(self, version: str) -> str:
        return os.path.join(self.release_root, DEFAULT_GITHUB_RELEASE_DIR, version)

    def _write_manifest(self, version: str, built_exe_name: str, release_notes: str) -> str:
        manifest = {
            "version": version,
            "release_notes": release_notes,
            "repo": DEFAULT_GITHUB_UPDATES_REPO,
            "branch": DEFAULT_GITHUB_UPDATES_BRANCH,
            "downloads": {
                "exe_name": built_exe_name,
                "relative_path": f"{DEFAULT_GITHUB_RELEASE_DIR}/{version}/{built_exe_name}",
                "download_url": f"{DEFAULT_RELEASE_DOWNLOAD_BASE_URL}/{version}/{built_exe_name.replace(' ', '%20')}",
            },
        }
        manifest_path = os.path.join(self.project_dir, "dist", "latest.json")
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as file:
            json.dump(manifest, file, indent=2)
        return manifest_path

    def _publish_release_copy(self, built_exe: str, version: str) -> str:
        release_dir = self._versioned_release_dir(version)
        os.makedirs(release_dir, exist_ok=True)
        destination = os.path.join(release_dir, os.path.basename(built_exe))
        self.remove_path(destination)
        shutil.copy2(built_exe, destination)
        return destination

    def _prepare_version(self) -> dict:
        settings = load_settings(self.version_settings_path)
        config = self._load_builder_config()
        mode = str(config.get("versioning", {}).get("mode", "ask") or "ask").strip().lower()
        custom_version = str(config.get("versioning", {}).get("custom_version", "") or "").strip()

        if mode == "increment":
            settings = increment_version(settings)
        elif mode == "custom" and custom_version:
            settings["version"] = custom_version
            settings["release_notes"] = f"Version {custom_version}:\n- Your release notes here"
        elif mode == "ask":
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                should_increment = bool(messagebox.askyesno("Icon Restore Build", f"Current version is {settings.get('version', '1.00.00')}. Increment before building?", parent=root))
            finally:
                root.destroy()
            if should_increment:
                settings = increment_version(settings)

        save_settings(settings, self.version_settings_path)
        return settings

    def confirm_build(self) -> bool:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            return bool(messagebox.askyesno("Icon Restore Build", "Build a fresh versioned Icon Restore executable?", parent=root))
        finally:
            root.destroy()

    def show_build_complete(self, built_exe: str, release_copy: str, manifest_path: str, version: str) -> None:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            messagebox.showinfo(
                "Icon Restore Build",
                f"Build complete.\n\nVersion: {version}\n\ndist EXE:\n{built_exe}\n\nRelease copy:\n{release_copy}\n\nManifest:\n{manifest_path}\n\nGitHub token detected: {'yes' if self._github_token() else 'no'}",
                parent=root,
            )
        finally:
            root.destroy()

    def run(self, extra_pyinstaller_args: Optional[list] = None) -> None:
        if not self.confirm_build():
            print("[Build] Cancelled by user.")
            return

        version_settings = self._prepare_version()
        version = str(version_settings.get("version", "1.00.00"))
        release_notes = str(version_settings.get("release_notes", "") or "")

        self.clean_build_only()
        self.clean_dist_only()
        self.clean_pycache()
        self._preclear_dist_exes()
        self.build(self.spec_file, extra_pyinstaller_args=extra_pyinstaller_args)

        built_exe = self._find_built_exe()
        if not built_exe:
            raise FileNotFoundError(f"Built EXE not found in dist: {self.dist_path}")

        release_copy = self._publish_release_copy(built_exe, version)
        manifest_path = self._write_manifest(version, os.path.basename(built_exe), release_notes)
        self.show_build_complete(built_exe, release_copy, manifest_path, version)


def main(project_dir: str | None = None) -> int:
    builder = ExeBuilder(
        project_dir=project_dir or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        spec_filename="icon_restore.spec",
    )
    builder.run(extra_pyinstaller_args=["--noconfirm"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
