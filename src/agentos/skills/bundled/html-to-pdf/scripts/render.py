"""Render HTML (file or URL) to PDF via WeasyPrint."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

PAGE_SIZES = {
    "letter": "Letter",
    "a4": "A4",
    "a3": "A3",
    "legal": "Legal",
}


def _is_url(spec: str) -> bool:
    parsed = urlparse(spec)
    return parsed.scheme in {"http", "https", "file"}


class _CssWarningCollector(logging.Handler):
    """Collects WeasyPrint's own parse warnings without touching global logging.

    WeasyPrint's CSS parser follows CSS error-recovery rules: an unrecognized
    property value (e.g. a typo'd ``--page-size Letterr``) is silently dropped,
    and rendering falls back to the UA default page size (A4) with no
    exception and nothing on stderr — the PDF is written and the script exits
    0 as if the requested size had been honoured. WeasyPrint does report the
    drop, but only via its own ``weasyprint`` logger, so that is what has to
    be inspected to tell a genuine size from a silently ignored one.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def render(html_spec: str, out_path: Path, page_size: str | None) -> None:
    try:
        from weasyprint import CSS, HTML
    except ImportError as exc:  # pragma: no cover - covered by --help path
        print(
            "error: weasyprint is not installed — `pip install 'use-agent-os[document-extras]'`",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    if _is_url(html_spec):
        html = HTML(url=html_spec)
    else:
        html_path = Path(html_spec)
        if not html_path.is_file():
            print(f"error: html source {html_path} not found", file=sys.stderr)
            raise SystemExit(2)
        html = HTML(filename=str(html_path))

    stylesheets: list[CSS] = []
    if page_size:
        normalized = PAGE_SIZES.get(page_size.lower(), page_size)
        collector = _CssWarningCollector()
        weasyprint_logger = logging.getLogger("weasyprint")
        weasyprint_logger.addHandler(collector)
        try:
            css = CSS(string=f"@page {{ size: {normalized}; }}")
        finally:
            weasyprint_logger.removeHandler(collector)
        if collector.messages:
            print(
                f"error: invalid --page-size {page_size!r} — " + "; ".join(collector.messages),
                file=sys.stderr,
            )
            raise SystemExit(2)
        stylesheets.append(css)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    html.write_pdf(target=str(out_path), stylesheets=stylesheets or None)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render HTML to PDF via WeasyPrint.")
    parser.add_argument("--html", required=True, help="HTML file path or URL")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--page-size",
        default=None,
        help="Page size override (Letter, A4, A3, Legal, or any valid CSS size value)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    render(args.html, args.out, args.page_size)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
