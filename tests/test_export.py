"""Markdown -> Word/PDF export.  Conversions run only where pandoc / LibreOffice
are available (CI installs neither), the path logic always."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from model_routing import export


def _has_pandoc() -> bool:
    try:
        export.pandoc_binary()
    except export.ExportError:
        return False
    return True


def _has_soffice() -> bool:
    try:
        export.soffice_binary()
    except export.ExportError:
        return False
    return True


def test_output_path_mirrors_docs(tmp_path: Path):
    root = tmp_path
    (root / "docs" / "experiments" / "exp9").mkdir(parents=True)
    src = root / "docs" / "experiments" / "exp9" / "paper.md"
    src.write_text("# x\n")
    out = root / "exports"
    assert export.output_path(src, root, out, "docx") == out / "exp9/paper.docx"
    plat = root / "docs" / "platform.md"
    plat.write_text("# p\n")
    assert export.output_path(plat, root, out, "pdf") == out / "platform.pdf"
    other = root / "README.md"
    other.write_text("# r\n")
    assert export.output_path(other, root, root / "exports", "pdf") == root / "exports/README.pdf"
    outside = tmp_path.parent / "elsewhere.md"
    assert (
        export.output_path(outside, root, root / "exports", "pdf") == root / "exports/elsewhere.pdf"
    )


def test_rejects_unknown_formats_and_missing_files(tmp_path: Path):
    with pytest.raises(export.ExportError):
        export.export([tmp_path / "x.md"], ["odt"], out_dir=tmp_path)
    if _has_pandoc():
        with pytest.raises(export.ExportError):
            export.export([tmp_path / "missing.md"], ["docx"], out_dir=tmp_path)


@pytest.mark.skipif(not _has_pandoc(), reason="pandoc not installed (uv sync --extra export)")
def test_markdown_to_docx_keeps_tables(tmp_path: Path):
    src = tmp_path / "doc.md"
    src.write_text("# Title\n\n| a | b |\n|---|---:|\n| x | 1 |\n\nSome **bold** text.\n")
    out = export.to_docx(src, tmp_path / "out" / "doc.docx")
    with zipfile.ZipFile(out) as z:
        body = z.read("word/document.xml").decode()
    assert "<w:tbl>" in body and "Title" in body and "bold" in body


@pytest.mark.skipif(not (_has_pandoc() and _has_soffice()), reason="needs pandoc and LibreOffice")
def test_export_writes_docx_and_pdf(tmp_path: Path):
    src = tmp_path / "doc.md"
    src.write_text("# Hello\n\nA paragraph.\n")
    written = export.export([src], ["docx", "pdf"], out_dir=tmp_path / "exports")
    assert [p.suffix for p in written] == [".docx", ".pdf"]
    assert written[1].read_bytes().startswith(b"%PDF")
    pdf_only = export.export([src], ["pdf"], out_dir=tmp_path / "pdf-only")
    assert [p.suffix for p in pdf_only] == [".pdf"]
    assert not list((tmp_path / "pdf-only").rglob("*.docx"))
