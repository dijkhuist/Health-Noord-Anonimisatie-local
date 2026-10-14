import os
import re
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime
from time import monotonic
from typing import Callable, Optional, Set

from src.hn_ano_tool.app.enums import DEDUCE_FILTER_GROUPS
from src.hn_ano_tool.engine.core import Anonymizer
from src.hn_ano_tool.engine.stats import RunStats
from src.hn_ano_tool.io.text_io import iter_lines_smart


class ProcessingCancelled(Exception):
    """Raised when a run is cancelled before its output is published."""


@dataclass
class Settings:
    input_file: str
    output_dir: str
    log_dir: Optional[str]
    extra_names_path: Optional[str] = None
    extra_names_paths: dict[str, str] = field(default_factory=dict)
    disabled_groups: Optional[Set[str]] = None
    whitelist_path: Optional[str] = None
  

def _replacement_totals(stats) -> tuple[int, int]:
    deduce_total = sum(
        count for key, count in stats.by_type.items() if not key.startswith("extra ")
    )
    extra_total = sum(
        count for key, count in stats.by_type.items() if key.startswith("extra ")
    )
    return deduce_total, extra_total


def _sanitize_error_message(error: Exception, settings: Settings) -> str:
    message = str(error).splitlines()[0][:300]
    replacements = [
        (settings.input_file, os.path.basename(settings.input_file)),
        (settings.output_dir, "[uitvoermap]"),
        (settings.log_dir or "", "[logmap]"),
        (settings.whitelist_path or "", "[whitelistbestand]"),
    ]
    replacements.extend(
        (path, "[extra lijst]") for path in (settings.extra_names_paths or {}).values()
    )
    if settings.extra_names_path:
        replacements.append((settings.extra_names_path, "[extra lijst]"))

    for path, replacement in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        if path:
            message = re.sub(re.escape(path), replacement, message, flags=re.IGNORECASE)
    return message or type(error).__name__


def _format_run_log(
    *,
    status: str,
    started_at: datetime,
    duration_seconds: float,
    input_file: str,
    input_bytes: int,
    processed_bytes: int,
    output_file: str | None,
    active_filters: list[str],
    disabled_filters: list[str],
    whitelist_used: bool,
    extra_lists_used: list[str],
    stats: RunStats,
    error: Exception | None = None,
    settings: Settings | None = None,
) -> str:
    deduce_total, extra_total = _replacement_totals(stats)
    lines = [
        "Anonymisatie-run",
        f"Status: {status}",
        f"Starttijd: {started_at.isoformat(timespec='seconds')}",
        f"Duur seconden: {duration_seconds:.1f}",
        f"Invoerbestand: {os.path.basename(input_file)}",
        f"Invoergrootte bytes: {input_bytes}",
        f"Verwerkte invoerbytes: {processed_bytes}",
        f"Uitvoerbestand: {output_file or 'Niet aangemaakt'}",
        f"Actieve filtergroepen: {', '.join(active_filters) if active_filters else 'Geen'}",
        f"Uitgeschakelde filtergroepen: {', '.join(disabled_filters) if disabled_filters else 'Geen'}",
        f"Whitelist gebruikt: {'Ja' if whitelist_used else 'Nee'}",
        f"Extra lijsten gebruikt: {', '.join(extra_lists_used) if extra_lists_used else 'Nee'}",
        f"Deduce-vervangingen: {deduce_total}",
        f"Extra-lijstvervangingen: {extra_total}",
        f"Totaal vervangingen: {deduce_total + extra_total}",
        "Vervangingen per type:",
    ]
    for k, v in sorted(stats.by_type.items()):
        lines.append(f"  {k}: {v}")
    if error is not None:
        message = _sanitize_error_message(error, settings) if settings else str(error)[:300]
        lines.extend(
            [
                f"Foutcategorie: {type(error).__name__}",
                f"Foutmelding: {message}",
            ]
        )
    return "\n".join(lines) + "\n"


def _write_log_atomically(log_path: str, log_dir: str, stem: str, contents: str) -> None:
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{stem}_log_",
        suffix=".tmp",
        dir=log_dir,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as log_file:
            log_file.write(contents)
        os.replace(temporary_path, log_path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


class MainController:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_event: threading.Event | None = None,
        phase_callback: Callable[[str], None] | None = None,
    ) -> tuple[str, str, str, object]:
        """
        Executes anonymization using settings, streaming input->output.
        Returns: (preview_text, output_path, log_path, stats)
        """
        run_started = monotonic()
        started_at = datetime.now()
        extra_names_paths = dict(self.settings.extra_names_paths or {})

        # Backward compatibility (alleen als het echt een string pad is)
        if (
            not extra_names_paths
            and isinstance(self.settings.extra_names_path, str)
            and self.settings.extra_names_path
        ):
            extra_names_paths["patient"] = self.settings.extra_names_path

        # ensure output/log dirs
        os.makedirs(self.settings.output_dir, exist_ok=True)
        log_dir = self.settings.log_dir or self.settings.output_dir
        os.makedirs(log_dir, exist_ok=True)
        total_input_bytes = os.path.getsize(self.settings.input_file)
        input_progress = {"bytes": 0}

        def record_input_progress(processed_bytes: int, _total_bytes: int) -> None:
            input_progress["bytes"] = processed_bytes

        # build output/log paths
        base = os.path.basename(self.settings.input_file)
        stem, _ = os.path.splitext(base)
        timestamp = started_at.strftime("%Y_%m_%d_H%H_M%M_S%S_%f")
        out_path = os.path.join(self.settings.output_dir, f"{stem}_anonymized_{timestamp}.txt")
        log_path = os.path.join(log_dir, f"{stem}_log_{timestamp}.txt")
        active_filters = [
            label
            for key, label in DEDUCE_FILTER_GROUPS.items()
            if key not in (self.settings.disabled_groups or set())
        ]
        disabled_filters = [
            label
            for key, label in DEDUCE_FILTER_GROUPS.items()
            if key in (self.settings.disabled_groups or set())
        ]
        extra_list_names = {
            "patient": "Patiëntenlijst",
            "patiënt": "Patiëntenlijst",
            "medewerker": "Medewerkerslijst",
            "locatie": "Locatielijst",
        }
        extra_lists_used = sorted(
            {
                extra_list_names.get(key.casefold(), "Extra lijst")
                for key, path in extra_names_paths.items()
                if path
            }
        )

        # Stream: anonymize line-by-line and write each chunk straight to disk,
        # keeping only a small preview (and the stats) in memory.
        PREVIEW_LIMIT = 20000
        stats = RunStats()
        preview_parts = []
        preview_len = 0
        total_written = 0

        def raise_if_cancelled() -> None:
            if cancel_event and cancel_event.is_set():
                raise ProcessingCancelled("Anonimiseren is geannuleerd.")

        output_fd, temporary_output_path = tempfile.mkstemp(
            prefix=f".{stem}_anonymized_",
            suffix=".tmp",
            dir=self.settings.output_dir,
        )
        os.close(output_fd)
        temporary_log_path = None

        try:
            raise_if_cancelled()
            if phase_callback:
                phase_callback("Tekst inlezen en anonimiseren")
            anon = Anonymizer(
                extra_names_paths=extra_names_paths,
                disabled=self.settings.disabled_groups,
                whitelist_path=self.settings.whitelist_path,
            )
            with open(temporary_output_path, "w", encoding="utf-8", newline="") as f:
                chunks = iter(
                    anon.anonymize_stream(
                        iter_lines_smart(self.settings.input_file, record_input_progress), stats
                    )
                )
                while True:
                    raise_if_cancelled()
                    try:
                        out_chunk = next(chunks)
                    except StopIteration:
                        break
                    raise_if_cancelled()
                    f.write(out_chunk)
                    total_written += len(out_chunk)
                    if preview_len < PREVIEW_LIMIT:
                        preview_parts.append(out_chunk)
                        preview_len += len(out_chunk)
                    if progress_callback:
                        progress_callback(input_progress["bytes"], total_input_bytes)

            raise_if_cancelled()
            if phase_callback:
                phase_callback("Uitvoer en logbestand opslaan")
            preview_text = "".join(preview_parts)[:PREVIEW_LIMIT]
            if total_written > len(preview_text):
                preview_text += (
                    "\n\n... (voorbeeld ingekort - de volledige uitvoer "
                    "staat in het opgeslagen bestand)"
                )

            log_fd, temporary_log_path = tempfile.mkstemp(
                prefix=f".{stem}_log_",
                suffix=".tmp",
                dir=log_dir,
            )
            os.close(log_fd)
            with open(temporary_log_path, "w", encoding="utf-8", newline="") as lf:
                lf.write(
                    _format_run_log(
                        status="Geslaagd",
                        started_at=started_at,
                        duration_seconds=monotonic() - run_started,
                        input_file=self.settings.input_file,
                        input_bytes=total_input_bytes,
                        processed_bytes=total_input_bytes,
                        output_file=os.path.basename(out_path),
                        active_filters=active_filters,
                        disabled_filters=disabled_filters,
                        whitelist_used=bool(self.settings.whitelist_path),
                        extra_lists_used=extra_lists_used,
                        stats=stats,
                    )
                )

            raise_if_cancelled()
            os.replace(temporary_output_path, out_path)
            temporary_output_path = None
            os.replace(temporary_log_path, log_path)
            temporary_log_path = None
            if progress_callback:
                progress_callback(total_input_bytes, total_input_bytes)
        except ProcessingCancelled as error:
            try:
                _write_log_atomically(
                    log_path,
                    log_dir,
                    stem,
                    _format_run_log(
                        status="Geannuleerd",
                        started_at=started_at,
                        duration_seconds=monotonic() - run_started,
                        input_file=self.settings.input_file,
                        input_bytes=total_input_bytes,
                        processed_bytes=input_progress["bytes"],
                        output_file=None,
                        active_filters=active_filters,
                        disabled_filters=disabled_filters,
                        whitelist_used=bool(self.settings.whitelist_path),
                        extra_lists_used=extra_lists_used,
                        stats=stats,
                        error=error,
                        settings=self.settings,
                    ),
                )
            except OSError:
                pass
            raise
        except Exception as error:
            try:
                _write_log_atomically(
                    log_path,
                    log_dir,
                    stem,
                    _format_run_log(
                        status="Mislukt",
                        started_at=started_at,
                        duration_seconds=monotonic() - run_started,
                        input_file=self.settings.input_file,
                        input_bytes=total_input_bytes,
                        processed_bytes=input_progress["bytes"],
                        output_file=None,
                        active_filters=active_filters,
                        disabled_filters=disabled_filters,
                        whitelist_used=bool(self.settings.whitelist_path),
                        extra_lists_used=extra_lists_used,
                        stats=stats,
                        error=error,
                        settings=self.settings,
                    ),
                )
            except OSError:
                pass
            raise
        finally:
            for temporary_path in (temporary_output_path, temporary_log_path):
                if temporary_path and os.path.exists(temporary_path):
                    os.remove(temporary_path)

        return preview_text, out_path, log_path, stats