# -*- coding: utf-8 -*-
"""
SpiderFoot Configuration Adapter

Adapter to integrate microservice-based configuration with existing SpiderFoot code.
Provides backward compatibility while enabling gradual migration to microservices.
"""

import logging
import os
from typing import Dict, Any, Optional
from copy import deepcopy

# Import service client
try:
    from .client import get_config_client, set_service_discovery_url
    _MICROSERVICES_AVAILABLE = True
except ImportError:
    _MICROSERVICES_AVAILABLE = False

logger = logging.getLogger(__name__)

class ConfigurationAdapter:
    """Adapter for microservice-based configuration management."""
    
    def __init__(self, use_microservices: bool = None, service_discovery_url: str = None):
        """Initialize configuration adapter.
        
        Args:
            use_microservices: Whether to use microservices (auto-detect if None)
            service_discovery_url: Service discovery URL
        """
        self.use_microservices = use_microservices
        if self.use_microservices is None:
            # Auto-detect based on environment variable
            self.use_microservices = os.getenv('USE_MICROSERVICES', 'false').lower() == 'true'
        
        self.service_discovery_url = service_discovery_url or os.getenv(
            'SERVICE_DISCOVERY_URL', 'http://localhost:8000'
        )
        
        # Check if microservices are actually available
        if self.use_microservices and not _MICROSERVICES_AVAILABLE:
            logger.warning("Microservices requested but client not available, falling back to monolithic mode")
            self.use_microservices = False
        
        if self.use_microservices:
            set_service_discovery_url(self.service_discovery_url)
            self.config_client = get_config_client()
        else:
            self.config_client = None
        
        # Local cache for configuration
        self._config_cache = {}
        self._fallback_config = {}
        
        logger.info(f"Configuration adapter initialized (microservices: {self.use_microservices})")
    
    def get_config(self, key: str = None, scope: str = "global", fallback: Any = None) -> Any:
        """Get configuration value(s).
        
        Args:
            key: Configuration key (if None, gets all configs for scope)
            scope: Configuration scope
            fallback: Fallback value if key not found
            
        Returns:
            Configuration value(s) or fallback
        """
        if self.use_microservices and self.config_client:
            try:
                result = self.config_client.get_config(key, scope)
                if result:
                    if key:
                        # Single key request
                        return result.get('value', fallback)
                    else:
                        # All configs request
                        return result.get('configs', {})
                else:
                    logger.warning(f"Failed to get config from microservice: {scope}:{key}")
            except Exception as e:
                logger.error(f"Error getting config from microservice: {e}")
        
        # Fallback to local cache or default
        if key:
            cache_key = f"{scope}:{key}"
            return self._config_cache.get(cache_key, fallback)
        else:
            # Return all configs for scope from cache
            prefix = f"{scope}:"
            return {
                k.replace(prefix, ""): v
                for k, v in self._config_cache.items()
                if k.startswith(prefix)
            }
    
    def set_config(self, key: str, value: Any, scope: str = "global", description: str = None) -> bool:
        """Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
            scope: Configuration scope
            description: Configuration description
            
        Returns:
            True if successful, False otherwise
        """
        # Always update local cache first
        cache_key = f"{scope}:{key}"
        self._config_cache[cache_key] = value
        
        if self.use_microservices and self.config_client:
            try:
                success = self.config_client.set_config(key, value, scope, description)
                if success:
                    logger.debug(f"Config updated via microservice: {scope}:{key}")
                    return True
                else:
                    logger.warning(f"Failed to update config via microservice: {scope}:{key}")
            except Exception as e:
                logger.error(f"Error setting config via microservice: {e}")
        
        # In monolithic mode or fallback, we just use the cache
        return True
    
    def update_configs(self, configs: Dict[str, Any], scope: str = "global") -> bool:
        """Update multiple configuration values.
        
        Args:
            configs: Dictionary of configuration key-value pairs
            scope: Configuration scope
            
        Returns:
            True if successful, False otherwise
        """
        # Update local cache
        for key, value in configs.items():
            cache_key = f"{scope}:{key}"
            self._config_cache[cache_key] = value
        
        if self.use_microservices and self.config_client:
            try:
                success = self.config_client.update_configs(configs, scope)
                if success:
                    logger.debug(f"Configs updated via microservice: {scope} ({len(configs)} items)")
                    return True
                else:
                    logger.warning(f"Failed to update configs via microservice: {scope}")
            except Exception as e:
                logger.error(f"Error updating configs via microservice: {e}")
        
        return True
    
    def delete_config(self, key: str, scope: str = "global") -> bool:
        """Delete configuration value.
        
        Args:
            key: Configuration key
            scope: Configuration scope
            
        Returns:
            True if successful, False otherwise
        """
        # Remove from local cache
        cache_key = f"{scope}:{key}"
        self._config_cache.pop(cache_key, None)
        
        if self.use_microservices and self.config_client:
            try:
                success = self.config_client.delete_config(key, scope)
                if success:
                    logger.debug(f"Config deleted via microservice: {scope}:{key}")
                    return True
                else:
                    logger.warning(f"Failed to delete config via microservice: {scope}:{key}")
            except Exception as e:
                logger.error(f"Error deleting config via microservice: {e}")
        
        return True
    
    def load_fallback_config(self, config_dict: Dict[str, Any], scope: str = "global"):
        """Load fallback configuration from a dictionary.
        
        Args:
            config_dict: Configuration dictionary
            scope: Configuration scope
        """
        for key, value in config_dict.items():
            cache_key = f"{scope}:{key}"
            if cache_key not in self._config_cache:
                self._config_cache[cache_key] = value
        
        self._fallback_config.update(config_dict)
        logger.debug(f"Loaded {len(config_dict)} fallback config items for scope: {scope}")
    
    def serialize_for_legacy(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize configuration for legacy SpiderFoot format.
        
        Args:
            config_dict: Modern configuration dictionary
            
        Returns:
            Legacy-formatted configuration dictionary
        """
        # Convert boolean values to integers for legacy compatibility
        legacy_config = {}
        for key, value in config_dict.items():
            if isinstance(value, bool):
                legacy_config[key] = 1 if value else 0
            elif isinstance(value, list):
                legacy_config[key] = ','.join(str(x) for x in value)
            else:
                legacy_config[key] = value
        
        return legacy_config
    
    def unserialize_from_legacy(self, legacy_config: Dict[str, Any], 
                               reference_config: Dict[str, Any]) -> Dict[str, Any]:
        """Unserialize configuration from legacy SpiderFoot format.
        
        Args:
            legacy_config: Legacy-formatted configuration
            reference_config: Reference configuration for type conversion
            
        Returns:
            Modern configuration dictionary
        """
        modern_config = {}
        
        for key, value in legacy_config.items():
            if key in reference_config:
                ref_value = reference_config[key]
                
                if isinstance(ref_value, bool):
                    modern_config[key] = str(value) == "1"
                elif isinstance(ref_value, int):
                    try:
                        modern_config[key] = int(value)
                    except (ValueError, TypeError):
                        modern_config[key] = ref_value
                elif isinstance(ref_value, list):
                    if isinstance(value, str):
                        modern_config[key] = [x.strip() for x in value.split(',') if x.strip()]
                    else:
                        modern_config[key] = ref_value
                else:
                    modern_config[key] = str(value)
            else:
                modern_config[key] = value
        
        return modern_config

# Global adapter instance
_config_adapter = None

def get_config_adapter() -> ConfigurationAdapter:
    """Get the global configuration adapter instance."""
    global _config_adapter
    if _config_adapter is None:
        _config_adapter = ConfigurationAdapter()
    return _config_adapter

def initialize_config_adapter(use_microservices: bool = None, 
                            service_discovery_url: str = None) -> ConfigurationAdapter:
    """Initialize the global configuration adapter."""
    global _config_adapter
    _config_adapter = ConfigurationAdapter(use_microservices, service_discovery_url)
    return _config_adapter