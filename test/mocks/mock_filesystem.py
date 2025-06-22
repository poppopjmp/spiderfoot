"""
Mock filesystem operations for SpiderFoot tests.
"""
from unittest.mock import patch, mock_open

# Example usage in tests:
# with patch('builtins.open', mock_open(read_data='data')):
#     ...
