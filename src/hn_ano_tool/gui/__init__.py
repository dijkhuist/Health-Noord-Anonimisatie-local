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


def application_directory() -> str:
    """Return the executable's folder, or the project root when running from source."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return str(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


def enable_dpi_awareness() -> None:
    """
    Tell Windows we render at the real screen resolution, so it stops
    bitmap-stretching (blurring) the window on scaled displays. Must run before
    the first Tk window is created. System-aware rather than per-monitor:
    Tk does not re-layout on WM_DPICHANGED.
    """
    if os.name != "nt":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def ui_scale(widget: tk.Misc) -> float:
    """Screen pixels per design pixel: 1.0 at 100% Windows scaling, 2.5 at 250%."""
    return widget.winfo_fpixels("1i") / 96


def make_check_images(root: tk.Misc) -> tuple[tk.PhotoImage, tk.PhotoImage]:
    """
    Draw (unchecked, checked) checkbox images at this screen's scale. The native
    Windows indicator does not grow with DPI and is tiny on scaled displays.
    """
    scale = ui_scale(root)
    size = max(13, round(18 * scale))
    border = max(1, round(1.5 * scale))

    def box(fill: str, edge: str) -> tk.PhotoImage:
        image = tk.PhotoImage(master=root, width=size, height=size)
        image.put(edge, to=(0, 0, size, size))
        image.put(fill, to=(border, border, size - border, size - border))
        return image

    unchecked = box("white", HN_MUTED)
    checked = box(HN_ORANGE, HN_ORANGE)

    # White tick: two strokes through these points (fractions of the box size).
    stroke = max(2, round(size / 7))
    points = [(0.22, 0.52), (0.42, 0.72), (0.78, 0.30)]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        steps = size * 2
        for i in range(steps + 1):
            x = int((x0 + (x1 - x0) * i / steps) * size - stroke / 2)
            y = int((y0 + (y1 - y0) * i / steps) * size - stroke / 2)
            checked.put("white", to=(x, y, x + stroke, y + stroke))
    return unchecked, checked


def apply_hn_theme(root: tk.Tk) -> ttk.Style:
    """
    Pas de Health Noord huisstijl toe op ttk widgets.
    Werkt het best met 'clam' theme op Windows.
    """
    style = ttk.Style(root)
    scale = ui_scale(root)

    def px(*values: int):
        scaled = tuple(round(v * scale) for v in values)
        return scaled[0] if len(scaled) == 1 else scaled

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
    style.configure("HN.Link.TLabel", background=HN_BG, foreground="#1769AA", font=base_font, underline=True)

    style.configure("HN.Title.TLabel", background=HN_BG, foreground=HN_NAVY, font=title_font)
    style.configure("HN.TitleOrange.TLabel", background=HN_BG, foreground=HN_ORANGE, font=title_font)
    style.configure("HN.SubTitle.TLabel", background=HN_BG, foreground=HN_NAVY, font=sub_title_font)
    # Same look as a Labelframe title, for a custom labelwidget (pass the font explicitly)
    style.configure("HN.Group.TLabel", background=HN_BG, foreground=HN_NAVY, font=group_font)

    # Labelframe als “card”
    style.configure("Card.TLabelframe", background=HN_BG, borderwidth=1, relief="solid")
    style.configure("Card.TLabelframe.Label", background=HN_BG, foreground=HN_NAVY, font=group_font)

    # Buttons
    style.configure("TButton", font=base_font, padding=px(10, 4))

    style.configure(
        "Primary.TButton",
        background=HN_ORANGE,
        foreground="white",
        font=button_font,
        padding=px(16, 8),
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
        padding=px(10, 5),
        borderwidth=1,
        relief="solid",
        font=base_font,
    )
    style.map("Secondary.TButton", background=[("active", "#EFF3F8")])

    style.configure(
        "Icon.TButton",
        background=HN_BG,
        foreground=HN_NAVY,
        padding=px(6, 3),
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
        padding=px(4, 2),
    )
    style.configure(
        "TCheckbutton",
        background=HN_SURFACE,
        foreground=HN_NAVY,
        font=base_font,
        padding=px(4, 2),
    )

    # Scrollbars: clam draws them `arrowsize` wide, which does not follow DPI on its own
    for orient in ("Vertical", "Horizontal"):
        style.configure(f"{orient}.TScrollbar", arrowsize=px(16))

    # Progressbar (oranje)
    style.configure(
        "HN.Horizontal.TProgressbar", 
        troughcolor=HN_BORDER, 
        background=HN_ORANGE, 
        thickness=px(16),
        barsize=px(60))

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
    "application_directory",
    "apply_hn_theme",
    "enable_dpi_awareness",
    "ui_scale",
    "make_check_images",
]
