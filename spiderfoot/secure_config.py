# -*- coding: utf-8 -*-
"""
Secure Configuration Management for SpiderFoot
Handles encryption of sensitive configuration data including API keys and passwords.
"""

import os
import json
import base64
import secrets
import time
from typing import Dict, Any, Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class SecureConfigManager:
    """Secure configuration manager with encryption for sensitive data."""
    
    def __init__(self, config_or_key: Union[str, Dict[str, Any], None] = None, salt: Optional[bytes] = None):
        """Initialize secure configuration manager.
        
        Args:
            config_or_key: Either a master encryption key (str), config dict, or None
            salt: Salt for key derivation (if None, generates new salt)
        """
        self.salt = salt or os.urandom(32)
        
        # Handle different input types
        if isinstance(config_or_key, dict):
            # If a config dict is passed, store it and extract master key if available
            self.config = config_or_key
            master_key = config_or_key.get('security.config.encryption_key') or config_or_key.get('SPIDERFOOT_ENCRYPTION_KEY')
        elif isinstance(config_or_key, str):
            # If a string is passed, it's the master key
            master_key = config_or_key
            self.config = {}
        else:
            # If None is passed, generate a new key
            master_key = None
            self.config = {}
        
        if master_key:
            self.master_key = master_key.encode()
        else:
            # Generate master key from environment or create new one
            self.master_key = self._get_or_create_master_key()
        
        # Derive encryption key from master key and salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key))
        self.cipher = Fernet(key)
        
        # Sensitive configuration keys that should be encrypted
        self.sensitive_keys = {
            'api_key', 'password', 'secret', 'token', 'key', 'credentials',
            'postgresql_password', 'redis_password', 'smtp_password',
            'elastic_password', 'auth_token', 'access_token', 'private_key'
        }
    
    def _get_or_create_master_key(self) -> bytes:
        """Get master key from environment or create new one.
        
        Returns:
            Master key bytes
        """
        # Try to get from environment variable
        env_key = os.environ.get('SPIDERFOOT_MASTER_KEY')
        if env_key:
            return base64.b64decode(env_key.encode())
        
        # Generate new master key
        master_key = secrets.token_bytes(32)
        
        # Save to environment for this session
        os.environ['SPIDERFOOT_MASTER_KEY'] = base64.b64encode(master_key).decode()
        
        return master_key
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if configuration key contains sensitive data.
        
        Args:
            key: Configuration key name
            
        Returns:
            True if key contains sensitive data
        """
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in self.sensitive_keys)
    
    def encrypt_value(self, value: str) -> str:
        """Encrypt a configuration value.
        
        Args:
            value: Value to encrypt
            
        Returns:
            Encrypted value as base64 string
        """
        if not isinstance(value, str):
            value = str(value)
        
        encrypted = self.cipher.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a configuration value.
        
        Args:
            encrypted_value: Encrypted value as base64 string
            
        Returns:
            Decrypted value
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_value.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception:
            # If decryption fails, return original value (might be unencrypted)
            return encrypted_value
    
    def encrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive values in configuration dictionary.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Configuration with encrypted sensitive values
        """
        encrypted_config = {}
        
        for key, value in config.items():
            if isinstance(value, dict):
                # Recursively encrypt nested dictionaries
                encrypted_config[key] = self.encrypt_config(value)
            elif isinstance(value, str) and self._is_sensitive_key(key) and value:
                # Encrypt sensitive string values
                if not value.startswith('enc:'):  # Don't double-encrypt
                    encrypted_config[key] = f"enc:{self.encrypt_value(value)}"
                else:
                    encrypted_config[key] = value
            else:
                # Keep non-sensitive values as-is
                encrypted_config[key] = value
        
        return encrypted_config
    
    def decrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive values in configuration dictionary.
        
        Args:
            config: Configuration dictionary with encrypted values
            
        Returns:
            Configuration with decrypted sensitive values
        """
        decrypted_config = {}
        
        for key, value in config.items():
            if isinstance(value, dict):
                # Recursively decrypt nested dictionaries
                decrypted_config[key] = self.decrypt_config(value)
            elif isinstance(value, str) and value.startswith('enc:'):
                # Decrypt encrypted values
                encrypted_value = value[4:]  # Remove 'enc:' prefix
                decrypted_config[key] = self.decrypt_value(encrypted_value)
            else:
                # Keep non-encrypted values as-is
                decrypted_config[key] = value
        
        return decrypted_config
    
    def save_secure_config(self, config: Dict[str, Any], filepath: str) -> None:
        """Save configuration with encrypted sensitive values.
        
        Args:
            config: Configuration dictionary
            filepath: Path to save configuration file
        """
        encrypted_config = self.encrypt_config(config)
        
        # Add metadata for security
        secure_config = {
            '_metadata': {
                'encrypted': True,
                'version': '1.0',
                'salt': base64.b64encode(self.salt).decode(),
                'algorithm': 'Fernet-PBKDF2-SHA256'
            },
            'config': encrypted_config
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(secure_config, f, indent=2)
        
        # Set restrictive file permissions
        os.chmod(filepath, 0o600)
    
    def load_secure_config(self, filepath: str) -> Dict[str, Any]:
        """Load and decrypt configuration from file.
        
        Args:
            filepath: Path to configuration file
            
        Returns:
            Decrypted configuration dictionary
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                secure_config = json.load(f)
            
            # Check if file is encrypted
            if secure_config.get('_metadata', {}).get('encrypted'):
                config = secure_config.get('config', {})
                return self.decrypt_config(config)
            else:
                # Handle legacy unencrypted config files
                return secure_config
        
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def migrate_config(self, old_config: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate old unencrypted configuration to encrypted format.
        
        Args:
            old_config: Old configuration dictionary
            
        Returns:
            Migrated configuration with encryption applied
        """
        return self.encrypt_config(old_config)
    
    def rotate_encryption_key(self, new_master_key: str, config_files: list = None) -> Dict[str, Any]:
        """Rotate encryption key and re-encrypt all sensitive data.
        
        Args:
            new_master_key: New master encryption key
            config_files: List of configuration files to re-encrypt
            
        Returns:
            Results of the key rotation process
        """
        results = {
            'success': False,
            'files_processed': 0,
            'files_failed': 0,
            'errors': []
        }
        
        try:
            # Create new cipher with new key
            new_key_bytes = new_master_key.encode()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self.salt,
                iterations=100000,
            )
            new_cipher_key = base64.urlsafe_b64encode(kdf.derive(new_key_bytes))
            new_cipher = Fernet(new_cipher_key)
            
            # Process configuration files
            config_files = config_files or []
            
            for config_file in config_files:
                try:
                    # Load with old cipher
                    old_config = self.load_secure_config(config_file)
                    
                    # Create backup
                    backup_file = f"{config_file}.backup.{int(time.time())}"
                    with open(backup_file, 'w', encoding='utf-8') as f:
                        json.dump(old_config, f, indent=2)
                    
                    # Update cipher and re-encrypt
                    old_cipher = self.cipher
                    self.cipher = new_cipher
                    self.master_key = new_key_bytes
                    
                    # Save with new encryption
                    self.save_secure_config(old_config, config_file)
                    
                    results['files_processed'] += 1
                    
                except Exception as e:
                    results['files_failed'] += 1
                    results['errors'].append(f"Failed to rotate key for {config_file}: {str(e)}")
            
            # Update environment variable
            os.environ['SPIDERFOOT_MASTER_KEY'] = base64.b64encode(new_key_bytes).decode()
            
            results['success'] = results['files_failed'] == 0
            
        except Exception as e:
            results['errors'].append(f"Key rotation failed: {str(e)}")
        
        return results
    
    def create_encrypted_backup(self, config: Dict[str, Any], backup_path: str, 
                               include_metadata: bool = True) -> bool:
        """Create encrypted backup of configuration.
        
        Args:
            config: Configuration to backup
            backup_path: Path for backup file
            include_metadata: Whether to include metadata
            
        Returns:
            True if backup was successful
        """
        try:
            backup_data = {
                'timestamp': int(time.time()),
                'version': '1.0',
                'config': self.encrypt_config(config)
            }
            
            if include_metadata:
                backup_data['metadata'] = {
                    'encrypted': True,
                    'salt': base64.b64encode(self.salt).decode(),
                    'algorithm': 'Fernet-PBKDF2-SHA256',
                    'backup_type': 'encrypted_config'
                }
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2)
            
            os.chmod(backup_path, 0o600)
            return True
            
        except Exception:
            return False
    
    def restore_from_backup(self, backup_path: str) -> Dict[str, Any]:
        """Restore configuration from encrypted backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            Restored configuration
        """
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            config = backup_data.get('config', {})
            return self.decrypt_config(config)
            
        except Exception:
            return {}
    
    def validate_compliance(self, config: Dict[str, Any], standards: list = None) -> Dict[str, Any]:
        """Validate configuration against security compliance standards.
        
        Args:
            config: Configuration to validate
            standards: List of compliance standards to check
            
        Returns:
            Compliance validation results
        """
        standards = standards or ['OWASP', 'NIST', 'ISO27001']
        
        compliance_results = {
            'overall_score': 0,
            'standards': {},
            'critical_issues': [],
            'recommendations': []
        }
        
        for standard in standards:
            if standard == 'OWASP':
                compliance_results['standards']['OWASP'] = self._validate_owasp_compliance(config)
            elif standard == 'NIST':
                compliance_results['standards']['NIST'] = self._validate_nist_compliance(config)
            elif standard == 'ISO27001':
                compliance_results['standards']['ISO27001'] = self._validate_iso27001_compliance(config)
        
        # Calculate overall score
        total_score = sum(result.get('score', 0) for result in compliance_results['standards'].values())
        compliance_results['overall_score'] = total_score / len(standards) if standards else 0
        
        # Collect critical issues and recommendations
        for standard_result in compliance_results['standards'].values():
            compliance_results['critical_issues'].extend(standard_result.get('critical_issues', []))
            compliance_results['recommendations'].extend(standard_result.get('recommendations', []))
        
        return compliance_results
    
    def _validate_owasp_compliance(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate OWASP security compliance.
        
        Args:
            config: Configuration to validate
            
        Returns:
            OWASP compliance results
        """
        issues = []
        recommendations = []
        score = 100
        
        # Check for secure authentication
        auth_config = config.get('authentication', {})
        if not auth_config.get('enabled'):
            issues.append('Authentication is not enabled')
            score -= 20
        
        if not auth_config.get('mfa_enabled'):
            recommendations.append('Enable multi-factor authentication')
            score -= 10
        
        # Check for secure session management
        session_config = config.get('session', {})
        if not session_config.get('secure'):
            issues.append('Secure session cookies not enabled')
            score -= 15
        
        if not session_config.get('httponly'):
            issues.append('HttpOnly session cookies not enabled')
            score -= 10
        
        # Check for HTTPS enforcement
        ssl_config = config.get('ssl', {})
        if not ssl_config.get('enabled'):
            issues.append('SSL/TLS not enabled')
            score -= 25
        
        # Check for secure headers
        headers_config = config.get('security_headers', {})
        required_headers = ['X-Frame-Options', 'X-Content-Type-Options', 'X-XSS-Protection']
        for header in required_headers:
            if not headers_config.get(header.lower().replace('-', '_')):
                recommendations.append(f'Enable {header} security header')
                score -= 5
        
        return {
            'score': max(0, score),
            'critical_issues': [issue for issue in issues],
            'recommendations': recommendations,
            'standard': 'OWASP'
        }
    
    def _validate_nist_compliance(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate NIST Cybersecurity Framework compliance.
        
        Args:
            config: Configuration to validate
            
        Returns:
            NIST compliance results
        """
        issues = []
        recommendations = []
        score = 100
        
        # Identify: Asset management
        if 'asset_management' not in config:
            recommendations.append('Implement asset management configuration')
            score -= 10
        
        # Protect: Access control
        access_control = config.get('access_control', {})
        if not access_control.get('rbac_enabled'):
            recommendations.append('Enable role-based access control')
            score -= 15
        
        # Detect: Monitoring and logging
        logging_config = config.get('logging', {})
        if not logging_config.get('security_events'):
            issues.append('Security event logging not configured')
            score -= 20
        
        if not logging_config.get('audit_trail'):
            recommendations.append('Enable audit trail logging')
            score -= 10
        
        # Respond: Incident response
        if 'incident_response' not in config:
            recommendations.append('Configure incident response procedures')
            score -= 15
        
        # Recover: Backup and recovery
        backup_config = config.get('backup', {})
        if not backup_config.get('enabled'):
            issues.append('Backup system not configured')
            score -= 20
        
        return {
            'score': max(0, score),
            'critical_issues': issues,
            'recommendations': recommendations,
            'standard': 'NIST'
        }
    
    def _validate_iso27001_compliance(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate ISO 27001 compliance.
        
        Args:
            config: Configuration to validate
            
        Returns:
            ISO 27001 compliance results
        """
        issues = []
        recommendations = []
        score = 100
        
        # Information security policy
        if 'security_policy' not in config:
            issues.append('Security policy not defined in configuration')
            score -= 25
        
        # Access control
        access_control = config.get('access_control', {})
        if not access_control.get('principle_of_least_privilege'):
            recommendations.append('Implement principle of least privilege')
            score -= 15
        
        # Cryptography
        crypto_config = config.get('cryptography', {})
        if not crypto_config.get('encryption_at_rest'):
            issues.append('Encryption at rest not enabled')
            score -= 20
        
        if not crypto_config.get('encryption_in_transit'):
            issues.append('Encryption in transit not enabled')
            score -= 20
        
        # Operations security
        ops_security = config.get('operations_security', {})
        if not ops_security.get('change_management'):
            recommendations.append('Implement change management procedures')
            score -= 10
        
        # System acquisition and maintenance
        if not config.get('secure_development', {}).get('enabled'):
            recommendations.append('Enable secure development practices')
            score -= 10
        
        return {
            'score': max(0, score),
            'critical_issues': issues,
            'recommendations': recommendations,
            'standard': 'ISO27001'
        }
