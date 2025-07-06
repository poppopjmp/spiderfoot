"""
Module Manager for SpiderFoot

This module handles loading, management, and operations on SpiderFoot modules.
It provides a centralized interface for module-related functionality.
"""

import os
import sys
import logging
import importlib.util
import traceback
from typing import Dict, Any, List, Optional

from spiderfoot import SpiderFootHelpers


class ModuleManager:
    """Centralized module management for SpiderFoot."""
    
    def __init__(self):
        """Initialize the module manager."""
        self.log = logging.getLogger(f"spiderfoot.{__name__}")
        self.modules = {}
        self.correlation_rules = []
        
    def load_modules(self, modules_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Load all SpiderFoot modules from the modules directory.
        
        Args:
            modules_dir: Optional path to modules directory
            
        Returns:
            Dict containing loaded modules
        """
        if modules_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            modules_dir = os.path.join(script_dir, '../../modules')
        
        self.log.info(f"Loading modules from: {modules_dir}")
        
        try:
            # Try using SpiderFootHelpers first
            modules = SpiderFootHelpers.loadModulesAsDict(modules_dir, ['sfp_template.py'])
            self.modules = modules
            self.log.info(f"Successfully loaded {len(modules)} modules using SpiderFootHelpers")
            return modules
        except Exception as e:
            self.log.warning(f"SpiderFootHelpers.loadModulesAsDict failed: {e}")
            # Fall back to custom loader
            return self._load_modules_custom(modules_dir)
    
    def _load_modules_custom(self, modules_dir: str) -> Dict[str, Any]:
        """
        Custom module loader as fallback.
        
        Args:
            modules_dir: Path to modules directory
            
        Returns:
            Dict containing loaded modules
        """
        sf_modules = {}
        
        try:
            # Add modules directory to Python path
            if modules_dir not in sys.path:
                sys.path.insert(0, modules_dir)
            
            # Get all SpiderFoot module files
            module_files = [f for f in os.listdir(modules_dir) 
                           if f.startswith('sfp_') and f.endswith('.py') and f != 'sfp_template.py']
            
            self.log.info(f"Custom loader: attempting to load {len(module_files)} modules")
            
            loaded_count = 0
            failed_count = 0
            
            for module_file in module_files:
                try:
                    module_name = module_file[:-3]  # Remove .py extension
                    spec = importlib.util.spec_from_file_location(
                        module_name, os.path.join(modules_dir, module_file)
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # Extract module information
                        if hasattr(module, module_name):
                            mod_class = getattr(module, module_name)
                            if hasattr(mod_class, '__doc__'):
                                sf_modules[module_name] = {
                                    'descr': mod_class.__doc__ or 'No description',
                                    'group': getattr(mod_class, 'group', 'Unknown'),
                                    'module': module,
                                    'class': mod_class
                                }
                                loaded_count += 1
                            else:
                                self.log.warning(f"Module {module_name} has no documentation")
                                failed_count += 1
                        else:
                            self.log.warning(f"Module {module_name} has no matching class")
                            failed_count += 1
                            
                except Exception as e:
                    self.log.error(f"Failed to load module {module_file}: {e}")
                    failed_count += 1
            
            self.log.info(f"Custom loader results: {loaded_count} loaded, {failed_count} failed")
            
        except Exception as e:
            self.log.error(f"Custom module loader failed: {e}")
            self.log.error(f"Traceback: {traceback.format_exc()}")
        
        self.modules = sf_modules
        return sf_modules
    
    def load_correlation_rules(self, correlations_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Load correlation rules from the correlations directory.
        
        Args:
            correlations_dir: Optional path to correlations directory
            
        Returns:
            List of loaded correlation rules
        """
        if correlations_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            correlations_dir = os.path.join(script_dir, '../../correlations')
        
        try:
            from spiderfoot.correlation.rule_loader import RuleLoader
            
            correlation_rules = []
            if os.path.exists(correlations_dir):
                loader = RuleLoader(correlations_dir)
                rules = loader.load_rules()
                errors = loader.get_errors()
                
                if errors:
                    for fname, err in errors:
                        self.log.warning(f"Failed to load correlation rule {fname}: {err}")
                        
                correlation_rules = rules
                
            self.correlation_rules = correlation_rules
            self.log.info(f"Loaded {len(correlation_rules)} correlation rules")
            return correlation_rules
            
        except Exception as e:
            self.log.warning(f"Failed to load correlation rules: {e}")
            self.correlation_rules = []
            return []
    
    def get_modules(self) -> Dict[str, Any]:
        """
        Get the currently loaded modules.
        
        Returns:
            Dict containing loaded modules
        """
        return self.modules
    
    def get_correlation_rules(self) -> List[Dict[str, Any]]:
        """
        Get the currently loaded correlation rules.
        
        Returns:
            List of loaded correlation rules
        """
        return self.correlation_rules
    
    def list_modules(self) -> List[str]:
        """
        List all available module names.
        
        Returns:
            List of module names
        """
        return sorted(self.modules.keys())
    
    def get_module_info(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific module.
        
        Args:
            module_name: Name of the module
            
        Returns:
            Dict containing module information or None if not found
        """
        return self.modules.get(module_name)
    
    def get_modules_by_group(self, group: str) -> List[str]:
        """
        Get modules by group.
        
        Args:
            group: Group name to filter by
            
        Returns:
            List of module names in the specified group
        """
        return [
            name for name, info in self.modules.items()
            if info.get('group', '').lower() == group.lower()
        ]
    
    def get_modules_by_usecase(self, usecase: str) -> List[str]:
        """
        Get modules by use case.
        
        Args:
            usecase: Use case to filter by ('all', 'footprint', 'investigate', 'passive')
            
        Returns:
            List of module names matching the use case
        """
        if usecase.lower() == 'all':
            return self.list_modules()
        
        # Capitalize first letter for matching
        usecase_formatted = usecase[0].upper() + usecase[1:].lower()
        
        matching_modules = []
        for name, info in self.modules.items():
            groups = info.get('group', '')
            if isinstance(groups, str):
                groups = [groups]
            elif not isinstance(groups, list):
                groups = []
                
            if usecase_formatted in groups:
                matching_modules.append(name)
        
        return matching_modules
    
    def validate_modules(self, module_list: List[str]) -> List[str]:
        """
        Validate that all modules in the list exist.
        
        Args:
            module_list: List of module names to validate
            
        Returns:
            List of valid module names
        """
        valid_modules = []
        for module_name in module_list:
            if module_name in self.modules:
                valid_modules.append(module_name)
            else:
                self.log.warning(f"Module '{module_name}' not found")
        
        return valid_modules
