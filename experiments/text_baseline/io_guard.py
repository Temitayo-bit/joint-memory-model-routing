"""Refuse to overwrite existing experiment outputs."""

from __future__ import annotations

from pathlib import Path


class OverwriteError(FileExistsError):
    """Output path already exists."""


def refuse_existing(path: Path) -> Path:
    if path.exists():
        raise OverwriteError("refusing to overwrite existing path: %s" % path)
    return path


def prepare_output_dir(path: Path) -> Path:
    refuse_existing(path)
    path.mkdir(parents=True)
    return path
