import os
import sys
import tkinter as tk
from tkinter import ttk

# -------------------- Health Noord style tokens --------------------
HN_NAVY = "#1F2D54"
HN_ORANGE = "#EA590C"
HN_ORANGE_DARK = "#D45100"
HN_BG = "#FFFFFF"
HN_SURFACE = "#F6F8FB"   # card achtergrond
HN_BORDER = "#E3E8F0"
HN_MUTED = "#5A6575"
HN_DISABLED = "#F2B79D"


def resource_path(relative_path: str) -> str:
    """
    Geef het absolute pad naar een resource terug. Werkt voor:
    - draaien vanuit source
    - PyInstaller onedir/onefile (via sys._MEIPASS)
    """
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def apply_hn_theme(root: tk.Tk) -> ttk.Style:
    """
    Pas de Health Noord huisstijl toe op ttk widgets.
    Werkt het best met 'clam' theme op Windows.
    """
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    base_font = ("Segoe UI", 11)
    title_font = ("Segoe UI", 22, "bold")
    sub_title_font = ("Segoe UI", 14, "bold")
    group_font = ("Segoe UI", 12, "bold")
    button_font = ("Segoe UI", 11, "bold")

    root.configure(bg=HN_BG)
    root.option_add("*Font", base_font)

    # Containers
    style.configure("App.TFrame", background=HN_BG)
    style.configure("Card.TFrame", background=HN_BG)

    # Labels
    style.configure("TLabel", background=HN_BG, foreground=HN_NAVY, font=base_font)
    style.configure("HN.Muted.TLabel", background=HN_BG, foreground=HN_MUTED, font=base_font)
    style.configure("HN.CardMuted.TLabel", background=HN_BG, foreground=HN_MUTED, font=base_font)
    style.configure("HN.Card.TLabel", background=HN_BG, foreground=HN_NAVY, font=base_font)

    style.configure("HN.Title.TLabel", background=HN_BG, foreground=HN_NAVY, font=title_font)
    style.configure("HN.TitleOrange.TLabel", background=HN_BG, foreground=HN_ORANGE, font=title_font)
    style.configure("HN.SubTitle.TLabel", background=HN_BG, foreground=HN_NAVY, font=sub_title_font)

    # Labelframe als “card”
    style.configure("Card.TLabelframe", background=HN_BG, borderwidth=1, relief="solid")
    style.configure("Card.TLabelframe.Label", background=HN_BG, foreground=HN_NAVY, font=group_font)

    # Buttons
    style.configure("TButton", font=base_font)

    style.configure(
        "Primary.TButton",
        background=HN_ORANGE,
        foreground="white",
        font=button_font,
        padding=(16, 10),
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "Primary.TButton",
        background=[("active", HN_ORANGE_DARK), ("disabled", HN_DISABLED)],
        foreground=[("disabled", "white")],
    )

    style.configure(
        "Secondary.TButton",
        background=HN_BG,
        foreground=HN_NAVY,
        padding=(12, 8),
        borderwidth=1,
        relief="solid",
        font=base_font,
    )
    style.map("Secondary.TButton", background=[("active", "#EFF3F8")])

    style.configure(
        "Icon.TButton",
        background=HN_BG,
        foreground=HN_NAVY,
        padding=(8, 6),
        borderwidth=1,
        relief="solid",
        font=base_font,
    )
    style.map("Icon.TButton", background=[("active", "#EFF3F8")])

    # Checkbuttons (jij gebruikt ChromeCheck.TCheckbutton)
    style.configure(
        "ChromeCheck.TCheckbutton",
        background=HN_SURFACE,
        foreground=HN_NAVY,
        font=base_font,
        padding=(4, 2),
    )
    style.configure(
        "TCheckbutton",
        background=HN_SURFACE,
        foreground=HN_NAVY,
        font=base_font,
        padding=(4, 2),
    )

    # Progressbar (oranje)
    style.configure(
        "HN.Horizontal.TProgressbar", 
        troughcolor=HN_BORDER, 
        background=HN_ORANGE, 
        thickness=16,
        barsize = 60)

    return style


__all__ = [
    "HN_NAVY",
    "HN_ORANGE",
    "HN_ORANGE_DARK",
    "HN_BG",
    "HN_SURFACE",
    "HN_BORDER",
    "HN_MUTED",
    "HN_DISABLED",
    "resource_path",
    "apply_hn_theme",
]
