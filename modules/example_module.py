# Example of proper logging in a SpiderFoot module

from spiderfoot.logconfig import get_module_logger
from spiderfoot.plugin import SpiderFootPlugin

# Get a module-specific logger
log = get_module_logger(__name__)

class ExampleModule(SpiderFootPlugin):
    """Example module demonstrating proper logging"""
    
    # ...module code...
    
    def handleEvent(self, event):
        """Handle an event."""
        # Use the plugin's logger via the log property
        self.log.debug(f"Processing event: {event.eventType}")
        
        # Process event
        if some_condition:
            self.log.info(f"Found interesting data: {data}")
        
        if error_condition:
            self.log.error(f"Error processing event: {error}")
            
        # ...module code...
