import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the parent directory to sys.path so tests can import modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))


@pytest.fixture(autouse=True)
def mock_runtime_state_cache():
    """Mock the runtime state cache to isolate tests from filesystem state."""
    with patch('notification_manager.runtime_state_cache_get', return_value=None), \
         patch('notification_manager.runtime_state_cache_set'):
        yield
