# tests/conftest.py
"""
Pytest Configuration
====================

Shared fixtures and configuration for all tests
"""

import pytest
import sys
import os

# Add src to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'src'))


@pytest.fixture
def mock_config():
    """Mock configuration object"""
    from unittest.mock import Mock
    
    config = Mock()
    config.LOG_LEVEL = 'INFO'
    config.FUTURES_LEVERAGE = 10
    config.MIN_MARGIN_USD = 5.0
    config.MAX_MARGIN_USD = 50.0
    config.MIN_RR_RATIO = 1.2
    config.USE_KELLY_ADJUSTMENT = True
    config.KELLY_MAX_FRACTION = 0.15
    config.QUALITY_MARGIN_MULTIPLIERS = {
        'A': 1.5,
        'B': 1.0,
        'C': 0.6,
        'D': 0.0
    }
    
    return config
