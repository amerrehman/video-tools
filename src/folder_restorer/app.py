from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

import customtkinter as ctk
import tkinter.messagebox as messagebox

from folder_restorer.restore_engine import (
    Stats,
    process_tree_recursive,
    refresh_explorer_icons,
    relaunch_as_admin,
    restart_explorer,
)
from folder_restorer.theme import THEME, configure_customtkinter


def is_cli_mode(args: argparse.Namespace) -> bool:
    return bool(args.no_gui or args.root)


def show_error(message: str, *, cli_mode: bool) -> None:
    if cli_mode:
        print(f"[error] {message}")
        return
    messagebox.showerror("Folder Restorer", message)


def show_info(message: str, *, cli_mode: bool) -> None:
    if cli_mode:
        print(message)
        return
    messagebox.showinfo("Folder Restorer", message)


def get_app_icon_path() -> str:
    project_root = Path(__file__).resolve().parents[2]
    return str(project_root / "restore.ico")


class FolderPickerDialog(ctk.CTk):
    def __init__(self, initial: Optional[str] = None):
        super().__init__()
        configure_customtkinter()
        self.selected_path: Optional[str] = None
        self.path_var = ctk.StringVar(value=os.path.abspath(initial or os.getcwd()))

        self.title("Folder Restorer")
        self.geometry("720x340")
        self.resizable(False, False)
        self.configure(fg_color=THEME["window_bg"])
        try:
            self.iconbitmap(get_app_icon_path())
        except Exception:
            pass

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(50, self._center_on_screen)

    def _build_ui(self) -> None:
        shell = ctk.CTkFrame(
            self,
            fg_color=THEME["shell"],
            border_width=1,
            border_color=THEME["border"],
            corner_radius=24,
        )
        shell.pack(fill="both", expand=True, padx=18, pady=18)

        topbar = ctk.CTkFrame(shell, fg_color="transparent")
        topbar.pack(fill="x", padx=22, pady=(20, 12))

        ctk.CTkLabel(
            topbar,
            text="Folder Restorer",
            text_color=THEME["text"],
            font=ctk.CTkFont(size=28, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            topbar,
            text="Paste the target folder path below. The app will remove icon overrides and refresh Explorer.",
            text_color=THEME["muted"],
            font=ctk.CTkFont(size=13),
            wraplength=620,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        card = ctk.CTkFrame(
            shell,
            fg_color=THEME["card"],
            border_width=1,
            border_color=THEME["border"],
            corner_radius=22,
        )
        card.pack(fill="x", padx=22, pady=(8, 14))

        ctk.CTkLabel(
            card,
            text="Folder Path",
            text_color=THEME["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 8))

        entry = ctk.CTkEntry(
            card,
            textvariable=self.path_var,
            height=40,
            fg_color=THEME["card_soft"],
            text_color=THEME["text"],
            border_color=THEME["border"],
            placeholder_text="C:\\Users\\Amer\\Downloads\\Example Folder",
            placeholder_text_color=THEME["muted"],
        )
        entry.pack(fill="x", padx=18, pady=(0, 10))
        entry.focus_set()
        entry.icursor("end")

        helper = ctk.CTkFrame(card, fg_color="transparent")
        helper.pack(fill="x", padx=18, pady=(0, 16))

        ctk.CTkButton(
            helper,
            text="Choose Folder",
            command=self._choose_folder,
            width=150,
            height=32,
            corner_radius=8,
            fg_color="#244B56",
            hover_color="#2E6674",
            text_color="#F7FFFF",
            border_width=2,
            border_color="#79B8C3",
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

        ctk.CTkLabel(
            helper,
            text="Tip: you can paste any folder path here.",
            text_color=THEME["muted"],
            font=ctk.CTkFont(size=12),
        ).pack(side="right")

        actions = ctk.CTkFrame(shell, fg_color="transparent")
        actions.pack(fill="x", padx=22, pady=(0, 20))

        ctk.CTkButton(
            actions,
            text="Cancel",
            command=self._cancel,
            width=110,
            height=36,
            corner_radius=8,
            fg_color="#244B56",
            hover_color="#2E6674",
            text_color="#F7FFFF",
            border_width=2,
            border_color="#79B8C3",
            font=ctk.CTkFont(size=13),
        ).pack(side="right")

        ctk.CTkButton(
            actions,
            text="Restore Icons",
            command=self._accept,
            width=150,
            height=36,
            corner_radius=8,
            fg_color="#5EE7D6",
            hover_color="#7FF3E5",
            text_color="#041C21",
            border_width=2,
            border_color="#B8FFF4",
            font=ctk.CTkFont(size=13),
        ).pack(side="right", padx=(0, 10))

        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self._cancel())

    def _center_on_screen(self) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _choose_folder(self) -> None:
        chooser = DirectoryChooserDialog(self, initial=self.path_var.get().strip() or os.getcwd())
        selected = chooser.show()
        if selected:
            self.path_var.set(selected)

    def _accept(self) -> None:
        candidate = self.path_var.get().strip().strip('"')
        if not candidate:
            messagebox.showerror("Folder Restorer", "Enter a folder path first.", parent=self)
            return

        candidate = os.path.abspath(os.path.expandvars(os.path.expanduser(candidate)))
        if not os.path.isdir(candidate):
            messagebox.showerror("Folder Restorer", f"Folder not found:\n{candidate}", parent=self)
            return

        self.selected_path = candidate
        self.destroy()

    def _cancel(self) -> None:
        self.selected_path = None
        self.destroy()


class DirectoryChooserDialog(ctk.CTkToplevel):
    def __init__(self, parent: ctk.CTk, initial: str):
        super().__init__(parent)
        self.selected_path: Optional[str] = None
        self.current_path = os.path.abspath(initial if os.path.isdir(initial) else os.getcwd())
        self.path_var = ctk.StringVar(value=self.current_path)

        self.title("Choose Folder")
        self.geometry("760x520")
        self.resizable(False, False)
        self.configure(fg_color=THEME["window_bg"])
        self.transient(parent)
        self.grab_set()
        try:
            self.iconbitmap(get_app_icon_path())
        except Exception:
            pass

        self._build_ui()
        self._refresh_directory_list()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(50, self._center_on_parent)

    def _build_ui(self) -> None:
        shell = ctk.CTkFrame(
            self,
            fg_color=THEME["shell"],
            border_width=1,
            border_color=THEME["border"],
            corner_radius=24,
        )
        shell.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            shell,
            text="Choose Folder",
            text_color=THEME["text"],
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(
            shell,
            text="Browse folders with the same dark theme, then confirm the folder you want to restore.",
            text_color=THEME["muted"],
            font=ctk.CTkFont(size=13),
            wraplength=680,
            justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 12))

        path_row = ctk.CTkFrame(shell, fg_color="transparent")
        path_row.pack(fill="x", padx=22, pady=(0, 12))

        self.path_entry = ctk.CTkEntry(
            path_row,
            textvariable=self.path_var,
            height=38,
            fg_color=THEME["card_soft"],
            text_color=THEME["text"],
            border_color=THEME["border"],
        )
        self.path_entry.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            path_row,
            text="Go",
            command=self._go_to_entered_path,
            width=74,
            height=38,
            corner_radius=8,
            fg_color="#244B56",
            hover_color="#2E6674",
            text_color="#F7FFFF",
            border_width=2,
            border_color="#79B8C3",
            font=ctk.CTkFont(size=13),
        ).pack(side="left", padx=(10, 0))

        card = ctk.CTkFrame(
            shell,
            fg_color=THEME["card"],
            border_width=1,
            border_color=THEME["border"],
            corner_radius=22,
        )
        card.pack(fill="both", expand=True, padx=22, pady=(0, 14))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(16, 10))

        ctk.CTkButton(
            actions,
            text="Up",
            command=self._go_up,
            width=84,
            height=32,
            corner_radius=8,
            fg_color="#244B56",
            hover_color="#2E6674",
            text_color="#F7FFFF",
            border_width=2,
            border_color="#79B8C3",
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

        ctk.CTkButton(
            actions,
            text="This Folder",
            command=self._select_current_folder,
            width=110,
            height=32,
            corner_radius=8,
            fg_color="#5EE7D6",
            hover_color="#7FF3E5",
            text_color="#041C21",
            border_width=2,
            border_color="#B8FFF4",
            font=ctk.CTkFont(size=12),
        ).pack(side="right")

        ctk.CTkLabel(
            card,
            text="Subfolders",
            text_color=THEME["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=18)

        self.directory_list = ctk.CTkScrollableFrame(
            card,
            fg_color=THEME["card_deep"],
            border_width=1,
            border_color=THEME["border"],
            corner_radius=18,
        )
        self.directory_list.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        self.directory_list.grid_columnconfigure(0, weight=1)

        footer = ctk.CTkFrame(shell, fg_color="transparent")
        footer.pack(fill="x", padx=22, pady=(0, 20))

        ctk.CTkButton(
            footer,
            text="Cancel",
            command=self._cancel,
            width=110,
            height=36,
            corner_radius=8,
            fg_color="#244B56",
            hover_color="#2E6674",
            text_color="#F7FFFF",
            border_width=2,
            border_color="#79B8C3",
            font=ctk.CTkFont(size=13),
        ).pack(side="right")

        self.bind("<Return>", lambda _event: self._go_to_entered_path())
        self.bind("<Escape>", lambda _event: self._cancel())

    def _center_on_parent(self) -> None:
        self.update_idletasks()
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_w = self.master.winfo_width()
        parent_h = self.master.winfo_height()
        width = self.winfo_width()
        height = self.winfo_height()
        x = max(0, parent_x + (parent_w - width) // 2)
        y = max(0, parent_y + (parent_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _clear_directory_buttons(self) -> None:
        for widget in self.directory_list.winfo_children():
            widget.destroy()

    def _refresh_directory_list(self) -> None:
        self.current_path = os.path.abspath(self.current_path)
        self.path_var.set(self.current_path)
        self._clear_directory_buttons()

        directories = []
        try:
            with os.scandir(self.current_path) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        directories.append(entry.name)
        except PermissionError:
            messagebox.showerror("Choose Folder", f"Permission denied:\n{self.current_path}", parent=self)
            return
        except FileNotFoundError:
            messagebox.showerror("Choose Folder", f"Folder not found:\n{self.current_path}", parent=self)
            return

        directories.sort(key=str.lower)
        if not directories:
            ctk.CTkLabel(
                self.directory_list,
                text="No subfolders found in this location.",
                text_color=THEME["muted"],
                font=ctk.CTkFont(size=13),
            ).grid(row=0, column=0, sticky="w", padx=10, pady=10)
            return

        for index, name in enumerate(directories):
            path = os.path.join(self.current_path, name)
            button = ctk.CTkButton(
                self.directory_list,
                text=name,
                anchor="w",
                command=lambda selected=path: self._enter_directory(selected),
                height=34,
                corner_radius=8,
                fg_color=THEME["card_soft"],
                hover_color=THEME["accent_deep"],
                text_color=THEME["text"],
                border_width=1,
                border_color=THEME["border"],
                font=ctk.CTkFont(size=13),
            )
            button.grid(row=index, column=0, sticky="ew", padx=8, pady=5)

    def _enter_directory(self, path: str) -> None:
        self.current_path = path
        self._refresh_directory_list()

    def _go_up(self) -> None:
        parent = os.path.dirname(self.current_path.rstrip("\\/"))
        if parent and parent != self.current_path:
            self.current_path = parent
            self._refresh_directory_list()

    def _go_to_entered_path(self) -> None:
        candidate = self.path_var.get().strip().strip('"')
        if not candidate:
            return
        candidate = os.path.abspath(os.path.expandvars(os.path.expanduser(candidate)))
        if not os.path.isdir(candidate):
            messagebox.showerror("Choose Folder", f"Folder not found:\n{candidate}", parent=self)
            return
        self.current_path = candidate
        self._refresh_directory_list()

    def _select_current_folder(self) -> None:
        self.selected_path = self.current_path
        self.destroy()

    def _cancel(self) -> None:
        self.selected_path = None
        self.destroy()

    def show(self) -> Optional[str]:
        self.wait_window()
        return self.selected_path


def pick_folder_dialog(initial: Optional[str] = None) -> Optional[str]:
    picker = FolderPickerDialog(initial=initial)
    picker.mainloop()
    return picker.selected_path


def confirm_explorer_restart(root: str, *, cli_mode: bool) -> bool:
    if cli_mode:
        return True

    message = (
        "This will restore default folder icons for:\n"
        f"{root}\n\n"
        "All open File Explorer folder windows will be closed while Windows Explorer restarts.\n\n"
        "Do you want to continue?"
    )
    return bool(messagebox.askokcancel("Folder Restorer", message, icon="warning"))


def show_summary(root: str, stats: Stats, *, dry_run: bool, cli_mode: bool) -> None:
    summary = "\n".join(
        [
            f"Folder: {root}",
            f"Mode: {'DRY RUN' if dry_run else 'LIVE'}",
            "",
            f"Folders scanned: {stats.scanned_folders}",
            f"desktop.ini found: {stats.desktop_ini_found}",
            f"desktop.ini removed: {stats.desktop_ini_removed}",
            f"attrib OK count: {stats.attrib_ok}",
            f"errors/warnings: {stats.errors}",
        ]
    )
    show_info(summary, cli_mode=cli_mode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recursively restore default Windows folder icons (aggressive desktop.ini cleanup; Drive-download friendly)."
    )
    parser.add_argument("root", nargs="?", default=None, help="Root folder to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change, but do nothing")
    parser.add_argument("--no-gui", action="store_true", help="Run without blocking message boxes when launched from a terminal")
    parser.add_argument("--elevate", action="store_true", help="Request administrator rights before making live changes")
    return parser.parse_args()


def main() -> int:
    configure_customtkinter()
    args = parse_args()
    cli_mode = is_cli_mode(args)

    root = args.root or pick_folder_dialog()
    if not root:
        print("No folder selected. Exiting.")
        return 1

    root = os.path.abspath(root)
    if not os.path.isdir(root):
        show_error(f"Not a directory:\n{root}", cli_mode=cli_mode)
        return 2

    if not args.dry_run and args.elevate:
        if relaunch_as_admin(root, dry_run=args.dry_run, no_gui=cli_mode):
            return 0
        show_error(
            "Administrator permission is required. The elevated relaunch was cancelled or failed.",
            cli_mode=cli_mode,
        )
        return 3

    if not args.dry_run and not confirm_explorer_restart(root, cli_mode=cli_mode):
        print("User cancelled before Explorer restart warning.")
        return 1

    print(f"Root: {root}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")

    stats = Stats()
    process_tree_recursive(root, dry_run=args.dry_run, stats=stats)
    refresh_explorer_icons(root, dry_run=args.dry_run)
    if not restart_explorer(dry_run=args.dry_run):
        stats.errors += 1

    print("\n--- Summary ---")
    print(f"Folders scanned:     {stats.scanned_folders}")
    print(f"desktop.ini found:   {stats.desktop_ini_found}")
    print(f"desktop.ini removed: {stats.desktop_ini_removed}")
    print(f"attrib OK count:     {stats.attrib_ok}")
    print(f"errors/warnings:     {stats.errors}")
    print("\nIf some icons still look wrong, restart Windows Explorer manually.")

    show_summary(root, stats, dry_run=args.dry_run, cli_mode=cli_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
