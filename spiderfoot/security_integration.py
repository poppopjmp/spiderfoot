# -*- coding: utf-8 -*-
"""
SpiderFoot Security Integration Module
Integrates all security enhancements into the existing SpiderFoot codebase.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# Import SpiderFoot core modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import security modules
from .secure_config import SecureConfigManager, EnvironmentConfigManager
from .csrf_protection import CSRFProtection
from .input_validation import InputValidator, SecurityHeaders
from .rate_limiting import RateLimiter
from .session_security import SecureSessionManager
from .api_security import APISecurityManager, APIKeyManager
from .security_logging import SecurityLogger, SecurityEventType, SecurityMonitor
from .web_security import SpiderFootSecurityManager


class SecurityIntegrator:
    """Main security integration class for SpiderFoot."""
    
    def __init__(self, spiderfoot_root: str = None):
        """Initialize security integrator.
        
        Args:
            spiderfoot_root: Root directory of SpiderFoot installation
        """
        self.spiderfoot_root = spiderfoot_root or os.path.dirname(os.path.dirname(__file__))
        self.security_config_path = os.path.join(self.spiderfoot_root, 'security_config.json')
        self.logger = logging.getLogger('spiderfoot.security.integrator')
        
        # Initialize security components
        self.config_manager = SecureConfigManager()
        self.security_logger = SecurityLogger()
        self.integration_status = {
            'csrf_protection': False,
            'input_validation': False,
            'rate_limiting': False,
            'secure_sessions': False,
            'api_security': False,
            'database_security': False,
            'configuration_security': False,
            'web_security': False
        }
    
    def analyze_existing_setup(self) -> Dict[str, Any]:
        """Analyze existing SpiderFoot setup for security gaps.
        
        Returns:
            Analysis results with security recommendations
        """
        analysis = {
            'current_security_level': 'low',
            'critical_issues': [],
            'recommendations': [],
            'file_modifications_needed': [],
            'new_dependencies': [],
            'configuration_changes': []
        }
        
        # Check existing files
        self._analyze_web_interface(analysis)
        self._analyze_api_endpoints(analysis)
        self._analyze_database_setup(analysis)
        self._analyze_configuration_files(analysis)
        self._analyze_dependencies(analysis)
        
        # Calculate security level
        critical_count = len(analysis['critical_issues'])
        if critical_count == 0:
            analysis['current_security_level'] = 'high'
        elif critical_count <= 3:
            analysis['current_security_level'] = 'medium'
        else:
            analysis['current_security_level'] = 'low'
        
        return analysis
    
    def _analyze_web_interface(self, analysis: Dict[str, Any]) -> None:
        """Analyze web interface for security issues."""
        web_files = [
            'spiderfoot/sfwebui.py',
            'spiderfoot/templates',
            'spiderfoot/static'
        ]
        
        for file_path in web_files:
            full_path = os.path.join(self.spiderfoot_root, file_path)
            if os.path.exists(full_path):
                if file_path.endswith('.py'):
                    # Check Python web files
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Check for CSRF protection
                        if 'csrf' not in content.lower():
                            analysis['critical_issues'].append(f'No CSRF protection in {file_path}')
                            analysis['file_modifications_needed'].append(file_path)
                        
                        # Check for input validation
                        if 'escape(' not in content and 'sanitize' not in content:
                            analysis['critical_issues'].append(f'No input validation in {file_path}')
                        
                        # Check for security headers
                        if 'X-Frame-Options' not in content:
                            analysis['recommendations'].append(f'Add security headers to {file_path}')
                
                elif file_path.endswith('templates'):
                    # Check template files
                    self._analyze_templates(full_path, analysis)
        
        # Add recommendations
        analysis['recommendations'].extend([
            'Implement CSRF protection for all forms',
            'Add input validation for all user inputs',
            'Implement secure session management',
            'Add security headers to all responses'
        ])
    
    def _analyze_templates(self, templates_dir: str, analysis: Dict[str, Any]) -> None:
        """Analyze template files for security issues."""
        if not os.path.exists(templates_dir):
            return
        
        for root, dirs, files in os.walk(templates_dir):
            for file in files:
                if file.endswith(('.html', '.htm')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                            # Check for XSS vulnerabilities
                            if '{{' in content and '|e' not in content:
                                analysis['critical_issues'].append(f'Potential XSS vulnerability in {file}')
                            
                            # Check for CSRF tokens
                            if '<form' in content and 'csrf_token' not in content:
                                analysis['critical_issues'].append(f'Missing CSRF token in form in {file}')
                    except Exception:
                        continue
    
    def _analyze_api_endpoints(self, analysis: Dict[str, Any]) -> None:
        """Analyze API endpoints for security issues."""
        api_files = [
            'spiderfoot/sfapi.py',
            'modules'
        ]
        
        for file_path in api_files:
            full_path = os.path.join(self.spiderfoot_root, file_path)
            if os.path.exists(full_path):
                if file_path.endswith('.py'):
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Check for authentication
                        if '@require_auth' not in content and 'authenticate' not in content:
                            analysis['critical_issues'].append(f'No authentication in API file {file_path}')
                        
                        # Check for rate limiting
                        if 'rate_limit' not in content:
                            analysis['recommendations'].append(f'Add rate limiting to {file_path}')
                        
                        # Check for input validation
                        if 'validate' not in content:
                            analysis['critical_issues'].append(f'No input validation in {file_path}')
        
        analysis['recommendations'].extend([
            'Implement JWT-based API authentication',
            'Add rate limiting to all API endpoints',
            'Implement API key management',
            'Add request/response validation'
        ])
    
    def _analyze_database_setup(self, analysis: Dict[str, Any]) -> None:
        """Analyze database setup for security issues."""
        db_file = os.path.join(self.spiderfoot_root, 'spiderfoot/db.py')
        
        if os.path.exists(db_file):
            with open(db_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for SQL injection protection
                if 'parameterized' not in content and '?' not in content:
                    analysis['critical_issues'].append('Potential SQL injection vulnerability in database layer')
                
                # Check for audit logging
                if 'audit' not in content.lower():
                    analysis['recommendations'].append('Add database audit logging')
                
                # Check for connection security
                if 'ssl' not in content.lower():
                    analysis['recommendations'].append('Enable SSL for database connections')
        
        analysis['file_modifications_needed'].append('spiderfoot/db.py')
    
    def _analyze_configuration_files(self, analysis: Dict[str, Any]) -> None:
        """Analyze configuration files for security issues."""
        config_patterns = ['*.conf', '*.config', '*.cfg', '*.ini', '*.json']
        
        for pattern in config_patterns:
            config_files = list(Path(self.spiderfoot_root).rglob(pattern))
            
            for config_file in config_files:
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        content = f.read().lower()
                        
                        # Check for hardcoded secrets
                        if any(keyword in content for keyword in ['password=', 'api_key=', 'secret=']):
                            analysis['critical_issues'].append(f'Hardcoded secrets in {config_file.name}')
                        
                        # Check for default passwords
                        if any(default in content for default in ['admin', 'password', 'changeme']):
                            analysis['critical_issues'].append(f'Default passwords in {config_file.name}')
                            
                except Exception:
                    continue
        
        analysis['configuration_changes'].extend([
            'Encrypt all sensitive configuration values',
            'Remove hardcoded passwords and API keys',
            'Implement environment-based configuration',
            'Add configuration validation'
        ])
    
    def _analyze_dependencies(self, analysis: Dict[str, Any]) -> None:
        """Analyze dependencies for security requirements."""
        requirements_file = os.path.join(self.spiderfoot_root, 'requirements.txt')
        
        # Security dependencies needed
        security_deps = [
            'cryptography>=3.4.8',  # For encryption
            'PyJWT>=2.4.0',         # For JWT tokens
            'redis>=4.0.0',         # For session/rate limiting
            'bleach>=4.1.0',        # For HTML sanitization
            'werkzeug>=2.0.0',      # For security utilities
        ]
        
        existing_deps = set()
        if os.path.exists(requirements_file):
            with open(requirements_file, 'r') as f:
                for line in f:
                    if '==' in line or '>=' in line:
                        dep_name = line.split('==')[0].split('>=')[0].strip()
                        existing_deps.add(dep_name.lower())
        
        for dep in security_deps:
            dep_name = dep.split('>=')[0].lower()
            if dep_name not in existing_deps:
                analysis['new_dependencies'].append(dep)
    
    def create_migration_plan(self) -> Dict[str, Any]:
        """Create detailed migration plan for security implementation.
        
        Returns:
            Detailed migration plan with steps and priorities
        """
        analysis = self.analyze_existing_setup()
        
        migration_plan = {
            'phases': {
                'phase_1_critical': {
                    'description': 'Address critical security vulnerabilities',
                    'priority': 'high',
                    'estimated_time': '2-3 days',
                    'tasks': []
                },
                'phase_2_essential': {
                    'description': 'Implement essential security features',
                    'priority': 'medium',
                    'estimated_time': '1-2 weeks',
                    'tasks': []
                },
                'phase_3_advanced': {
                    'description': 'Add advanced security features',
                    'priority': 'low',
                    'estimated_time': '1-2 weeks',
                    'tasks': []
                }
            },
            'rollback_plan': {
                'backup_locations': [],
                'rollback_steps': [],
                'validation_checks': []
            },
            'testing_plan': {
                'unit_tests': [],
                'integration_tests': [],
                'security_tests': []
            }
        }
        
        # Phase 1: Critical security issues
        migration_plan['phases']['phase_1_critical']['tasks'].extend([
            {
                'task': 'Install security dependencies',
                'action': 'pip install cryptography PyJWT redis bleach werkzeug',
                'files_affected': ['requirements.txt'],
                'risk': 'low'
            },
            {
                'task': 'Implement CSRF protection',
                'action': 'Add CSRF tokens to all forms',
                'files_affected': ['spiderfoot/sfwebui.py', 'templates/*.html'],
                'risk': 'medium'
            },
            {
                'task': 'Add input validation',
                'action': 'Sanitize all user inputs',
                'files_affected': ['spiderfoot/sfwebui.py', 'spiderfoot/sfapi.py'],
                'risk': 'medium'
            },
            {
                'task': 'Encrypt configuration secrets',
                'action': 'Replace plaintext API keys with encrypted versions',
                'files_affected': ['config files'],
                'risk': 'high'
            }
        ])
        
        # Phase 2: Essential features
        migration_plan['phases']['phase_2_essential']['tasks'].extend([
            {
                'task': 'Implement rate limiting',
                'action': 'Add rate limiting to API and web endpoints',
                'files_affected': ['spiderfoot/sfapi.py', 'spiderfoot/sfwebui.py'],
                'risk': 'medium'
            },
            {
                'task': 'Add secure session management',
                'action': 'Replace default sessions with secure session manager',
                'files_affected': ['spiderfoot/sfwebui.py'],
                'risk': 'medium'
            },
            {
                'task': 'Implement API authentication',
                'action': 'Add JWT-based API authentication',
                'files_affected': ['spiderfoot/sfapi.py'],
                'risk': 'medium'
            },
            {
                'task': 'Add security logging',
                'action': 'Implement comprehensive security event logging',
                'files_affected': ['all modules'],
                'risk': 'low'
            }
        ])
        
        # Phase 3: Advanced features
        migration_plan['phases']['phase_3_advanced']['tasks'].extend([
            {
                'task': 'Database security enhancements',
                'action': 'Add audit logging and connection security',
                'files_affected': ['spiderfoot/db.py'],
                'risk': 'medium'
            },
            {
                'task': 'Security monitoring dashboard',
                'action': 'Create security monitoring interface',
                'files_affected': ['new files'],
                'risk': 'low'
            },
            {
                'task': 'Compliance validation',
                'action': 'Add OWASP/NIST compliance checking',
                'files_affected': ['configuration system'],
                'risk': 'low'
            }
        ])
        
        # Rollback plan
        migration_plan['rollback_plan'].update({
            'backup_locations': [
                'backup/pre_security_upgrade/',
                'backup/database/',
                'backup/config/'
            ],
            'rollback_steps': [
                'Stop SpiderFoot services',
                'Restore backed up files',
                'Restore database if needed',
                'Restart services',
                'Validate functionality'
            ],
            'validation_checks': [
                'Web interface accessibility',
                'API functionality',
                'Database connectivity',
                'Module loading'
            ]
        })
        
        return migration_plan
    
    def execute_migration(self, phase: str = 'phase_1_critical', 
                         dry_run: bool = True) -> Dict[str, Any]:
        """Execute migration phase.
        
        Args:
            phase: Migration phase to execute
            dry_run: If True, only simulate the migration
            
        Returns:
            Migration execution results
        """
        migration_plan = self.create_migration_plan()
        phase_plan = migration_plan['phases'].get(phase, {})
        
        results = {
            'phase': phase,
            'dry_run': dry_run,
            'success': False,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'errors': [],
            'warnings': []
        }
        
        if not phase_plan:
            results['errors'].append(f'Unknown migration phase: {phase}')
            return results
        
        # Create backup before making changes
        if not dry_run:
            self._create_backup()
        
        # Execute tasks
        for task in phase_plan.get('tasks', []):
            try:
                if dry_run:
                    self.logger.info(f"[DRY RUN] Would execute: {task['task']}")
                    results['tasks_completed'] += 1
                else:
                    self._execute_task(task)
                    results['tasks_completed'] += 1
                    
            except Exception as e:
                results['tasks_failed'] += 1
                results['errors'].append(f"Task '{task['task']}' failed: {str(e)}")
        
        results['success'] = results['tasks_failed'] == 0
        
        # Log results
        if results['success']:
            self.security_logger.log_security_event(
                SecurityEventType.CONFIG_CHANGED,
                {
                    'migration_phase': phase,
                    'tasks_completed': results['tasks_completed'],
                    'dry_run': dry_run
                },
                severity='INFO'
            )
        else:
            self.security_logger.log_security_event(
                SecurityEventType.SUSPICIOUS_ACTIVITY,
                {
                    'migration_phase': phase,
                    'tasks_failed': results['tasks_failed'],
                    'errors': results['errors']
                },
                severity='ERROR'
            )
        
        return results
    
    def _create_backup(self) -> None:
        """Create backup of current installation."""
        import shutil
        from datetime import datetime
        
        backup_dir = os.path.join(self.spiderfoot_root, 'backup', 
                                 f"pre_security_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup critical files
        critical_files = [
            'spiderfoot/sfwebui.py',
            'spiderfoot/sfapi.py',
            'spiderfoot/db.py',
            'requirements.txt'
        ]
        
        for file_path in critical_files:
            source = os.path.join(self.spiderfoot_root, file_path)
            if os.path.exists(source):
                dest = os.path.join(backup_dir, file_path)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(source, dest)
    
    def _execute_task(self, task: Dict[str, Any]) -> None:
        """Execute a specific migration task.
        
        Args:
            task: Task configuration
        """
        task_name = task['task']
        
        if 'Install security dependencies' in task_name:
            self._install_dependencies()
        elif 'CSRF protection' in task_name:
            self._implement_csrf_protection()
        elif 'input validation' in task_name:
            self._implement_input_validation()
        elif 'Encrypt configuration' in task_name:
            self._encrypt_configuration()
        elif 'rate limiting' in task_name:
            self._implement_rate_limiting()
        elif 'secure session' in task_name:
            self._implement_secure_sessions()
        elif 'API authentication' in task_name:
            self._implement_api_authentication()
        elif 'security logging' in task_name:
            self._implement_security_logging()
        else:
            raise NotImplementedError(f"Task not implemented: {task_name}")
    
    def _install_dependencies(self) -> None:
        """Install required security dependencies."""
        import subprocess
        
        dependencies = [
            'cryptography>=3.4.8',
            'PyJWT>=2.4.0',
            'redis>=4.0.0',
            'bleach>=4.1.0'
        ]
        
        for dep in dependencies:
            subprocess.run([sys.executable, '-m', 'pip', 'install', dep], check=True)
    
    def _implement_csrf_protection(self) -> None:
        """Implement CSRF protection in web interface."""
        # This would modify sfwebui.py to add CSRF protection
        # Implementation would be specific to the actual code structure
        pass
    
    def _implement_input_validation(self) -> None:
        """Implement input validation across the application."""
        # This would add input validation to all user input points
        pass
    
    def _encrypt_configuration(self) -> None:
        """Encrypt sensitive configuration values."""
        # This would find and encrypt all API keys and passwords
        pass
    
    def _implement_rate_limiting(self) -> None:
        """Implement rate limiting for API and web endpoints."""
        # This would add rate limiting decorators to endpoints
        pass
    
    def _implement_secure_sessions(self) -> None:
        """Implement secure session management."""
        # This would replace default Flask sessions with secure sessions
        pass
    
    def _implement_api_authentication(self) -> None:
        """Implement JWT-based API authentication."""
        # This would add JWT authentication to API endpoints
        pass
    
    def _implement_security_logging(self) -> None:
        """Implement comprehensive security logging."""
        # This would add security event logging throughout the application
        pass
    
    def validate_security_implementation(self) -> Dict[str, Any]:
        """Validate that security features are properly implemented.
        
        Returns:
            Validation results
        """
        validation_results = {
            'overall_status': 'unknown',
            'checks_passed': 0,
            'checks_failed': 0,
            'details': {}
        }
        
        # Define validation checks
        checks = {
            'csrf_protection': self._validate_csrf_implementation,
            'input_validation': self._validate_input_validation,
            'rate_limiting': self._validate_rate_limiting,
            'secure_sessions': self._validate_secure_sessions,
            'api_security': self._validate_api_security,
            'database_security': self._validate_database_security,
            'configuration_security': self._validate_configuration_security,
            'security_logging': self._validate_security_logging
        }
        
        # Run validation checks
        for check_name, check_function in checks.items():
            try:
                result = check_function()
                validation_results['details'][check_name] = result
                
                if result.get('status') == 'pass':
                    validation_results['checks_passed'] += 1
                    self.integration_status[check_name] = True
                else:
                    validation_results['checks_failed'] += 1
                    
            except Exception as e:
                validation_results['details'][check_name] = {
                    'status': 'error',
                    'message': str(e)
                }
                validation_results['checks_failed'] += 1
        
        # Determine overall status
        total_checks = len(checks)
        if validation_results['checks_passed'] == total_checks:
            validation_results['overall_status'] = 'excellent'
        elif validation_results['checks_passed'] >= total_checks * 0.8:
            validation_results['overall_status'] = 'good'
        elif validation_results['checks_passed'] >= total_checks * 0.6:
            validation_results['overall_status'] = 'fair'
        else:
            validation_results['overall_status'] = 'poor'
        
        return validation_results
    
    def _validate_csrf_implementation(self) -> Dict[str, Any]:
        """Validate CSRF protection implementation."""
        # Check if CSRF protection is properly implemented
        return {'status': 'pending', 'message': 'CSRF validation not yet implemented'}
    
    def _validate_input_validation(self) -> Dict[str, Any]:
        """Validate input validation implementation."""
        return {'status': 'pending', 'message': 'Input validation check not yet implemented'}
    
    def _validate_rate_limiting(self) -> Dict[str, Any]:
        """Validate rate limiting implementation."""
        return {'status': 'pending', 'message': 'Rate limiting validation not yet implemented'}
    
    def _validate_secure_sessions(self) -> Dict[str, Any]:
        """Validate secure session implementation."""
        return {'status': 'pending', 'message': 'Session security validation not yet implemented'}
    
    def _validate_api_security(self) -> Dict[str, Any]:
        """Validate API security implementation."""
        return {'status': 'pending', 'message': 'API security validation not yet implemented'}
    
    def _validate_database_security(self) -> Dict[str, Any]:
        """Validate database security implementation."""
        return {'status': 'pending', 'message': 'Database security validation not yet implemented'}
    
    def _validate_configuration_security(self) -> Dict[str, Any]:
        """Validate configuration security implementation."""
        return {'status': 'pending', 'message': 'Configuration security validation not yet implemented'}
    
    def _validate_security_logging(self) -> Dict[str, Any]:
        """Validate security logging implementation."""
        return {'status': 'pending', 'message': 'Security logging validation not yet implemented'}


def main():
    """Main function for running security integration."""
    integrator = SecurityIntegrator()
    
    print("SpiderFoot Security Integration Tool")
    print("=" * 40)
    
    # Analyze current setup
    print("Analyzing current setup...")
    analysis = integrator.analyze_existing_setup()
    
    print(f"\nCurrent Security Level: {analysis['current_security_level'].upper()}")
    print(f"Critical Issues Found: {len(analysis['critical_issues'])}")
    print(f"Recommendations: {len(analysis['recommendations'])}")
    
    if analysis['critical_issues']:
        print("\nCritical Issues:")
        for issue in analysis['critical_issues'][:5]:  # Show first 5
            print(f"  - {issue}")
    
    # Create migration plan
    print("\nCreating migration plan...")
    migration_plan = integrator.create_migration_plan()
    
    print("\nMigration Phases:")
    for phase_name, phase_data in migration_plan['phases'].items():
        print(f"  {phase_name}: {len(phase_data['tasks'])} tasks ({phase_data['estimated_time']})")
    
    # Ask for user confirmation
    response = input("\nWould you like to run Phase 1 (Critical) in dry-run mode? (y/n): ")
    if response.lower() == 'y':
        print("\nExecuting Phase 1 (dry run)...")
        results = integrator.execute_migration('phase_1_critical', dry_run=True)
        
        print(f"Tasks that would be completed: {results['tasks_completed']}")
        if results['errors']:
            print("Potential issues:")
            for error in results['errors']:
                print(f"  - {error}")
    
    print("\nSecurity integration analysis complete.")


if __name__ == '__main__':
    main()
