"""
Dependencies and helpers for SpiderFoot API
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from spiderfoot.db import SpiderFootDb
from spiderfoot.sflib.core import SpiderFoot
from spiderfoot.helpers import SpiderFootHelpers
import multiprocessing as mp
import logging

security = HTTPBearer(auto_error=False)


class Config:
    def __init__(self):
        from spiderfoot import __version__
        default_config = {
            '__modules__': {},
            '__correlationrules__': [],
            '_debug': False,
            '__webaddr': '127.0.0.1',
            '__webport': '8001',
            '__webaddr_apikey': None,
            '__database': f"{SpiderFootHelpers.dataPath()}/spiderfoot.db",
            '__loglevel': 'INFO',
            '__logfile': '',
            '__version__': __version__,
            'scan_defaults': {},
            'workspace_defaults': {},
            'api_keys': [],
            'credentials': []
        }
        # Remove all in-memory stubs for real data usage
        # (do not set __modules__, __eventtypes__, __globaloptdescs__ here)
        self.defaultConfig = default_config.copy()
        dbh = SpiderFootDb(self.defaultConfig, init=True)
        sf = SpiderFoot(self.defaultConfig)
        self.config = sf.configUnserialize(dbh.configGet(), self.defaultConfig)
        self.loggingQueue = mp.Queue()
        self.log = logging.getLogger("spiderfoot.api")
        # Remove monkey-patch: rely on real SpiderFoot methods

    def get_config(self):
        return self.config

    def update_config(self, updates: dict):
        for key, value in updates.items():
            self.config[key] = value
        return self.config

    def set_config_option(self, key, value):
        self.config[key] = value

    def save_config(self):
        pass  # stub for test/compat

    def reload(self):
        pass  # stub for test/compat

    def validate_config(self, options):
        return True, []  # stub for test/compat

    def get_scan_defaults(self):
        return self.config.get('scan_defaults', {})

    def set_scan_defaults(self, options):
        self.config['scan_defaults'] = options

    def get_workspace_defaults(self):
        return self.config.get('workspace_defaults', {})

    def set_workspace_defaults(self, options):
        self.config['workspace_defaults'] = options

    def get_api_keys(self):
        return self.config.get('api_keys', [])

    def add_api_key(self, key_data):
        self.config.setdefault('api_keys', []).append(key_data)

    def delete_api_key(self, key_id):
        self.config['api_keys'] = [k for k in self.config.get('api_keys', []) if k.get('key') != key_id]

    def get_credentials(self):
        return self.config.get('credentials', [])

    def add_credential(self, cred_data):
        self.config.setdefault('credentials', []).append(cred_data)

    def delete_credential(self, cred_id):
        self.config['credentials'] = [c for c in self.config.get('credentials', []) if c.get('key') != cred_id]

    def replace_config(self, new_config):
        self.config = new_config
        # Ensure all required keys are present after replacement
        for key, value in self.defaultConfig.items():
            if key not in self.config:
                self.config[key] = value

    def get_module_config(self, module_name):
        return self.config.get('__modules__', {}).get(module_name)

    def update_module_config(self, module_name, new_config):
        modules = self.config.setdefault('__modules__', {})
        if module_name not in modules:
            raise KeyError("404: Module not found")
        modules[module_name] = new_config

    def scanResultDelete(self, scan_id):
        # Stub for test/compat: do nothing or remove from in-memory if implemented
        pass


app_config = None


def get_app_config():
    global app_config
    if app_config is None:
        app_config = Config()
    return app_config


async def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        return None
    config = get_app_config()
    api_key = config.get_config().get('__webaddr_apikey')
    if api_key and credentials.credentials != api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return credentials.credentials


async def optional_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        return None
    return await get_api_key(credentials)
