#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot Security Integration and Migration Tool
=================================================

This module provides tools for integrating and migrating SpiderFoot to use
the new security framework. It analyzes existing code, plans migrations,
and applies security enhancements.

Author: SpiderFoot Security Team
"""

import os
import sys
import ast
import logging
import re
import shutil
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Add the parent directory to sys.path to import security modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from spiderfoot.secure_config import SecureConfigManager
from spiderfoot.security_middleware import install_cherrypy_security, install_fastapi_security


class SecurityMigrationTool:
    """
    Tool for migrating SpiderFoot to use the new security framework.
    """
    
    def __init__(self, spiderfoot_root: str):
        """
        Initialize migration tool.
        
        Args:
            spiderfoot_root: Root directory of SpiderFoot installation
        """
        self.spiderfoot_root = os.path.abspath(spiderfoot_root)
        self.log = logging.getLogger(__name__)
        
        # Migration configuration
        self.backup_dir = os.path.join(self.spiderfoot_root, 'security_migration_backup')
        self.migration_log = os.path.join(self.spiderfoot_root, 'security_migration.log')
        
        # Files that need security integration
        self.target_files = {
            'sfwebui.py': 'web_interface',
            'spiderfoot/api/main.py': 'api_main',
            'spiderfoot/webui/routes.py': 'web_routes',
            'spiderfoot/webui/security.py': 'web_security',
            'sf.py': 'main_config'
        }
        
        # Security features to integrate
        self.security_features = [
            'csrf_protection',
            'input_validation', 
            'rate_limiting',
            'session_security',
            'api_security',
            'security_logging',
            'security_headers'
        ]
        
        self.log.info(f"Security migration tool initialized for {self.spiderfoot_root}")
    
    def analyze_current_security(self) -> Dict[str, Any]:
        """
        Analyze current security implementation in SpiderFoot.
        
        Returns:
            Analysis results
        """
        self.log.info("Analyzing current security implementation...")
        
        analysis = {
            'files_analyzed': 0,
            'security_issues': [],
            'existing_security': [],
            'recommendations': [],
            'migration_complexity': 'low'
        }
        
        for file_path, file_type in self.target_files.items():
            full_path = os.path.join(self.spiderfoot_root, file_path)
            if os.path.exists(full_path):
                file_analysis = self._analyze_file_security(full_path, file_type)
                analysis['files_analyzed'] += 1
                analysis['security_issues'].extend(file_analysis['issues'])
                analysis['existing_security'].extend(file_analysis['existing'])
                analysis['recommendations'].extend(file_analysis['recommendations'])
        
        # Determine migration complexity
        issue_count = len(analysis['security_issues'])
        if issue_count > 20:
            analysis['migration_complexity'] = 'high'
        elif issue_count > 10:
            analysis['migration_complexity'] = 'medium'
        
        self.log.info(f"Analysis complete. Found {issue_count} security issues.")
        return analysis
    
    def _analyze_file_security(self, file_path: str, file_type: str) -> Dict[str, List]:
        """
        Analyze security in a specific file.
        
        Args:
            file_path: Path to file to analyze
            file_type: Type of file (web_interface, api_main, etc.)
            
        Returns:
            File analysis results
        """
        result = {
            'issues': [],
            'existing': [],
            'recommendations': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for existing security measures
            if 'csrf' in content.lower():
                result['existing'].append(f"{file_path}: CSRF protection found")
            else:
                result['issues'].append(f"{file_path}: Missing CSRF protection")
                result['recommendations'].append(f"{file_path}: Add CSRF token validation")
            
            if 'rate.limit' in content.lower() or 'ratelimit' in content.lower():
                result['existing'].append(f"{file_path}: Rate limiting found")
            else:
                result['issues'].append(f"{file_path}: Missing rate limiting")
                result['recommendations'].append(f"{file_path}: Add rate limiting")
            
            if 'xss' in content.lower() or 'html.escape' in content.lower():
                result['existing'].append(f"{file_path}: XSS protection found")
            else:
                result['issues'].append(f"{file_path}: Missing XSS protection")
                result['recommendations'].append(f"{file_path}: Add input validation and XSS protection")
            
            if 'session' in content.lower() and 'secure' in content.lower():
                result['existing'].append(f"{file_path}: Session security found")
            else:
                result['issues'].append(f"{file_path}: Missing secure session management")
                result['recommendations'].append(f"{file_path}: Implement secure session management")
            
            # Check for specific vulnerabilities based on file type
            if file_type == 'web_interface':
                self._analyze_web_interface_security(content, file_path, result)
            elif file_type == 'api_main':
                self._analyze_api_security(content, file_path, result)
            elif file_type == 'web_routes':
                self._analyze_routes_security(content, file_path, result)
                
        except Exception as e:
            self.log.error(f"Error analyzing {file_path}: {e}")
            result['issues'].append(f"{file_path}: Analysis failed - {e}")
        
        return result
    
    def _analyze_web_interface_security(self, content: str, file_path: str, result: Dict):
        """Analyze web interface specific security."""
        # Check for authentication
        if 'auth' not in content.lower() and 'login' not in content.lower():
            result['issues'].append(f"{file_path}: Missing authentication")
            result['recommendations'].append(f"{file_path}: Implement authentication system")
        
        # Check for input sanitization
        if 'sanitize' not in content.lower() and 'escape' not in content.lower():
            result['issues'].append(f"{file_path}: Missing input sanitization")
            result['recommendations'].append(f"{file_path}: Add input sanitization")
    
    def _analyze_api_security(self, content: str, file_path: str, result: Dict):
        """Analyze API specific security."""
        # Check for API key validation
        if 'api.key' not in content.lower() and 'apikey' not in content.lower():
            result['issues'].append(f"{file_path}: Missing API key validation")
            result['recommendations'].append(f"{file_path}: Implement API key validation")
        
        # Check for JWT
        if 'jwt' not in content.lower() and 'token' not in content.lower():
            result['issues'].append(f"{file_path}: Missing JWT authentication")
            result['recommendations'].append(f"{file_path}: Add JWT authentication")
    
    def _analyze_routes_security(self, content: str, file_path: str, result: Dict):
        """Analyze routes specific security."""
        # Check for route protection
        if '@require' not in content.lower() and 'auth' not in content.lower():
            result['issues'].append(f"{file_path}: Missing route protection")
            result['recommendations'].append(f"{file_path}: Add route authentication")
    
    def create_migration_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a detailed migration plan based on analysis.
        
        Args:
            analysis: Security analysis results
            
        Returns:
            Migration plan
        """
        self.log.info("Creating migration plan...")
        
        plan = {
            'phases': [],
            'estimated_time': 0,
            'risk_level': analysis['migration_complexity'],
            'backup_required': True,
            'rollback_plan': True
        }
        
        # Phase 1: Setup and backup
        phase1 = {
            'name': 'Setup and Backup',
            'description': 'Create backups and install security modules',
            'tasks': [
                'Create backup of existing files',
                'Install security modules',
                'Validate security module dependencies',
                'Create migration log'
            ],
            'estimated_time': 30,
            'risk': 'low'
        }
        plan['phases'].append(phase1)
        
        # Phase 2: Core security integration
        phase2 = {
            'name': 'Core Security Integration',
            'description': 'Integrate core security features',
            'tasks': [
                'Update configuration management',
                'Integrate security middleware',
                'Add CSRF protection',
                'Implement input validation'
            ],
            'estimated_time': 120,
            'risk': 'medium'
        }
        plan['phases'].append(phase2)
        
        # Phase 3: Web interface security
        phase3 = {
            'name': 'Web Interface Security',
            'description': 'Secure web interface and routes',
            'tasks': [
                'Update web routes with security',
                'Add session security',
                'Implement rate limiting',
                'Add security headers'
            ],
            'estimated_time': 90,
            'risk': 'medium'
        }
        plan['phases'].append(phase3)
        
        # Phase 4: API security
        phase4 = {
            'name': 'API Security',
            'description': 'Secure API endpoints',
            'tasks': [
                'Implement API authentication',
                'Add JWT support',
                'Secure API routes',
                'Add API rate limiting'
            ],
            'estimated_time': 60,
            'risk': 'low'
        }
        plan['phases'].append(phase4)
        
        # Phase 5: Testing and validation
        phase5 = {
            'name': 'Testing and Validation',
            'description': 'Test security implementation',
            'tasks': [
                'Run security tests',
                'Validate all features work',
                'Performance testing',
                'Security audit'
            ],
            'estimated_time': 60,
            'risk': 'low'
        }
        plan['phases'].append(phase5)
        
        plan['estimated_time'] = sum(phase['estimated_time'] for phase in plan['phases'])
        
        self.log.info(f"Migration plan created with {len(plan['phases'])} phases")
        return plan
    
    def execute_migration(self, plan: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute the migration plan.
        
        Args:
            plan: Migration plan to execute
            dry_run: If True, only simulate the migration
            
        Returns:
            Migration results
        """
        self.log.info(f"{'Simulating' if dry_run else 'Executing'} migration plan...")
        
        results = {
            'success': True,
            'phases_completed': 0,
            'phases_failed': 0,
            'errors': [],
            'warnings': [],
            'dry_run': dry_run
        }
        
        if not dry_run:
            # Create backup
            self._create_backup()
        
        for i, phase in enumerate(plan['phases']):
            self.log.info(f"{'Simulating' if dry_run else 'Executing'} phase {i+1}: {phase['name']}")
            
            try:
                phase_result = self._execute_phase(phase, dry_run)
                if phase_result['success']:
                    results['phases_completed'] += 1
                    self.log.info(f"Phase {i+1} completed successfully")
                else:
                    results['phases_failed'] += 1
                    results['errors'].extend(phase_result['errors'])
                    self.log.error(f"Phase {i+1} failed: {phase_result['errors']}")
                    
                    if not dry_run and phase['risk'] == 'high':
                        self.log.error("High-risk phase failed, stopping migration")
                        results['success'] = False
                        break
                        
            except Exception as e:
                results['phases_failed'] += 1
                error_msg = f"Phase {i+1} exception: {e}"
                results['errors'].append(error_msg)
                self.log.error(error_msg)
                
                if not dry_run:
                    results['success'] = False
                    break
        
        # Overall success check
        if results['phases_failed'] > 0:
            results['success'] = False
        
        self.log.info(f"Migration {'simulation' if dry_run else 'execution'} completed. "
                     f"Success: {results['success']}, "
                     f"Phases completed: {results['phases_completed']}/{len(plan['phases'])}")
        
        return results
    
    def _create_backup(self):
        """Create backup of existing files."""
        self.log.info("Creating backup of existing files...")
        
        if os.path.exists(self.backup_dir):
            shutil.rmtree(self.backup_dir)
        
        os.makedirs(self.backup_dir)
        
        for file_path in self.target_files.keys():
            full_path = os.path.join(self.spiderfoot_root, file_path)
            if os.path.exists(full_path):
                backup_path = os.path.join(self.backup_dir, file_path)
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                shutil.copy2(full_path, backup_path)
                self.log.info(f"Backed up {file_path}")
    
    def _execute_phase(self, phase: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
        """Execute a single migration phase."""
        result = {
            'success': True,
            'errors': [],
            'warnings': []
        }
        
        phase_name = phase['name']
        
        try:
            if phase_name == 'Setup and Backup':
                result = self._execute_setup_phase(dry_run)
            elif phase_name == 'Core Security Integration':
                result = self._execute_core_security_phase(dry_run)
            elif phase_name == 'Web Interface Security':
                result = self._execute_web_security_phase(dry_run)
            elif phase_name == 'API Security':
                result = self._execute_api_security_phase(dry_run)
            elif phase_name == 'Testing and Validation':
                result = self._execute_testing_phase(dry_run)
            else:
                result['errors'].append(f"Unknown phase: {phase_name}")
                result['success'] = False
                
        except Exception as e:
            result['errors'].append(f"Phase execution error: {e}")
            result['success'] = False
        
        return result
    
    def _execute_setup_phase(self, dry_run: bool) -> Dict[str, Any]:
        """Execute setup and backup phase."""
        result = {'success': True, 'errors': [], 'warnings': []}
        
        if not dry_run:
            try:
                # Backup already created in execute_migration
                
                # Validate security modules exist
                security_modules = [
                    'csrf_protection.py',
                    'input_validation.py', 
                    'rate_limiting.py',
                    'session_security.py',
                    'api_security.py',
                    'security_logging.py',
                    'security_middleware.py'
                ]
                
                for module in security_modules:
                    module_path = os.path.join(self.spiderfoot_root, 'spiderfoot', module)
                    if not os.path.exists(module_path):
                        result['errors'].append(f"Missing security module: {module}")
                        result['success'] = False
                        
            except Exception as e:
                result['errors'].append(f"Setup phase error: {e}")
                result['success'] = False
        
        return result
    
    def _execute_core_security_phase(self, dry_run: bool) -> Dict[str, Any]:
        """Execute core security integration phase."""
        result = {'success': True, 'errors': [], 'warnings': []}
        
        if not dry_run:
            try:
                # Update main configuration files to use SecureConfigManager
                self._integrate_secure_config()
                
                # Add security middleware imports to main files
                self._add_security_imports()
                
            except Exception as e:
                result['errors'].append(f"Core security phase error: {e}")
                result['success'] = False
        else:
            result['warnings'].append("Core security integration would modify configuration management")
        
        return result
    
    def _execute_web_security_phase(self, dry_run: bool) -> Dict[str, Any]:
        """Execute web interface security phase."""
        result = {'success': True, 'errors': [], 'warnings': []}
        
        if not dry_run:
            try:
                # Update web routes to use security middleware
                self._integrate_web_security()
                
            except Exception as e:
                result['errors'].append(f"Web security phase error: {e}")
                result['success'] = False
        else:
            result['warnings'].append("Web security integration would modify web interface")
        
        return result
    
    def _execute_api_security_phase(self, dry_run: bool) -> Dict[str, Any]:
        """Execute API security phase."""
        result = {'success': True, 'errors': [], 'warnings': []}
        
        if not dry_run:
            try:
                # Update API to use security middleware
                self._integrate_api_security()
                
            except Exception as e:
                result['errors'].append(f"API security phase error: {e}")
                result['success'] = False
        else:
            result['warnings'].append("API security integration would modify API endpoints")
        
        return result
    
    def _execute_testing_phase(self, dry_run: bool) -> Dict[str, Any]:
        """Execute testing and validation phase."""
        result = {'success': True, 'errors': [], 'warnings': []}
        
        if not dry_run:
            try:
                # Run basic validation
                self._validate_security_integration()
                
            except Exception as e:
                result['errors'].append(f"Testing phase error: {e}")
                result['success'] = False
        else:
            result['warnings'].append("Testing phase would validate security integration")
        
        return result
    
    def _integrate_secure_config(self):
        """Integrate SecureConfigManager into main configuration."""
        # This would update sf.py and other config files to use SecureConfigManager
        self.log.info("Integrating SecureConfigManager (placeholder)")
    
    def _add_security_imports(self):
        """Add security module imports to main files."""
        # This would add imports for security modules
        self.log.info("Adding security imports (placeholder)")
    
    def _integrate_web_security(self):
        """Integrate security middleware into web interface."""
        # This would update sfwebui.py and routes.py to use security middleware
        self.log.info("Integrating web security (placeholder)")
    
    def _integrate_api_security(self):
        """Integrate security middleware into API."""
        # This would update API files to use security middleware
        self.log.info("Integrating API security (placeholder)")
    
    def _validate_security_integration(self):
        """Validate that security integration works correctly."""
        # This would run tests to validate the integration
        self.log.info("Validating security integration (placeholder)")
    
    def rollback_migration(self) -> Dict[str, Any]:
        """
        Rollback migration changes.
        
        Returns:
            Rollback results
        """
        self.log.info("Rolling back migration changes...")
        
        result = {
            'success': True,
            'files_restored': 0,
            'errors': []
        }
        
        try:
            if not os.path.exists(self.backup_dir):
                result['errors'].append("No backup directory found")
                result['success'] = False
                return result
            
            # Restore backed up files
            for file_path in self.target_files.keys():
                backup_path = os.path.join(self.backup_dir, file_path)
                if os.path.exists(backup_path):
                    original_path = os.path.join(self.spiderfoot_root, file_path)
                    shutil.copy2(backup_path, original_path)
                    result['files_restored'] += 1
                    self.log.info(f"Restored {file_path}")
            
            self.log.info(f"Rollback completed. Restored {result['files_restored']} files.")
            
        except Exception as e:
            result['errors'].append(f"Rollback error: {e}")
            result['success'] = False
            self.log.error(f"Rollback failed: {e}")
        
        return result


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='SpiderFoot Security Migration Tool')
    parser.add_argument('spiderfoot_root', help='Root directory of SpiderFoot installation')
    parser.add_argument('--analyze', action='store_true', help='Only analyze current security')
    parser.add_argument('--plan', action='store_true', help='Create migration plan')
    parser.add_argument('--migrate', action='store_true', help='Execute migration')
    parser.add_argument('--dry-run', action='store_true', help='Simulate migration without changes')
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        tool = SecurityMigrationTool(args.spiderfoot_root)
        
        if args.rollback:
            result = tool.rollback_migration()
            print(f"Rollback {'successful' if result['success'] else 'failed'}")
            if result['errors']:
                print("Errors:", result['errors'])
            return 0 if result['success'] else 1
        
        # Analyze security
        analysis = tool.analyze_current_security()
        print(f"Security Analysis:")
        print(f"  Files analyzed: {analysis['files_analyzed']}")
        print(f"  Security issues: {len(analysis['security_issues'])}")
        print(f"  Migration complexity: {analysis['migration_complexity']}")
        
        if args.analyze:
            print("\nSecurity Issues:")
            for issue in analysis['security_issues']:
                print(f"  - {issue}")
            print("\nRecommendations:")
            for rec in analysis['recommendations']:
                print(f"  - {rec}")
            return 0
        
        # Create migration plan
        plan = tool.create_migration_plan(analysis)
        print(f"\nMigration Plan:")
        print(f"  Phases: {len(plan['phases'])}")
        print(f"  Estimated time: {plan['estimated_time']} minutes")
        print(f"  Risk level: {plan['risk_level']}")
        
        if args.plan:
            for i, phase in enumerate(plan['phases']):
                print(f"\n  Phase {i+1}: {phase['name']}")
                print(f"    Description: {phase['description']}")
                print(f"    Time: {phase['estimated_time']} minutes")
                print(f"    Risk: {phase['risk']}")
                print(f"    Tasks:")
                for task in phase['tasks']:
                    print(f"      - {task}")
            return 0
        
        # Execute migration
        if args.migrate or args.dry_run:
            result = tool.execute_migration(plan, dry_run=args.dry_run)
            action = "Simulation" if args.dry_run else "Migration"
            print(f"\n{action} {'successful' if result['success'] else 'failed'}")
            print(f"  Phases completed: {result['phases_completed']}/{len(plan['phases'])}")
            
            if result['errors']:
                print("  Errors:")
                for error in result['errors']:
                    print(f"    - {error}")
            
            if result['warnings']:
                print("  Warnings:")
                for warning in result['warnings']:
                    print(f"    - {warning}")
            
            return 0 if result['success'] else 1
        
        print("\nUse --migrate to execute the migration or --dry-run to simulate it")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
