# Database security enhancements
import logging
import hmac
import hashlib
from typing import Optional, Dict, Any

class DatabaseSecurity:
    """Database security enhancements for SpiderFoot."""
    
    def __init__(self, db_instance):
        """Initialize database security.
        
        Args:
            db_instance: SpiderFootDb instance
        """
        self.db = db_instance
        self.logger = logging.getLogger('spiderfoot.db.security')
        self.audit_enabled = True
        
    def audit_log(self, operation: str, table: str, user_id: str = None, 
                  data_hash: str = None, success: bool = True) -> None:
        """Log database operations for audit trail.
        
        Args:
            operation: Type of operation (SELECT, INSERT, UPDATE, DELETE)
            table: Table name
            user_id: User performing operation
            data_hash: Hash of sensitive data (for privacy)
            success: Whether operation was successful
        """
        if not self.audit_enabled:
            return
            
        try:
            audit_entry = {
                'timestamp': int(time.time() * 1000),
                'operation': operation,
                'table': table,
                'user_id': user_id or 'system',
                'data_hash': data_hash,
                'success': success,
                'ip_address': getattr(request, 'remote_addr', None) if 'request' in globals() else None
            }
            
            # Log to audit table (create if doesn't exist)
            self._ensure_audit_table()
            
            with self.db.dbhLock:
                if self.db.db_type == 'sqlite':
                    qry = """INSERT INTO tbl_audit_log 
                           (timestamp, operation, table_name, user_id, data_hash, success, ip_address)
                           VALUES (?, ?, ?, ?, ?, ?, ?)"""
                    params = (audit_entry['timestamp'], audit_entry['operation'], 
                             audit_entry['table'], audit_entry['user_id'],
                             audit_entry['data_hash'], audit_entry['success'],
                             audit_entry['ip_address'])
                else:  # postgresql
                    qry = """INSERT INTO tbl_audit_log 
                           (timestamp, operation, table_name, user_id, data_hash, success, ip_address)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                    params = (audit_entry['timestamp'], audit_entry['operation'],
                             audit_entry['table'], audit_entry['user_id'],
                             audit_entry['data_hash'], audit_entry['success'],
                             audit_entry['ip_address'])
                
                self.db.dbh.execute(qry, params)
                self.db.conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}")
    
    def _ensure_audit_table(self) -> None:
        """Ensure audit log table exists."""
        try:
            with self.db.dbhLock:
                if self.db.db_type == 'sqlite':
                    qry = """CREATE TABLE IF NOT EXISTS tbl_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp BIGINT NOT NULL,
                        operation VARCHAR(20) NOT NULL,
                        table_name VARCHAR(50) NOT NULL,
                        user_id VARCHAR(50),
                        data_hash VARCHAR(64),
                        success BOOLEAN DEFAULT TRUE,
                        ip_address VARCHAR(45),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )"""
                else:  # postgresql
                    qry = """CREATE TABLE IF NOT EXISTS tbl_audit_log (
                        id SERIAL PRIMARY KEY,
                        timestamp BIGINT NOT NULL,
                        operation VARCHAR(20) NOT NULL,
                        table_name VARCHAR(50) NOT NULL,
                        user_id VARCHAR(50),
                        data_hash VARCHAR(64),
                        success BOOLEAN DEFAULT TRUE,
                        ip_address INET,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )"""
                
                self.db.dbh.execute(qry)
                self.db.conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to create audit table: {e}")
    
    def hash_sensitive_data(self, data: str, salt: str = None) -> str:
        """Create hash of sensitive data for audit logging.
        
        Args:
            data: Sensitive data to hash
            salt: Optional salt for hashing
            
        Returns:
            SHA-256 hash of the data
        """
        if salt is None:
            salt = "spiderfoot_audit_salt"
        
        combined = f"{salt}{data}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def validate_sql_query(self, query: str) -> bool:
        """Validate SQL query for potential injection attacks.
        
        Args:
            query: SQL query to validate
            
        Returns:
            True if query appears safe
        """
        # Basic SQL injection patterns
        dangerous_patterns = [
            r';\s*(drop|delete|truncate|alter)\s+',
            r'union\s+select',
            r'exec\s*\(',
            r'script\s*>',
            r'<\s*script',
            r'javascript:',
            r'vbscript:',
            r'--\s*$',
            r'/\*.*\*/',
        ]
        
        query_lower = query.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                self.logger.warning(f"Potentially dangerous SQL pattern detected: {pattern}")
                return False
        
        return True
    
    def secure_connection_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add security parameters to database connection.
        
        Args:
            params: Database connection parameters
            
        Returns:
            Enhanced connection parameters with security settings
        """
        if self.db.db_type == 'postgresql':
            # Add PostgreSQL security parameters
            params.update({
                'sslmode': 'require',
                'sslcert': params.get('sslcert'),
                'sslkey': params.get('sslkey'),
                'sslrootcert': params.get('sslrootcert'),
                'connect_timeout': 30,
                'application_name': 'spiderfoot_secure'
            })
        elif self.db.db_type == 'sqlite':
            # Add SQLite security parameters  
            params.update({
                'timeout': 30,
                'check_same_thread': False,
                'isolation_level': 'DEFERRED'
            })
        
        return params
    
    def clean_audit_logs(self, retention_days: int = 90) -> None:
        """Clean old audit logs to maintain performance.
        
        Args:
            retention_days: Number of days to retain audit logs
        """
        try:
            cutoff_timestamp = int((time.time() - (retention_days * 24 * 3600)) * 1000)
            
            with self.db.dbhLock:
                if self.db.db_type == 'sqlite':
                    qry = "DELETE FROM tbl_audit_log WHERE timestamp < ?"
                    params = (cutoff_timestamp,)
                else:  # postgresql
                    qry = "DELETE FROM tbl_audit_log WHERE timestamp < %s"
                    params = (cutoff_timestamp,)
                
                self.db.dbh.execute(qry, params)
                self.db.conn.commit()
                
                self.logger.info(f"Cleaned audit logs older than {retention_days} days")
                
        except Exception as e:
            self.logger.error(f"Failed to clean audit logs: {e}")

# Add security instance to SpiderFootDb
# ...existing SpiderFootDb class code...