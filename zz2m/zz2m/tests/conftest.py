import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock

# Mock z2m_services before any imports that depend on it
mock_service_runner = MagicMock()
mock_service_runner.build_logger = lambda name: logging.getLogger(name)
sys.modules['z2m_services'] = MagicMock()
sys.modules['z2m_services.service_runner'] = mock_service_runner

# Add the z2m package root to sys.path so tests can import modules
project_root = Path(__file__).parent.parent.parent.parent
package_root = Path(__file__).parent.parent.parent
zmw_lib_root = str(project_root) + '/zzmw_lib'
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(package_root))
sys.path.insert(0, str(zmw_lib_root))
