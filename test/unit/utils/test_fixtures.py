"""Common test fixtures and utilities."""

import os
import json
import tempfile
import random
import string

def get_test_data_path(filename):
    """Get the full path to a test data file.
    
    Args:
        filename (str): The filename within the test data directory
        
    Returns:
        str: Full path to the test data file
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    test_data_dir = os.path.join(base_dir, 'test_data')
    
    # Create directory if it doesn't exist
    if not os.path.exists(test_data_dir):
        os.makedirs(test_data_dir)
        
    return os.path.join(test_data_dir, filename)

def create_temp_json_file(data):
    """Create a temporary JSON file with the given data.
    
    Args:
        data (dict): The data to write to the file
        
    Returns:
        str: Path to the temporary file
    """
    fd, path = tempfile.mkstemp(suffix='.json')
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    return path

def random_string(length=10):
    """Generate a random string of letters and digits.
    
    Args:
        length (int): The length of the string to generate
        
    Returns:
        str: Random string
    """
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def create_test_target():
    """Create a test target with random domain.
    
    Returns:
        tuple: (target_value, target_type)
    """
    domain = f"{random_string(8)}.com"
    return domain, 'INTERNET_NAME'

def create_test_module(module_class, sf, opts=None):
    """Create and initialize a module instance for testing.
    
    Args:
        module_class: The module class
        sf (SpiderFoot): SpiderFoot instance
        opts (dict, optional): Module options
        
    Returns:
        object: Initialized module instance
    """
    if opts is None:
        opts = {}
        
    module = module_class()
    module.setup(sf, opts)
    return module
