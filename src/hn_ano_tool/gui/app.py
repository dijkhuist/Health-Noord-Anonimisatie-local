import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from queue import Queue, Empty
import os

from src.hn_ano_tool.app.service import MainController, Settings
from src.hn_ano_tool.app.enums import DEDUCE_FILTER_GROUPS
from src.hn_ano_tool.engine.deduce_adapter import warmup_deducefy
from src.hn_ano_tool.io.text_io import validate_txt_path

from src.hn_ano_tool.gui import (
    apply_hn_theme,
    resource_path,
    HN_SURFACE,
    HN_NAVY,
    HN_BORDER,
)
MIN_FILTER_KOLOM_PX = 380

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Health Noord - Anonimisatie-tool")
        self.geometry("1200x900")

        # --- Window icon (robust for dev + PyInstaller) ---
        ico_path = resource_path("assets/favicon.ico")
        png_path = resource_path("assets/favicon.png")

        # 1) Prefer .ico for Windows titlebar/taskbar
        try:
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except Exception:
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
        main = ttk.Frame(self, padding=18, style="App.TFrame")
        main.pack(fill="both", expand=True)

        # Header
        header = ttk.Frame(main, style="App.TFrame")
        header.pack(fill="x", pady=(0, 14))

        # Optional logo in header (small)
        logo_row = ttk.Frame(header, style="App.TFrame")
        logo_row.pack(fill="x")

        try:
            if os.path.exists(png_path):
                self._hn_logo_img = tk.PhotoImage(file=png_path).subsample(2, 2)
                ttk.Label(logo_row, image=self._hn_logo_img, style="TLabel").pack(side="left", padx=(0, 10))
        except Exception:
            self._hn_logo_img = None

        title_row = ttk.Frame(logo_row, style="App.TFrame")
        title_row.pack(side="left", fill="x", expand=True)

        ttk.Label(title_row, text="Health ", style="HN.Title.TLabel").pack(side="left")
        ttk.Label(title_row, text="Noord", style="HN.TitleOrange.TLabel").pack(side="left")

        ttk.Label(header, text="Tekst-anonimisatie", style="HN.SubTitle.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(
            header,
            text="Configureer de instellingen en kies een bestand om te anonimiseren.",
            style="HN.Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        # --- Upper content: 2 columns ---
        upper = ttk.Frame(main, style="App.TFrame")
        upper.pack(fill="x", expand=False)

        upper.grid_columnconfigure(0, weight=2, uniform="cols")
        upper.grid_columnconfigure(1, weight=1, uniform="cols", minsize=MIN_FILTER_KOLOM_PX)

        left_col = ttk.Frame(upper, style="App.TFrame")
        right_col = ttk.Frame(upper, style="App.TFrame")

        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        # === LEFT COLUMN ===
        frm_files = ttk.Labelframe(left_col, text="Bestanden", style="Card.TLabelframe", padding=14)
        frm_files.pack(fill="x", pady=(0, 10))

        def _muted_label(parent, text: str) -> ttk.Label:
            return ttk.Label(parent, text=text, style="HN.CardMuted.TLabel", anchor="w")

        # Input file
        row_in = ttk.Frame(frm_files, style="Card.TFrame")
        row_in.pack(fill="x", pady=6)

        ttk.Button(
            row_in,
            text="✖",
            width=3,
            style="Icon.TButton",
            command=lambda: self._clear_path("input_file", self.lbl_in, "Geen bestand geselecteerd"),
        ).pack(side="left")

        ttk.Button(
            row_in,
            text="📁 Invoerbestand (.txt) te anonimiseren tekst",
            style="Secondary.TButton",
            command=self.choose_input,
        ).pack(side="left", padx=(8, 0))

        self.lbl_in = _muted_label(row_in, "Geen bestand geselecteerd")
        self.lbl_in.pack(side="left", padx=10, fill="x", expand=True)

        # Output folder
        row_out = ttk.Frame(frm_files, style="Card.TFrame")
        row_out.pack(fill="x", pady=6)

        ttk.Button(
            row_out,
            text="✖",
            width=3,
            style="Icon.TButton",
            command=lambda: self._clear_path("output_dir", self.lbl_out, "Geen map geselecteerd"),
        ).pack(side="left")

        ttk.Button(
            row_out,
            text="📁 Uitvoermap geanonimiseerde tekst",
            style="Secondary.TButton",
            command=self.choose_output,
        ).pack(side="left", padx=(8, 0))

        self.lbl_out = _muted_label(row_out, "Geen map geselecteerd")
        self.lbl_out.pack(side="left", padx=10, fill="x", expand=True)

        # Log folder
        row_log = ttk.Frame(frm_files, style="Card.TFrame")
        row_log.pack(fill="x", pady=6)

        ttk.Button(
            row_log,
            text="✖",
            width=3,
            style="Icon.TButton",
            command=lambda: self._clear_path("log_dir", self.lbl_log, "Geen map geselecteerd"),
        ).pack(side="left")

        ttk.Button(
            row_log,
            text="📁 Uitvoermap log-bestand",
            style="Secondary.TButton",
            command=self.choose_log,
        ).pack(side="left", padx=(8, 0))

        self.lbl_log = _muted_label(row_log, "Geen map geselecteerd")
        self.lbl_log.pack(side="left", padx=10, fill="x", expand=True)

        # Extra patienten names file
        row_extra = ttk.Frame(frm_files, style="Card.TFrame")
        row_extra.pack(fill="x", pady=6)

        ttk.Button(
            row_extra,
            text="✖",
            width=3,
            style="Icon.TButton",
            command=lambda: self._clear_path(
                "extra_names_path",
                self.lbl_extra_names,
                "Geen patiëntenbestand geselecteerd",
            ),
        ).pack(side="left")

        ttk.Button(
            row_extra,
            text="📁 Invoerbestand (.txt) patiënten",
            style="Secondary.TButton",
            command=self.choose_extra_names,
        ).pack(side="left", padx=(8, 0))

        self.lbl_extra_names = _muted_label(row_extra, "Geen patiëntenbestand geselecteerd")
        self.lbl_extra_names.pack(side="left", padx=10, fill="x", expand=True)

        # Extra medewerkers names file
        row_extra_med = ttk.Frame(frm_files, style="Card.TFrame")
        row_extra_med.pack(fill="x", pady=6)

        ttk.Button(
            row_extra_med,
            text="✖",
            width=3,
            style="Icon.TButton",
            command=lambda: self._clear_path(
                "extra_medewerkers_names_path",
                self.lbl_extra_medewerkers_names,
                "Geen medewerkersbestand geselecteerd",
            ),
        ).pack(side="left")

        ttk.Button(
            row_extra_med,
            text="📁 Invoerbestand (.txt) medewerkers",
            style="Secondary.TButton",
            command=self.choose_extra_medewerkers_names,
        ).pack(side="left", padx=(8, 0))

        self.lbl_extra_medewerkers_names = _muted_label(row_extra_med, "Geen medewerkersbestand geselecteerd")
        self.lbl_extra_medewerkers_names.pack(side="left", padx=10, fill="x", expand=True)

        # Extra locaties names file
        row_extra_loc = ttk.Frame(frm_files, style="Card.TFrame")
        row_extra_loc.pack(fill="x", pady=6)

        ttk.Button(
            row_extra_loc,
            text="✖",
            width=3,
            style="Icon.TButton",
            command=lambda: self._clear_path(
                "extra_locaties_names_path",
                self.lbl_extra_locaties_names,
                "Geen locatiesbestand geselecteerd",
            ),
        ).pack(side="left")

        ttk.Button(
            row_extra_loc,
            text="📁 Invoerbestand (.txt) locaties",
            style="Secondary.TButton",
            command=self.choose_extra_locaties_names,
        ).pack(side="left", padx=(8, 0))

        self.lbl_extra_locaties_names = _muted_label(row_extra_loc, "Geen locatiesbestand geselecteerd")
        self.lbl_extra_locaties_names.pack(side="left", padx=10, fill="x", expand=True)

        self.input_file = None
        self.output_dir = None
        self.log_dir = None
        self.extra_names_path = None
        self.extra_medewerkers_names_path = None
        self.extra_locaties_names_path = None

        # === RIGHT COLUMN ===
        frm_filters = ttk.Labelframe(right_col, text="Filter op", style="Card.TLabelframe", padding=14)
        frm_filters.pack(fill="both", expand=True)

        self.filter_vars: dict[str, tk.BooleanVar] = {}

        row = 0
        for key, label in DEDUCE_FILTER_GROUPS.items():
            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(frm_filters, text=label, variable=var, style="ChromeCheck.TCheckbutton")
            chk.grid(row=row, column=0, sticky="w", padx=6, pady=4)
            self.filter_vars[key] = var
            row += 1

        # --- Run button full width ---
        run_frame = ttk.Frame(main, style="App.TFrame")
        run_frame.pack(fill="x", pady=(14, 8))

        self.btn_run = ttk.Button(run_frame, text="⏳ Bezig met initialiseren...", style="Primary.TButton", command=self.run)
        self.btn_run.pack(fill="x")
        self.btn_run.config(state="disabled")

        # progress UI
        self.progressbar = ttk.Progressbar(main, mode="determinate", style="HN.Horizontal.TProgressbar")
        self.progressbar.pack(fill="x", pady=(6, 0))

        self.progress_label = ttk.Label(main, text="", style="HN.Muted.TLabel")
        self.progress_label.pack(anchor="w", pady=(3, 10))

        # --- Output preview ---
        preview_frame = ttk.Frame(main, style="App.TFrame")
        preview_frame.pack(fill="both", expand=True)

        ttk.Label(preview_frame, text="Geanonimiseerde tekst:", style="TLabel").pack(anchor="w", pady=(0, 6))

        self.txt_out = tk.Text(
            preview_frame,
            height=10,
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
        self.txt_out.pack(fill="both", expand=True, padx=0, pady=(0, 6))

        # Stats summary bar
        self.lbl_stats = ttk.Label(main, text="", anchor="w", style="HN.Muted.TLabel")
        self.lbl_stats.pack(fill="x", pady=(4, 0))

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

    def _clear_path(self, attr_name: str, label_widget: ttk.Label, default_text: str):
        setattr(self, attr_name, None)
        label_widget.config(text=default_text, style="HN.CardMuted.TLabel")

    def choose_input(self):
        path = filedialog.askopenfilename(
            title="Kies invoerbestand (.txt)",
            filetypes=[("Tekstbestanden", "*.txt"), ("Alle bestanden", "*.*")],
        )
        if path:
            err = validate_txt_path(path)
            if err:
                messagebox.showerror("Ongeldig bestand", err)
                return
            self.input_file = path
            self.lbl_in.config(text=path, style="HN.Card.TLabel")

    def choose_output(self):
        path = filedialog.askdirectory(title="Kies uitvoermap")
        if path:
            self.output_dir = path
            self.lbl_out.config(text=path, style="HN.Card.TLabel")

    def choose_log(self):
        path = filedialog.askdirectory(title="Kies map voor logbestanden")
        if path:
            self.log_dir = path
            self.lbl_log.config(text=path, style="HN.Card.TLabel")

    def choose_extra_names(self):
        path = filedialog.askopenfilename(
            title="Kies patiëntenbestand (.txt)",
            filetypes=[("Tekstbestanden", "*.txt"), ("Alle bestanden", "*.*")],
        )
        if path:
            err = validate_txt_path(path)
            if err:
                messagebox.showerror("Ongeldig bestand", err)
                return
            self.extra_names_path = path
            self.lbl_extra_names.config(text=path, style="HN.Card.TLabel")

    def choose_extra_medewerkers_names(self):
        path = filedialog.askopenfilename(
            title="Kies medewerkersbestand (.txt)",
            filetypes=[("Tekstbestanden", "*.txt"), ("Alle bestanden", "*.*")],
        )
        if path:
            err = validate_txt_path(path)
            if err:
                messagebox.showerror("Ongeldig bestand", err)
                return
            self.extra_medewerkers_names_path = path
            self.lbl_extra_medewerkers_names.config(text=path, style="HN.Card.TLabel")

    def choose_extra_locaties_names(self):
        path = filedialog.askopenfilename(
            title="Kies locatiesbestand (.txt)",
            filetypes=[("Tekstbestanden", "*.txt"), ("Alle bestanden", "*.*")],
        )
        if path:
            err = validate_txt_path(path)
            if err:
                messagebox.showerror("Ongeldig bestand", err)
                return
            self.extra_locaties_names_path = path
            self.lbl_extra_locaties_names.config(text=path, style="HN.Card.TLabel")

    def bring_to_front(self):
        self.lift()
        self.attributes("-topmost", True)
        self.focus_force()
        self.after(200, lambda: self.attributes("-topmost", False))

    # --- Run Anonymizer ---
    def run(self):
        if not self.input_file or not self.output_dir:
            messagebox.showerror("Fout", "Selecteer zowel een invoerbestand als een uitvoermap.")
            return
        
        try:
            size_mb = os.path.getsize(self.input_file) / (1024 * 1024)
        except OSError:
            size_mb = 0
        if size_mb > 50:
            proceed = messagebox.askokcancel(
                "Groot bestand",
                f"Dit bestand is ongeveer {size_mb:.0f} MB. Anonimiseren kan even "
                f"duren en de tool kan tijdelijk niet reageren. Wil je doorgaan?",
            )
            if not proceed:
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
        )

        self.progressbar.config(mode="indeterminate")
        self.progressbar.start(10)
        self.progress_label.config(text="Bezig met anonimiseren...")

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
            out_text, out_path, log_path, stats = controller.run()
            self.ui_queue.put(("run_success", out_text, out_path, log_path, stats))
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
                        self.progress_label.config(text=f"Initialisatie mislukt: {err}")
                        self.btn_run.config(text=f"Initialisatie mislukt: {err}")
                        messagebox.showerror("Initialisatie mislukt", f"Deduce initialisatie faalde:\n{err}")
                    else:
                        self.progress_label.config(text="Klaar voor gebruik.")
                        self.btn_run.config(state="normal", text="Anonimiseer bestand")

                elif msg[0] == "run_success":
                    _, out_text, out_path, log_path, stats = msg

                    try:
                        self.progressbar.stop()
                    except Exception:
                        pass
                    self.progressbar.config(mode="determinate")
                    self.progress_label.config(text="Klaar.")
                    
                    self.txt_out.configure(state="normal")
                    self.txt_out.delete("1.0", "end")
                    self.txt_out.insert("end", out_text) # already bounded by the controller
                    self.txt_out.configure(state="disabled")

                    summary = f"{stats.total} waarden geanonimiseerd"
                    details = "  • " + "  |  ".join(f"{k}: {v}" for k, v in sorted(stats.by_type.items()))
                    self.lbl_stats.config(text=f"{summary}   —   {details}")

                    messagebox.showinfo("Gereed", f"Geanonimiseerd bestand opgeslagen in:\n{out_path}")

                elif msg[0] == "run_error":
                    _, err = msg

                    try:
                        self.progressbar.stop()
                    except Exception:
                        pass
                    self.progressbar.config(mode="determinate")
                    self.progress_label.config(text="Anonimiseren mislukt.")

                    messagebox.showerror("Fout", f"Er is een fout opgetreden:\n{err}")

        except Empty:
            pass

        self.after(100, self._process_ui_queue)


if __name__ == "__main__":
    # Tip: start bij voorkeur met `python -m gui.app` vanaf project-root
    app = App()
    app.mainloop()
