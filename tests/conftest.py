"""Shared fixtures: every simulation in the test suite runs at smoke size."""
import os

import pytest

os.environ.setdefault("ARRAYTX_SMOKE", "1")


@pytest.fixture(scope="session")
def fr2_sim():
    from arraytx import ArraySim, load_config
    return ArraySim(load_config("configs/fr2_4el_survey.yaml"))


@pytest.fixture(scope="session")
def anchor_sim():
    from arraytx import ArraySim, load_config
    return ArraySim(load_config("configs/sub6_1el_anchor.yaml"))
