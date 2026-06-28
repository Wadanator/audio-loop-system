"""Runtime path helpers for the refactored package layout."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def project_root() -> Path:
    return PROJECT_ROOT


def runtime_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)
