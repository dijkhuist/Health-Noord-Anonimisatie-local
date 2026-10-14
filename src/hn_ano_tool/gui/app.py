import ctypes
import ctypes.wintypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from queue import Queue, Empty
import os
import time

from src.hn_ano_tool.app.service import MainController, ProcessingCancelled, Settings
from src.hn_ano_tool.app.enums import DEDUCE_FILTER_GROUPS
from src.hn_ano_tool.engine.deduce_adapter import warmup_deducefy
from src.hn_ano_tool.io.text_io import validate_txt_path

from src.hn_ano_tool.gui import (
    apply_hn_theme,
    resource_path,
    application_directory,
    HN_BG,
    HN_SURFACE,
    HN_NAVY,
    HN_BORDER,
)
from src.hn_ano_tool.gui.preferences import load_preferences, save_preferences
from src.hn_ano_tool.gui.preflight import validate_run_paths
MIN_FILTER_KOLOM_PX = 380


def _work_area(root: tk.Misc) -> tuple[int, int, int, int]:
    """Screen area without the taskbar as (left, top, right, bottom)."""
    if os.name == "nt":
        try:
            rect = ctypes.wintypes.RECT()
            SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                return rect.left, rect.top, rect.right, rect.bottom
        except (AttributeError, OSError):
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


class _Tooltip:
    """Show the text from `get_text` under `widget` while the mouse hovers over it."""

    def __init__(self, widget: tk.Widget, get_text):
        self.widget = widget
        self.get_text = get_text
        self.tip = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event):
        text = self.get_text()
        if not text or self.tip:
            return
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip,
            text=text,
            bg="#FFFFE0",
            fg=HN_NAVY,
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=3,
        ).pack()

    def _hide(self, _event):
        if self.tip:
            self.tip.destroy()
            self.tip = None

class App(tk.Tk):
    def __init__(self):
        if os.name == "nt":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "Hanze.HealthNoord.AnonymisatieTool"
                )
            except (AttributeError, OSError):
                pass
        super().__init__()

        self._run_active = False
        self._cancel_requested = False
        self._cancel_event = None
        self._ready_for_run = False
        self._run_started_at = 0.0
        self._current_phase = ""
        self._last_output_path = None
        self._last_log_path = None
        self._preferences = load_preferences()
        self.whitelist_path = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.title("Health Noord - Anonimisatie-tool")

        # --- Window icon (robust for dev + PyInstaller) ---
        ico_path = resource_path("assets/health_noord.ico")
        fallback_ico_path = resource_path("assets/favicon.ico")
        png_path = resource_path("assets/favicon.png")
        # Pre-scaled with Lanczos: Tk's subsample() skips pixels and makes the tagline jagged.
        logo_path = resource_path("assets/hoofdlogo-healthNoord-klein.png")

        # 1) Prefer .ico for Windows titlebar/taskbar
        try:
            if os.path.exists(ico_path):
                self.iconbitmap(default=ico_path)
                self.iconbitmap(ico_path)
            elif os.path.exists(fallback_ico_path):
                self.iconbitmap(default=fallback_ico_path)
                self.iconbitmap(fallback_ico_path)
        except tk.TclError:
            if os.path.exists(fallback_ico_path):
                try:
                    self.iconbitmap(default=fallback_ico_path)
                    self.iconbitmap(fallback_ico_path)
                except tk.TclError:
                    pass

        # 2) Fallback / also set iconphoto (keep reference!)
        try:
            if os.path.exists(png_path):
                self._icon_img = tk.PhotoImage(file=png_path)
                self.iconphoto(True, self._icon_img)
        except Exception:
            pass

        # --- Apply Health Noord theme ---
        self.style = apply_hn_theme(self)
        base_font = ("Segoe UI", 11)

        # --- Main container ---
        main = ttk.Frame(self, padding=(18, 12, 18, 12), style="App.TFrame")
        main.pack(fill="both", expand=True)

        # Header: small logo with the title next to it, on one row
        header = ttk.Frame(main, style="App.TFrame")
        header.pack(fill="x", pady=(0, 10))

        self._hn_logo_img = None
        try:
            if os.path.exists(logo_path):
                self._hn_logo_img = tk.PhotoImage(file=logo_path)
                ttk.Label(header, image=self._hn_logo_img, style="TLabel").pack(side="left")
        except Exception:
            self._hn_logo_img = None

        if self._hn_logo_img is None:
            ttk.Label(header, text="Health ", style="HN.Title.TLabel").pack(side="left")
            ttk.Label(header, text="Noord", style="HN.TitleOrange.TLabel").pack(side="left")

        title_col = ttk.Frame(header, style="App.TFrame")
        title_col.pack(side="left", padx=(18, 0))
        ttk.Label(title_col, text="Tekst-anonimisatie", style="HN.SubTitle.TLabel").pack(anchor="w")
        ttk.Label(
            title_col,
            text="Kies een invoerbestand en uitvoermap, en eventueel extra lijsten.",
            style="HN.Muted.TLabel",
        ).pack(anchor="w")

        # --- Upper content: 2 columns ---
        upper = ttk.Frame(main, style="App.TFrame")
        upper.pack(fill="x", expand=False)

        upper.grid_columnconfigure(0, weight=2, uniform="cols")
        upper.grid_columnconfigure(1, weight=1, uniform="cols", minsize=MIN_FILTER_KOLOM_PX)
        upper.grid_rowconfigure(0, weight=1)

        left_col = ttk.Frame(upper, style="App.TFrame")
        right_col = ttk.Frame(upper, style="App.TFrame")

        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        # === LEFT COLUMN ===
        # attr name -> (path label, clear button, placeholder text)
        self._path_rows: dict[str, tuple[ttk.Label, ttk.Button, str]] = {}
        self._full_paths: dict[str, str] = {}

        frm_required = ttk.Labelframe(left_col, text="Verplicht", style="Card.TLabelframe", padding=(14, 8))
        frm_required.pack(fill="x")
        frm_optional = ttk.Labelframe(left_col, text="Optioneel", style="Card.TLabelframe", padding=(14, 8))
        frm_optional.pack(fill="both", expand=True, pady=(10, 0))
        for frame in (frm_required, frm_optional):
            frame.grid_columnconfigure(1, weight=1)

        self._add_path_row(
            frm_required, 0, "📁 Invoer .txt", self.choose_input,
            "input_file", "Geen bestand geselecteerd",
        )
        self._add_path_row(
            frm_required, 1, "📁 Uitvoermap", self.choose_output,
            "output_dir", "Geen map geselecteerd",
        )
        self._add_path_row(
            frm_optional, 0, "📁 Logmap", self.choose_log,
            "log_dir", "Geen map geselecteerd (log komt in de uitvoermap)",
        )
        self._add_path_row(
            frm_optional, 1, "📁 Patiëntenlijst", self.choose_extra_names,
            "extra_names_path", "Geen patiëntenbestand geselecteerd",
        )
        self._add_path_row(
            frm_optional, 2, "📁 Medewerkerslijst", self.choose_extra_medewerkers_names,
            "extra_medewerkers_names_path", "Geen medewerkersbestand geselecteerd",
        )
        self._add_path_row(
            frm_optional, 3, "📁 Locatielijst", self.choose_extra_locaties_names,
            "extra_locaties_names_path", "Geen locatiesbestand geselecteerd",
        )
        self._add_path_row(
            frm_optional, 4, "📁 Whitelist", self.choose_whitelist,
            "whitelist_path", "Geen whitelistbestand geselecteerd",
        )

        # === RIGHT COLUMN ===
        frm_filters = ttk.Labelframe(right_col, text="Filter op", style="Card.TLabelframe", padding=14)
        frm_filters.pack(fill="both", expand=True)

        self.filter_vars: dict[str, tk.BooleanVar] = {}
        disabled_groups = set(self._preferences.get("disabled_groups", []))

        row = 0
        for key, label in DEDUCE_FILTER_GROUPS.items():
            var = tk.BooleanVar(value=key not in disabled_groups)
            # Classic tk.Checkbutton: on Windows it draws the native box with a
            # tick, where ttk's "clam" theme draws a cross that reads as "off".
            chk = tk.Checkbutton(
                frm_filters,
                text=label,
                variable=var,
                command=self._save_preferences,
                anchor="w",
                bg=HN_BG,
                fg=HN_NAVY,
                activebackground=HN_BG,
                activeforeground=HN_NAVY,
                selectcolor="white",
                highlightthickness=0,
                borderwidth=0,
                font=base_font,
            )
            chk.grid(row=row, column=0, sticky="w", padx=6, pady=3)
            self.filter_vars[key] = var
            row += 1

        # --- Run button full width ---
        run_frame = ttk.Frame(main, style="App.TFrame")
        run_frame.pack(fill="x", pady=(12, 6))

        self.btn_run = ttk.Button(run_frame, text="⏳ Bezig met initialiseren...", style="Primary.TButton", command=self.run)
        self.btn_run.pack(side="left", fill="x", expand=True)
        self.btn_run.config(state="disabled")
        self.btn_cancel = ttk.Button(
            run_frame,
            text="Annuleer verwerking",
            style="Secondary.TButton",
            command=self.cancel_run,
            state="disabled",
        )
        self.btn_cancel.pack(side="left", padx=(8, 0))

        # progress UI
        self.progressbar = ttk.Progressbar(main, mode="determinate", style="HN.Horizontal.TProgressbar")
        self.progressbar.pack(fill="x", pady=(6, 0))

        self.progress_label = ttk.Label(main, text="", style="HN.Muted.TLabel")
        self.progress_label.pack(anchor="w", pady=(3, 8))

        # Result summary is packed at the bottom BEFORE the preview, so on a small
        # screen the preview shrinks instead of these lines falling off the window.
        result_frame = ttk.Frame(main, style="App.TFrame")
        result_frame.pack(side="bottom", fill="x")

        self.lbl_stats = ttk.Label(result_frame, text="", anchor="w", style="HN.Muted.TLabel")
        self.lbl_stats.pack(fill="x", pady=(4, 0))
        self.lbl_output_location = ttk.Label(
            result_frame,
            text="",
            style="HN.Link.TLabel",
            cursor="hand2",
            takefocus=True,
            wraplength=1100,
            justify="left",
        )
        self.lbl_output_location.pack(fill="x", anchor="w")
        self.lbl_output_location.bind("<Button-1>", lambda _event: self.open_output())
        self.lbl_output_location.bind("<Return>", lambda _event: self.open_output())
        self.lbl_output_location.bind("<space>", lambda _event: self.open_output())
        self.lbl_log_location = ttk.Label(
            result_frame,
            text="",
            style="HN.Link.TLabel",
            cursor="hand2",
            takefocus=True,
            wraplength=1100,
            justify="left",
        )
        self.lbl_log_location.pack(fill="x", anchor="w")
        self.lbl_log_location.bind("<Button-1>", lambda _event: self.open_log())
        self.lbl_log_location.bind("<Return>", lambda _event: self.open_log())
        self.lbl_log_location.bind("<space>", lambda _event: self.open_log())

        # --- Output preview ---
        preview_frame = ttk.Frame(main, style="App.TFrame")
        preview_frame.pack(fill="both", expand=True)

        preview_header = ttk.Frame(preview_frame, style="App.TFrame")
        preview_header.pack(fill="x", pady=(0, 6))
        ttk.Label(preview_header, text="Geanonimiseerde tekst:", style="TLabel").pack(side="left")
        self.btn_open_output = ttk.Button(
            preview_header,
            text="Open resultaat",
            style="Secondary.TButton",
            command=self.open_output,
            state="disabled",
        )
        self.btn_open_output.pack(side="right")
        self.btn_open_folder = ttk.Button(
            preview_header,
            text="Open uitvoermap",
            style="Secondary.TButton",
            command=self.open_output_folder,
            state="disabled",
        )
        self.btn_open_folder.pack(side="right", padx=(0, 8))

        output_frame = ttk.Frame(preview_frame, style="App.TFrame")
        output_frame.pack(fill="both", expand=True, padx=0, pady=(0, 6))

        self.txt_out = tk.Text(
            output_frame,
            height=6,
            wrap="word",
            bg=HN_SURFACE,
            fg=HN_NAVY,
            insertbackground=HN_NAVY,
            font=base_font,
            relief="flat",
            highlightthickness=1,
            highlightbackground=HN_BORDER,
            padx=12,
            pady=10,
            state="disabled",
        )
        output_scrollbar = ttk.Scrollbar(
            output_frame,
            orient="vertical",
            command=self.txt_out.yview,
        )
        self.txt_out.configure(yscrollcommand=output_scrollbar.set)
        self.txt_out.pack(side="left", fill="both", expand=True)
        output_scrollbar.pack(side="right", fill="y")

        self._fit_to_screen()

        # to front on start
        self.after(100, self.bring_to_front)

        # --- Background warm-up deduce ---
        self.ui_queue = Queue()
        self.after(100, self._process_ui_queue)

        # --- Start warm-up bij opstart (Deduce init) ---
        self.progressbar.config(mode="indeterminate")
        self.progressbar.start(30)
        self.progress_label.config(text="Initialiseren (Deduce)...")

        self.after(100, self._start_warmup)

    # --- File Choosers ---

    def _add_path_row(
        self,
        parent: ttk.Labelframe,
        row: int,
        button_text: str,
        command,
        attr_name: str,
        default_text: str,
    ):
        setattr(self, attr_name, None)
        ttk.Button(
            parent,
            text=button_text,
            style="Secondary.TButton",
            width=18,
            command=command,
        ).grid(row=row, column=0, sticky="w", pady=4)

        # width=1: the label takes the space the grid gives it instead of
        # stretching the column to fit a long path.
        label = ttk.Label(parent, text=default_text, style="HN.CardMuted.TLabel", anchor="w", width=1)
        label.grid(row=row, column=1, sticky="ew", padx=10)
        _Tooltip(label, lambda: self._full_paths.get(attr_name))

        clear_button = ttk.Button(
            parent,
            text="✖",
            width=3,
            style="Icon.TButton",
            command=lambda: self._clear_path(attr_name),
        )
        clear_button.grid(row=row, column=2, sticky="e")
        clear_button.grid_remove()  # only shown once something is selected

        self._path_rows[attr_name] = (label, clear_button, default_text)

    @staticmethod
    def _display_path(path: str, is_file: bool, max_chars: int = 60) -> str:
        text = os.path.basename(path) if is_file else os.path.normpath(path)
        if len(text) > max_chars:
            keep = (max_chars - 1) // 2
            text = text[:keep] + "…" + text[-keep:]
        return text

    def _set_path(self, attr_name: str, path: str, is_file: bool = True):
        label, clear_button, _ = self._path_rows[attr_name]
        setattr(self, attr_name, path)
        self._full_paths[attr_name] = os.path.normpath(path)
        label.config(text=self._display_path(path, is_file), style="HN.Card.TLabel")
        clear_button.grid()

    def _clear_path(self, attr_name: str):
        label, clear_button, default_text = self._path_rows[attr_name]
        setattr(self, attr_name, None)
        self._full_paths.pop(attr_name, None)
        label.config(text=default_text, style="HN.CardMuted.TLabel")
        clear_button.grid_remove()

    def _fit_to_screen(self):
        """Size the window to its content, but never beyond the screen's work area."""
        self.update_idletasks()
        left, top, right, bottom = _work_area(self)
        scale = self.winfo_fpixels("1i") / 96
        frame = int(40 * scale)  # title bar + window borders
        available_width = right - left - frame
        available_height = bottom - top - frame

        width = min(max(self.winfo_reqwidth(), int(1200 * scale)), available_width)
        # Room for a taller preview when the screen has it.
        height = min(self.winfo_reqheight() + int(200 * scale), available_height)
        self.minsize(min(int(900 * scale), width), min(self.winfo_reqheight(), height))
        x = left + max(0, (right - left - width) // 2)
        y = top + max(0, (bottom - top - height - frame) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _save_preferences(self):
        disabled_groups = {key for key, var in self.filter_vars.items() if not var.get()}
        try:
            save_preferences(disabled_groups)
        except OSError:
            self.progress_label.configure(text="Instellingen opslaan mislukt.")

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"

        def update_controls(parent):
            for child in parent.winfo_children():
                if isinstance(child, (ttk.Button, ttk.Checkbutton, tk.Checkbutton)):
                    child.configure(state=state)
                update_controls(child)

        update_controls(self)
        self.btn_run.configure(
            state="normal" if enabled and self._ready_for_run else "disabled"
        )
        self.btn_cancel.configure(
            state="normal" if self._run_active and not self._cancel_requested else "disabled"
        )
        result_state = "normal" if enabled and self._last_output_path else "disabled"
        self.btn_open_output.configure(state=result_state)
        self.btn_open_folder.configure(state=result_state)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _format_file_size(size: int) -> str:
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / 1024:.0f} KB"

    def _on_close(self):
        if self._run_active:
            messagebox.showwarning(
                "Verwerking bezig",
                "Wacht tot de run klaar is of annuleer eerst.",
                parent=self,
            )
            return
        self.destroy()

    def cancel_run(self):
        if not self._run_active or self._cancel_requested:
            return
        if not messagebox.askyesno(
            "Annuleren bevestigen",
            "De huidige tekstchunk wordt afgemaakt. Gedeeltelijke uitvoer wordt verwijderd. Annuleren?",
            parent=self,
        ):
            return

        self._cancel_requested = True
        self._cancel_event.set()
        self.btn_cancel.configure(state="disabled", text="Annuleren...")
        self.progress_label.configure(
            text=f"{self._current_phase} | Annuleren na de huidige tekstchunk..."
        )

    def open_output(self):
        self._open_path(self._last_output_path)

    def open_log(self):
        self._open_path(self._last_log_path)

    def _show_run_log_popup(self, log_path: str):
        try:
            with open(log_path, "r", encoding="utf-8") as log_file:
                log_contents = log_file.read()
        except OSError as err:
            messagebox.showerror(
                "Log openen mislukt",
                str(err).splitlines()[0][:180],
                parent=self,
            )
            return

        popup = tk.Toplevel(self)
        popup.title("Resultaten van de anonimisatie")
        popup.geometry("720x520")
        popup.transient(self)
        popup.minsize(560, 360)

        body = ttk.Frame(popup, padding=14)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        log_text = tk.Text(body, wrap="word", height=20, width=80, state="normal")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=log_text.yview)
        log_text.configure(yscrollcommand=scrollbar.set)
        log_text.insert("1.0", log_contents)
        log_text.configure(state="disabled")
        log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(6, 0))

        footer = ttk.Frame(body)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        close_button = ttk.Button(
            footer,
            text="Sluiten",
            width=14,
            command=popup.destroy,
        )
        close_button.pack(side="right")
        popup.bind("<Escape>", lambda _event: popup.destroy())
        popup.protocol("WM_DELETE_WINDOW", popup.destroy)
        popup.grab_set()
        popup.focus_set()

    @staticmethod
    def _open_path(path: str | None):
        if not path:
            return
        try:
            os.startfile(path)
        except Exception as err:
            messagebox.showerror(
                "Openen mislukt",
                f"{os.path.basename(path)}\n{str(err).splitlines()[0][:180]}",
            )

    def open_output_folder(self):
        if not self._last_output_path:
            return
        try:
            os.startfile(os.path.dirname(self._last_output_path))
        except Exception as err:
            messagebox.showerror("Map openen mislukt", str(err).splitlines()[0][:180], parent=self)

    def _choose_txt(self, attr_name: str, title: str):
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[("Tekstbestanden", "*.txt"), ("Alle bestanden", "*.*")],
            initialdir=application_directory(),
        )
        if path:
            err = validate_txt_path(path)
            if err:
                messagebox.showerror("Ongeldig bestand", err, parent=self)
                return
            self._set_path(attr_name, path)

    def _choose_dir(self, attr_name: str, title: str):
        path = filedialog.askdirectory(title=title, initialdir=application_directory())
        if path:
            self._set_path(attr_name, path, is_file=False)

    def choose_input(self):
        self._choose_txt("input_file", "Kies invoerbestand (.txt)")

    def choose_output(self):
        self._choose_dir("output_dir", "Kies uitvoermap")

    def choose_log(self):
        self._choose_dir("log_dir", "Kies map voor logbestanden")

    def choose_extra_names(self):
        self._choose_txt("extra_names_path", "Kies patiëntenbestand (.txt)")

    def choose_extra_medewerkers_names(self):
        self._choose_txt("extra_medewerkers_names_path", "Kies medewerkersbestand (.txt)")

    def choose_extra_locaties_names(self):
        self._choose_txt("extra_locaties_names_path", "Kies locatiesbestand (.txt)")

    def choose_whitelist(self):
        self._choose_txt("whitelist_path", "Kies whitelistbestand (.txt)")

    def bring_to_front(self):
        self.lift()
        self.attributes("-topmost", True)
        self.focus_force()
        self.after(200, lambda: self.attributes("-topmost", False))

    # --- Run Anonymizer ---
    def run(self):
        if self._run_active:
            return

        optional_files = {
            "Patiëntenlijst": self.extra_names_path,
            "Medewerkerslijst": self.extra_medewerkers_names_path,
            "Locatielijst": self.extra_locaties_names_path,
            "Whitelist": self.whitelist_path,
        }
        validation_errors = validate_run_paths(
            self.input_file,
            self.output_dir,
            self.log_dir,
            optional_files,
        )
        if validation_errors:
            messagebox.showerror(
                "Controle mislukt",
                "Corrigeer eerst:\n\n• " + "\n• ".join(validation_errors),
                parent=self,
            )
            return

        input_size = os.path.getsize(self.input_file)
        log_directory = self.log_dir or self.output_dir
        summary = (
            f"Bestand: {os.path.basename(self.input_file)}\n"
            f"Grootte: {self._format_file_size(input_size)}\n"
            f"Uitvoer: {self.output_dir}\n"
            f"Log: {log_directory}"
        )
        if input_size > 50 * 1024 * 1024:
            summary += "\n\nGroot bestand; de verwerking kan enige tijd duren."
        if not messagebox.askokcancel(
            "Controle voor start",
            summary + "\n\nStart anonimiseren?",
            parent=self,
        ):
            return

        extra_names_paths = {}
        if self.extra_names_path:
            extra_names_paths["patient"] = self.extra_names_path
        if self.extra_medewerkers_names_path:
            extra_names_paths["medewerker"] = self.extra_medewerkers_names_path
        if self.extra_locaties_names_path:
            extra_names_paths["locatie"] = self.extra_locaties_names_path

        disabled_groups = {key for key, var in self.filter_vars.items() if not var.get()}
        print("[GUI] Uitgeschakelde groepen:", disabled_groups)

        settings = Settings(
            input_file=self.input_file,
            output_dir=self.output_dir,
            log_dir=self.log_dir,
            extra_names_paths=extra_names_paths,
            disabled_groups=disabled_groups,
            whitelist_path=self.whitelist_path,
        )

        total_bytes = input_size
        self._run_active = True
        self._cancel_requested = False
        self._cancel_event = threading.Event()
        self._run_started_at = time.monotonic()
        self._current_phase = "Verwerking voorbereiden"
        self._last_output_path = None
        self._last_log_path = None
        self.lbl_output_location.configure(text="")
        self.lbl_log_location.configure(text="")
        self._set_controls_enabled(False)
        self.btn_run.config(text="Anonimiseren...")
        self.btn_cancel.configure(text="Annuleer verwerking", state="normal")
        self.txt_out.configure(state="normal")
        self.txt_out.delete("1.0", "end")
        self.txt_out.configure(state="disabled")
        self.lbl_stats.config(text="")
        self.progressbar.stop()
        self.progressbar.config(mode="determinate", maximum=max(total_bytes, 1))
        self.progressbar["value"] = 0
        self.progress_label.config(
            text=f"Voortgang: 0% van {self._format_file_size(total_bytes)} | tijdsinschatting volgt"
        )

        t = threading.Thread(target=self._run_worker, args=(settings,), daemon=True)
        t.start()

    def _start_warmup(self):
        t = threading.Thread(target=self._warmup_worker, daemon=True)
        t.start()

    def _warmup_worker(self):
        try:
            warmup_deducefy()
            self.ui_queue.put(("warmup_done", None))
        except Exception as e:
            self.ui_queue.put(("warmup_done", e))

    def _run_worker(self, settings: Settings):
        try:
            controller = MainController(settings)
            out_text, out_path, log_path, stats = controller.run(
                progress_callback=lambda processed, total: self.ui_queue.put(
                    ("run_progress", processed, total)
                ),
                cancel_event=self._cancel_event,
                phase_callback=lambda phase: self.ui_queue.put(("run_phase", phase)),
            )
            self.ui_queue.put(("run_success", out_text, out_path, log_path, stats))
        except ProcessingCancelled:
            self.ui_queue.put(("run_cancelled", None))
        except Exception as e:
            self.ui_queue.put(("run_error", e))

    def _process_ui_queue(self):
        try:
            while True:
                msg = self.ui_queue.get_nowait()

                if msg[0] == "warmup_done":
                    err = msg[1]
                    try:
                        self.progressbar.stop()
                    except Exception:
                        pass
                    self.progressbar.config(mode="determinate")
                    self.progressbar["value"] = 0

                    if err:
                        detail = str(err).splitlines()[0][:220]
                        self.progress_label.config(text="Initialisatie mislukt.")
                        self.btn_run.config(text="Initialisatie mislukt")
                        messagebox.showerror("Initialisatie mislukt", detail, parent=self)
                    else:
                        self.progress_label.config(text="Klaar voor gebruik.")
                        self._ready_for_run = True
                        self._set_controls_enabled(True)
                        self.btn_run.config(text="Anonimiseer bestand")

                elif msg[0] == "run_progress":
                    _, processed_bytes, total_bytes = msg
                    total_bytes = max(total_bytes, 1)
                    processed_bytes = min(processed_bytes, total_bytes)
                    self.progressbar["maximum"] = total_bytes
                    self.progressbar["value"] = processed_bytes
                    percent = processed_bytes / total_bytes
                    elapsed = time.monotonic() - self._run_started_at
                    progress_text = (
                        f"{self._current_phase} | {percent:.0%} | "
                        f"{self._format_file_size(processed_bytes)} van "
                        f"{self._format_file_size(total_bytes)} verwerkt"
                    )
                    if elapsed >= 10 and processed_bytes > 0 and processed_bytes < total_bytes:
                        remaining = elapsed * (total_bytes - processed_bytes) / processed_bytes
                        progress_text += f" | resterend ca. {self._format_duration(remaining)}"
                    elif processed_bytes < total_bytes:
                        progress_text += " | tijdsinschatting volgt"
                    self.progress_label.config(text=progress_text)

                elif msg[0] == "run_phase":
                    self._current_phase = msg[1]
                    if self._current_phase == "Uitvoer en logbestand opslaan":
                        self.btn_cancel.configure(state="disabled", text="Afronden...")
                    self.progress_label.config(text=self._current_phase)

                elif msg[0] == "run_success":
                    _, out_text, out_path, log_path, stats = msg

                    try:
                        self.progressbar.stop()
                    except Exception:
                        pass
                    self.progressbar.config(mode="determinate")
                    self.progressbar["value"] = self.progressbar["maximum"]
                    self._last_output_path = out_path
                    self._last_log_path = log_path
                    self._run_active = False
                    self._cancel_event = None
                    self._cancel_requested = False
                    self._set_controls_enabled(True)
                    self.btn_run.config(text="Anonimiseer bestand")
                    self.progress_label.config(text="Gereed | verwerking en uitvoer opslaan voltooid")
                    
                    self.txt_out.configure(state="normal")
                    self.txt_out.delete("1.0", "end")
                    self.txt_out.insert("end", out_text) # already bounded by the controller
                    self.txt_out.configure(state="disabled")

                    details = " · ".join(
                        f"{key} {value}" for key, value in sorted(stats.by_type.items())
                    )
                    summary = f"{stats.total} vervangen"
                    self.lbl_stats.config(text=f"{summary} | {details}" if details else summary)
                    self.lbl_output_location.configure(text=f"Uitvoerbestand: {out_path}")
                    self.lbl_log_location.configure(text=f"Logbestand: {log_path}")
                    self._show_run_log_popup(log_path)

                elif msg[0] == "run_cancelled":
                    try:
                        self.progressbar.stop()
                    except Exception:
                        pass
                    self.progressbar.config(mode="determinate")
                    self._run_active = False
                    self._cancel_event = None
                    self._cancel_requested = False
                    self._set_controls_enabled(True)
                    self.btn_run.config(text="Anonimiseer bestand")
                    self.btn_cancel.config(text="Annuleer verwerking")
                    self.progress_label.config(
                        text="Geannuleerd | er is geen gedeeltelijke uitvoer opgeslagen."
                    )

                elif msg[0] == "run_error":
                    _, err = msg

                    try:
                        self.progressbar.stop()
                    except Exception:
                        pass
                    self.progressbar.config(mode="determinate")
                    self._run_active = False
                    self._cancel_event = None
                    self._cancel_requested = False
                    self._set_controls_enabled(True)
                    self.btn_run.config(text="Anonimiseer bestand")
                    self.progress_label.config(text="Anonimiseren mislukt.")

                    detail = str(err).splitlines()[0][:240]
                    messagebox.showerror("Verwerking mislukt", detail, parent=self)

        except Empty:
            pass

        self.after(100, self._process_ui_queue)


if __name__ == "__main__":
    # Tip: start bij voorkeur met `python -m gui.app` vanaf project-root
    app = App()
    app.mainloop()
