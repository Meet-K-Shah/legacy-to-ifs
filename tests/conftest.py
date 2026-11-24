"""Shared fixtures: generate a small deterministic dataset in a temp project and run all three mock loads once."""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ifs_migration.config import Paths  # noqa: E402
from ifs_migration.datagen.generate import generate  # noqa: E402
from ifs_migration.pipeline import run_mock  # noqa: E402


@pytest.fixture(scope="session")
def project(tmp_path_factory):
    root = tmp_path_factory.mktemp("proj")
    shutil.copytree(ROOT / "sql", root / "sql")
    paths = Paths(root)
    generate(paths, scale=0.1, seed=11, verbose=False)
    summaries = {m: run_mock(paths, m, backend="sqlite", verbose=False) for m in (1, 2, 3)}
    return paths, summaries
