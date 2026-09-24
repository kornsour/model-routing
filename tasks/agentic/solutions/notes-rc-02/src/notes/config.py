"""Per-user defaults from an INI file (``.notesrc``).

The file is INI as Python's :mod:`configparser` reads it with its default
settings: ``[section]`` headers; ``option = value`` or ``option: value``
lines; whole-line comments starting with ``;`` or ``#``; a value may
continue on following lines that are indented; option names are
case-insensitive (reported in lowercase); ``%(name)s`` inside a value is
replaced by the option ``name`` from the same section (or from
``[DEFAULT]``); and every option in ``[DEFAULT]`` is inherited by every
other section.

:func:`load_config` returns ``{section: {option: value}}`` with ``DEFAULT``
folded into each section rather than listed as a section of its own. The
``notes`` CLI reads the ``[notes]`` section: ``db`` (path of the store, used
when ``--db`` is not given), ``page_size`` (the default for
``list --page-size``) and ``tags`` (comma-separated tags added to every
``add``).
"""

from __future__ import annotations

import configparser
from pathlib import Path


def load_config(path: str | Path) -> dict[str, dict[str, str]]:
    parser = configparser.ConfigParser()
    with Path(path).open() as handle:
        parser.read_file(handle)
    # A section proxy already folds in [DEFAULT] and applies interpolation.
    return {name: dict(parser[name]) for name in parser.sections()}


def notes_defaults(path: str | Path) -> dict[str, str]:
    """The effective ``[notes]`` section of ``path``, or ``{}`` if there is no such file."""
    rc = Path(path)
    if not rc.exists():
        return {}
    return load_config(rc).get("notes", {})
