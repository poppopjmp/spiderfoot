"""
Helper functions for SpiderFoot test modules.
Provides utilities for patching modules to fix common test issues.
"""

def patch_module_log_property(module):
    """
    Dynamically patch a SpiderFoot module to add a log property setter.
    This allows tests to replace the logger with a mock object.
    
    Args:
        module: SpiderFoot module instance to patch
        
    Returns:
        The patched module
    """
    # First check if module needs patching
    module_class = module.__class__
    
    # Check if the log property is already settable
    try:
        # Attempt to set the log property to test if it's settable
        original_log = module.log
        module.log = original_log
        return module  # If we get here, no patching needed
    except AttributeError:
        # Need to patch the class
        pass
        
    # Store the original log property getter
    for base in module_class.__mro__:
        if 'log' in base.__dict__:
            original_property = base.__dict__['log']
            original_getter = original_property.fget
            break
    else:
        # If we can't find the property, can't patch
        raise ValueError(f"Could not find log property in {module_class.__name__}")
            
    # Define a new property with both getter and setter
    def log_getter(self):
        if hasattr(self, '_mock_log'):
            return self._mock_log
        return original_getter(self)
        
    def log_setter(self, value):
        self._mock_log = value
        
    # Apply the new property to the class
    setattr(module_class, 'log', property(log_getter, log_setter))
    
    return module
