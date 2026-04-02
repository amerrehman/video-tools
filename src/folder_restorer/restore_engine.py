from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from dataclasses import dataclass


DESKTOP_INI_TRIGGERS = (
    "iconresource=",
    "iconfile=",
    "iconindex=",
    "clsid=",
    "localizedresourcename=",
    "infotip=",
    "iconarea_image=",
    "[.shellclassinfo]",
)


@dataclass
class Stats:
    scanned_folders: int = 0
    desktop_ini_found: int = 0
    desktop_ini_removed: int = 0
    attrib_ok: int = 0
    errors: int = 0


def is_running_as_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(root: str, *, dry_run: bool, no_gui: bool) -> bool:
    params = []
    if root:
        params.append(root)
    if dry_run:
        params.append("--dry-run")
    if no_gui:
        params.append("--no-gui")

    executable = sys.executable
    if getattr(sys, "frozen", False):
        parameter_line = subprocess.list2cmdline(params)
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        launcher_path = os.path.join(project_root, "icon_restore.py")
        parameter_line = subprocess.list2cmdline([launcher_path, *params])

    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            parameter_line,
            None,
            1,
        )
        return result > 32
    except Exception:
        return False


def run_attrib(path: str, *, clear_system_hidden_readonly: bool, dry_run: bool) -> bool:
    args = ["-r", path]
    if clear_system_hidden_readonly:
        args = ["-s", "-h", "-r", path]

    if dry_run:
        print(f"[dry-run] attrib {' '.join(args)}")
        return True

    try:
        cp = subprocess.run(["attrib", *args], capture_output=True, text=True, shell=False)
        if cp.returncode == 0:
            return True
        cp2 = subprocess.run(["cmd", "/c", "attrib", *args], capture_output=True, text=True, shell=False)
        return cp2.returncode == 0
    except Exception:
        return False


def desktop_ini_looks_like_customization(desktop_ini_path: str) -> bool:
    try:
        with open(desktop_ini_path, "r", encoding="utf-8", errors="ignore") as file_obj:
            text = file_obj.read().lower()
        return any(key in text for key in DESKTOP_INI_TRIGGERS)
    except Exception:
        return True


def remove_desktop_ini(folder_path: str, desktop_ini_path: str, *, dry_run: bool, stats: Stats) -> None:
    stats.desktop_ini_found += 1
    if not desktop_ini_looks_like_customization(desktop_ini_path):
        return

    if run_attrib(desktop_ini_path, clear_system_hidden_readonly=True, dry_run=dry_run):
        stats.attrib_ok += 1

    if dry_run:
        print(f"[dry-run] delete: {desktop_ini_path}")
        deleted = True
    else:
        try:
            os.remove(desktop_ini_path)
            deleted = True
        except Exception:
            deleted = False

    if deleted:
        stats.desktop_ini_removed += 1
    else:
        stats.errors += 1
        print(f"[warn] Could not delete: {desktop_ini_path}")

    if run_attrib(folder_path, clear_system_hidden_readonly=True, dry_run=dry_run):
        stats.attrib_ok += 1


def should_skip_dir(entry_name: str) -> bool:
    lowered = entry_name.lower()
    if entry_name.startswith("."):
        return True
    if lowered in {"$recycle.bin", "system volume information"}:
        return True
    return False


def process_tree_recursive(folder_path: str, *, dry_run: bool, stats: Stats) -> None:
    stats.scanned_folders += 1

    desktop_ini_path = os.path.join(folder_path, "desktop.ini")
    if os.path.isfile(desktop_ini_path):
        remove_desktop_ini(folder_path, desktop_ini_path, dry_run=dry_run, stats=stats)

    try:
        with os.scandir(folder_path) as entries:
            for entry in entries:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if entry.is_symlink():
                    continue
                if should_skip_dir(entry.name):
                    continue
                process_tree_recursive(entry.path, dry_run=dry_run, stats=stats)
    except PermissionError:
        stats.errors += 1
        print(f"[warn] Permission denied: {folder_path}")
    except FileNotFoundError:
        return
    except Exception as exc:
        stats.errors += 1
        print(f"[warn] Error scanning {folder_path}: {exc}")


def refresh_explorer_icons(root: str | None = None, *, dry_run: bool) -> None:
    if dry_run:
        print("[dry-run] shell refresh (SHChangeNotify)")
        return

    try:
        shcne_assocchanged = 0x08000000
        shcne_updatedir = 0x00001000
        shcnf_pathw = 0x0005
        shcnf_idlist = 0x0000
        ctypes.windll.shell32.SHChangeNotify(shcne_assocchanged, shcnf_idlist, None, None)
        if root:
            ctypes.windll.shell32.SHChangeNotify(shcne_updatedir, shcnf_pathw, root, None)
    except Exception:
        pass


def restart_explorer(*, dry_run: bool) -> bool:
    if dry_run:
        print("[dry-run] restart explorer.exe")
        return True

    try:
        subprocess.run(
            ["taskkill", "/f", "/im", "explorer.exe"],
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        time.sleep(0.75)
        subprocess.Popen(["explorer.exe"], shell=False)
        return True
    except Exception:
        return False
