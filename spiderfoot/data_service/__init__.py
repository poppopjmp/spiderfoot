"""
SpiderFoot Data Service - Abstract data access layer.

Decouples modules from direct database access by providing a
service interface (local or remote) that handles all persistence.
This enables modules to run as independent services without
holding database connections.
"""

from spiderfoot.data_service.base import DataService, DataServiceConfig
from spiderfoot.data_service.local import LocalDataService
from spiderfoot.data_service.factory import create_data_service

__all__ = [
    'DataService',
    'DataServiceConfig',
    'LocalDataService',
    'create_data_service',
]
