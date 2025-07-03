import cherrypy
from .routes import WebUiRoutes
from .security import setup_security_headers

def create_app(web_config, config, loggingQueue=None):
    setup_security_headers()
    return WebUiRoutes(web_config, config, loggingQueue)

def main():
    # Placeholder: load config and web_config as needed
    # Example usage:
    # app = create_app(web_config, config)
    # cherrypy.quickstart(app, config=cherrypy.config)
    pass

__all__ = ["create_app", "main"]
