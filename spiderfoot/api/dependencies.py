"""
Dependencies and helpers for SpiderFoot API
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from spiderfoot import SpiderFootDb, SpiderFoot, SpiderFootHelpers
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
            '__version__': __version__
        }
        self.defaultConfig = default_config.copy()
        dbh = SpiderFootDb(self.defaultConfig, init=True)
        sf = SpiderFoot(self.defaultConfig)
        self.config = sf.configUnserialize(dbh.configGet(), self.defaultConfig)
        self.loggingQueue = mp.Queue()
        self.log = logging.getLogger("spiderfoot.api")
    def get_config(self):
        return self.config
    def update_config(self, updates: dict):
        for key, value in updates.items():
            self.config[key] = value
        return self.config

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
