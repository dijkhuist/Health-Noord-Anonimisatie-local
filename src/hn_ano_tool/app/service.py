import os
from dataclasses import dataclass, field
from datetime import datetime
from src.hn_ano_tool.engine.core import Anonymizer
from typing import Optional, Set
from src.hn_ano_tool.engine.stats import RunStats
from src.hn_ano_tool.io.text_io import iter_lines_smart

@dataclass
class Settings:
    input_file: str
    output_dir: str
    log_dir: Optional[str]
    extra_names_path: Optional[str] = None
    extra_names_paths: dict[str, str] = field(default_factory=dict)
    disabled_groups: Optional[Set[str]] = None
  

def _format_stats_log(stats) -> str:
    lines = [
        "Anonymization summary",
        f"Timestamp: {datetime.now().isoformat(timespec='seconds')}",
        f"Total items changed: {stats.total}",
    ]
    for k, v in sorted(stats.by_type.items()):
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"


class MainController:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self) -> tuple[str, str, str, object]:
        """
        Executes anonymization using settings, streaming input->output.
        Returns: (preview_text, output_path, log_path, stats)
        """
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

        anon = Anonymizer(
            extra_names_paths=extra_names_paths,
            disabled=self.settings.disabled_groups,
        )

        # build output/log paths
        base = os.path.basename(self.settings.input_file)
        stem, _ = os.path.splitext(base)
        time = datetime.now().strftime("%Y_%m_%d_H%H_M%M_S%S")
        out_path = os.path.join(self.settings.output_dir, f"{stem}_anonymized_{time}.txt")
        log_path = os.path.join(log_dir, f"{stem}_log_{time}.txt")

        # Stream: anonymize line-by-line and write each chunk straight to disk,
        # keeping only a small preview (and the stats) in memory.
        PREVIEW_LIMIT = 20000
        stats = RunStats()
        preview_parts = []
        preview_len = 0
        total_written = 0

        with open(out_path, "w", encoding="utf-8", newline="") as f:
            for out_chunk in anon.anonymize_stream(
                iter_lines_smart(self.settings.input_file), stats
            ):
                f.write(out_chunk)
                total_written += len(out_chunk)
                if preview_len < PREVIEW_LIMIT:
                    preview_parts.append(out_chunk)
                    preview_len += len(out_chunk)

        preview_text = "".join(preview_parts)[:PREVIEW_LIMIT]
        if total_written > len(preview_text):
            preview_text += (
                "\n\n... (voorbeeld ingekort - de volledige uitvoer "
                "staat in het opgeslagen bestand)"
            )
        
        with open(log_path, "w", encoding="utf-8", newline="") as lf:
            lf.write(_format_stats_log(stats))

        return preview_text, out_path, log_path, stats