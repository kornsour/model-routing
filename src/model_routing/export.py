"""Export Markdown documents (papers, findings) to Word and PDF.

    make docs-export                                   # every docs/paper/*.md
    make docs-export DOCS="docs/paper/exp06-results.md" FORMATS=docx

Markdown -> .docx goes through pandoc: a ``pandoc`` on the PATH if there is
one, else the copy bundled with the ``pypandoc-binary`` wheel (``uv sync
--extra export``).  .docx -> .pdf goes through LibreOffice in headless mode,
so the PDF is exactly the Word document; no LaTeX is needed.

Output lands in ``exports/`` at the repository root (git-ignored), mirroring
the source path below ``docs/``: ``docs/paper/x.md`` -> ``exports/paper/x.docx``.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

FORMATS = ("docx", "pdf")
DEFAULT_GLOB = "docs/paper/*.md"
# Pipe tables, fenced code, strikeout and autolinks as written in this repo.
PANDOC_FROM = "gfm"

_SOFFICE_CANDIDATES = (
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)


class ExportError(RuntimeError):
    pass


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise ExportError("could not find the repository root (no pyproject.toml)")


def pandoc_binary() -> str:
    found = shutil.which("pandoc")
    if found:
        return found
    try:
        import pypandoc  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ExportError(
            "pandoc is not installed: run `uv sync --extra dev --extra export` "
            "(bundles pandoc) or install pandoc"
        ) from exc
    return str(pypandoc.get_pandoc_path())


def soffice_binary() -> str:
    for candidate in _SOFFICE_CANDIDATES:
        path = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if path:
            return path
    raise ExportError(
        "LibreOffice was not found (needed for PDF): install it, or export docx only "
        "with FORMATS=docx"
    )


def output_path(source: Path, root: Path, out_dir: Path, fmt: str) -> Path:
    source = source.resolve()
    try:
        rel = source.relative_to(root / "docs")
    except ValueError:
        try:
            rel = source.relative_to(root)
        except ValueError:
            rel = Path(source.name)
    return out_dir / rel.with_suffix(f".{fmt}")


def to_docx(source: Path, target: Path, *, pandoc: str | None = None) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        pandoc or pandoc_binary(),
        str(source),
        "--from",
        PANDOC_FROM,
        "--to",
        "docx",
        "--output",
        str(target),
        # Relative links and images resolve against the source file.
        "--resource-path",
        str(source.parent),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ExportError(f"pandoc failed on {source}: {proc.stderr.strip()[-500:]}")
    return target


def to_pdf(docx: Path, target: Path, *, soffice: str | None = None) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    # A private profile lets this run while LibreOffice is open in the GUI.
    with tempfile.TemporaryDirectory(prefix="lo-profile-") as profile:
        cmd = [
            soffice or soffice_binary(),
            f"-env:UserInstallation=file://{profile}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(target.parent),
            str(docx),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
    produced = target.parent / f"{docx.stem}.pdf"
    if proc.returncode != 0 or not produced.exists():
        raise ExportError(f"LibreOffice failed on {docx}: {(proc.stderr or proc.stdout)[-500:]}")
    if produced != target:
        produced.replace(target)
    return target


def export(
    sources: Iterable[Path], formats: Iterable[str] = FORMATS, *, out_dir: Path | None = None
) -> list[Path]:
    formats = list(formats)
    unknown = sorted(set(formats) - set(FORMATS))
    if unknown:
        raise ExportError(f"unknown format(s) {unknown}; choose from {list(FORMATS)}")
    root = repo_root()
    out_dir = out_dir or root / "exports"
    written: list[Path] = []
    pandoc = pandoc_binary()
    soffice = soffice_binary() if "pdf" in formats else None
    for source in sources:
        source = Path(source)
        if not source.is_file():
            raise ExportError(f"no such file: {source}")
        docx = output_path(source, root, out_dir, "docx")
        to_docx(source, docx, pandoc=pandoc)
        if "docx" in formats:
            written.append(docx)
        if "pdf" in formats:
            written.append(to_pdf(docx, output_path(source, root, out_dir, "pdf"), soffice=soffice))
        if "docx" not in formats:
            docx.unlink(missing_ok=True)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Export Markdown docs to Word and PDF.")
    ap.add_argument("docs", nargs="*", help=f"Markdown files (default: {DEFAULT_GLOB})")
    ap.add_argument("--formats", default=",".join(FORMATS), help="comma-separated: docx,pdf")
    ap.add_argument("--out", type=Path, help="output directory (default: exports/)")
    args = ap.parse_args(argv)
    root = repo_root()
    sources = [Path(d) for d in args.docs] or sorted(root.glob(DEFAULT_GLOB))
    if not sources:
        print(f"nothing to export (no files match {DEFAULT_GLOB})", file=sys.stderr)
        return 1
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    try:
        for path in export(sources, formats, out_dir=args.out):
            print(path)
    except ExportError as exc:
        print(f"export failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
