from __future__ import annotations

import pytest

from hola_multiagent.config.settings import settings
from hola_multiagent.data.loader import DataLoader


@pytest.fixture(scope="session")
def dataframes():
    loader = DataLoader(data_source=settings.data_source, file_paths=settings.file_paths)
    return loader.as_agent_context(loader.load_all())
