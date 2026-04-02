import customtkinter as ctk


THEME = {
    "window_bg": "#08141A",
    "shell": "#0D1D24",
    "card": "#122A33",
    "card_soft": "#183742",
    "card_deep": "#0B1D24",
    "border": "#244B56",
    "accent": "#53E0D0",
    "accent_soft": "#2A8E87",
    "accent_deep": "#103E42",
    "text": "#EAF8F7",
    "muted": "#88A9B0",
    "idle": "#9DB1B6",
    "success": "#57D08B",
    "warning": "#F3B85A",
    "danger": "#FF6B6B",
}


def configure_customtkinter() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
