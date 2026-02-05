"""
Snowflake database connector with context manager support.

Supports multiple authentication methods:
- Password authentication
- Key-pair authentication (RSA private key)
- External browser authentication (OAuth)
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import snowflake.connector
from snowflake.connector import DictCursor
from src.connectors.base_connector import BaseConnector
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Authentication types
AUTH_PASSWORD = "snowflake"
AUTH_KEYPAIR = "keypair"
AUTH_EXTERNAL_BROWSER = "externalbrowser"
AUTH_OAUTH_TOKEN = "oauth"


class SnowflakeConnector(BaseConnector):
    """
    Snowflake connection manager with context manager support.
    
    Usage:
        with SnowflakeConnector(config) as conn:
            conn.execute_query("SELECT 1")
    """
    
    PLATFORM = "snowflake"
    
    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None,
        authenticator: Optional[str] = None,
        private_key_path: Optional[str] = None,
        private_key_passphrase: Optional[str] = None,
        token: Optional[str] = None
    ):
        """
        Initialize Snowflake connector.
        
        Args:
            account: Snowflake account identifier
            user: Username
            password: Password (for password auth)
            warehouse: Warehouse name
            database: Database name
            schema: Schema name
            role: Role name
            authenticator: Authentication method ('snowflake', 'oauth', 'keypair', 'externalbrowser')
            private_key_path: Path to RSA private key file (for key-pair auth)
            private_key_passphrase: Passphrase for encrypted private key (optional)
            token: Programmatic Access Token (PAT) for OAuth authentication
            
        If not provided, reads from environment variables:
            SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
            SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA,
            SNOWFLAKE_ROLE, SNOWFLAKE_AUTHENTICATOR, SNOWFLAKE_PRIVATE_KEY_PATH,
            SNOWFLAKE_PRIVATE_KEY_PASSPHRASE, SNOWFLAKE_TOKEN
            
        Authentication Methods:
            1. Password (default): Set SNOWFLAKE_PASSWORD
            2. OAuth/PAT: Set SNOWFLAKE_AUTHENTICATOR=oauth and SNOWFLAKE_TOKEN
            3. Key-pair: Set SNOWFLAKE_AUTHENTICATOR=keypair and SNOWFLAKE_PRIVATE_KEY_PATH
            4. External browser: Set SNOWFLAKE_AUTHENTICATOR=externalbrowser
        """
        self.account = account or os.getenv("SNOWFLAKE_ACCOUNT")
        self.user = user or os.getenv("SNOWFLAKE_USER")
        self.password = password or os.getenv("SNOWFLAKE_PASSWORD")
        self.warehouse = warehouse or os.getenv("SNOWFLAKE_WAREHOUSE")
        self.database = database or os.getenv("SNOWFLAKE_DATABASE")
        self.schema = schema or os.getenv("SNOWFLAKE_SCHEMA")
        self.role = role or os.getenv("SNOWFLAKE_ROLE")
        
        # Authentication settings
        self.authenticator = authenticator or os.getenv("SNOWFLAKE_AUTHENTICATOR", "snowflake")
        self.private_key_path = private_key_path or os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
        self.private_key_passphrase = private_key_passphrase or os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
        self.token = token or os.getenv("SNOWFLAKE_TOKEN")
        
        self.connection: Optional[snowflake.connector.SnowflakeConnection] = None
        self.cursor: Optional[snowflake.connector.cursor.SnowflakeCursor] = None
        
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate required connection parameters based on authentication method."""
        # Always required
        required_base = ["account", "user"]
        missing = [param for param in required_base if not getattr(self, param)]
        
        if missing:
            raise ValueError(
                f"Missing required connection parameters: {', '.join(missing)}"
            )
        
        # Validate based on authentication method
        auth_method = self.authenticator.lower() if self.authenticator else "snowflake"
        
        if auth_method == "snowflake":
            # Password authentication - password required
            if not self.password:
                raise ValueError(
                    "Password is required for password authentication. "
                    "Set SNOWFLAKE_PASSWORD or use key-pair authentication "
                    "(set SNOWFLAKE_AUTHENTICATOR=keypair)"
                )
        
        elif auth_method == "oauth":
            # OAuth/PAT authentication - token required
            if not self.token:
                raise ValueError(
                    "Token is required for OAuth/PAT authentication. "
                    "Set SNOWFLAKE_TOKEN with your Programmatic Access Token"
                )
        
        elif auth_method == "keypair":
            # Key-pair authentication - private key path required
            if not self.private_key_path:
                raise ValueError(
                    "Private key path is required for key-pair authentication. "
                    "Set SNOWFLAKE_PRIVATE_KEY_PATH"
                )
            
            # Expand ~ to home directory and verify key file exists
            key_path = Path(self.private_key_path).expanduser()
            if not key_path.exists():
                raise ValueError(
                    f"Private key file not found: {self.private_key_path}"
                )
        
        elif auth_method == "externalbrowser":
            # External browser authentication - no additional params needed
            logger.info("Using external browser authentication (OAuth)")
        
        else:
            raise ValueError(
                f"Unknown authenticator: {auth_method}. "
                f"Use 'snowflake', 'oauth', 'keypair', or 'externalbrowser'"
            )
    
    def _load_private_key(self) -> bytes:
        """
        Load and parse RSA private key for key-pair authentication.
        
        Returns:
            Private key bytes in DER format
        """
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
        
        if not self.private_key_path:
            raise ValueError("Private key path is not set")
        
        key_path = Path(self.private_key_path).expanduser()
        logger.info(f"Loading private key from: {key_path}")
        
        with open(key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=self.private_key_passphrase.encode() if self.private_key_passphrase else None,
                backend=default_backend()
            )
        
        # Convert to DER format for Snowflake
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return private_key_bytes
    
    def connect(self) -> None:
        """Establish connection to Snowflake using configured authentication method."""
        try:
            auth_method = self.authenticator.lower() if self.authenticator else "snowflake"
            logger.info(f"Connecting to Snowflake account: {self.account}")
            logger.info(f"Authentication method: {auth_method}")
            
            connection_params: Dict[str, Any] = {
                "account": self.account,
                "user": self.user
            }
            
            # Set authentication parameters based on method
            if auth_method == "snowflake":
                # Password authentication
                connection_params["password"] = self.password
                
            elif auth_method == "oauth":
                # OAuth/PAT authentication
                connection_params["authenticator"] = "oauth"
                connection_params["token"] = self.token
                logger.info("Using Programmatic Access Token (PAT) authentication")
                
            elif auth_method == "keypair":
                # Key-pair authentication - private_key expects bytes
                connection_params["private_key"] = self._load_private_key()
                logger.info("Using RSA key-pair authentication")
                
            elif auth_method == "externalbrowser":
                # External browser (OAuth) authentication
                connection_params["authenticator"] = "externalbrowser"
                logger.info("Using external browser authentication - browser will open")
            
            # Add optional connection parameters
            if self.warehouse:
                connection_params["warehouse"] = self.warehouse
            if self.database:
                connection_params["database"] = self.database
            if self.schema:
                connection_params["schema"] = self.schema
            if self.role:
                connection_params["role"] = self.role
            
            self.connection = snowflake.connector.connect(**connection_params)
            self.cursor = self.connection.cursor()
            
            logger.info("Successfully connected to Snowflake")
            
        except snowflake.connector.errors.DatabaseError as e:
            logger.error(f"Failed to connect to Snowflake: {e}")
            raise
    
    def close(self) -> None:
        """Close Snowflake connection."""
        if self.cursor:
            self.cursor.close()
            logger.debug("Cursor closed")
        
        if self.connection:
            self.connection.close()
            logger.info("Connection closed")
    
    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[tuple]:
        """
        Execute SQL query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters for parameterized queries
            
        Returns:
            List of result tuples
        """
        if not self.cursor:
            raise RuntimeError("Not connected to Snowflake. Call connect() first.")
        
        try:
            logger.debug(f"Executing query: {query[:100]}...")
            
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            # Fetch results if query returns data
            if self.cursor.description:
                results = self.cursor.fetchall()
                logger.debug(f"Query returned {len(results)} rows")
                return results
            
            logger.debug("Query executed successfully (no results)")
            return []
            
        except snowflake.connector.errors.ProgrammingError as e:
            logger.error(f"SQL execution failed: {e}")
            logger.error(f"Query: {query}")
            raise
    
    def execute_dict(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results as dictionaries.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        if not self.connection:
            raise RuntimeError("Not connected to Snowflake")
        
        try:
            cursor = self.connection.cursor(DictCursor)
            logger.debug(f"Executing query: {query[:100]}...")
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if cursor.description:
                results = cursor.fetchall()
                logger.debug(f"Query returned {len(results)} rows")
                cursor.close()
                return results
            
            cursor.close()
            return []
            
        except snowflake.connector.errors.ProgrammingError as e:
            logger.error(f"SQL execution failed: {e}")
            raise
    
    def execute_many(
        self,
        query: str,
        data: List[tuple]
    ) -> None:
        """
        Execute query with multiple parameter sets (batch insert).
        
        Args:
            query: SQL query with placeholders
            data: List of parameter tuples
        """
        if not self.cursor:
            raise RuntimeError("Not connected to Snowflake")
        
        try:
            logger.info(f"Executing batch query with {len(data)} rows")
            self.cursor.executemany(query, data)
            logger.info("Batch execution completed")
            
        except snowflake.connector.errors.ProgrammingError as e:
            logger.error(f"Batch execution failed: {e}")
            raise
    
    def commit(self) -> None:
        """Commit current transaction."""
        if not self.connection:
            raise RuntimeError("Not connected to Snowflake")
        
        self.connection.commit()
        logger.debug("Transaction committed")
    
    def rollback(self) -> None:
        """Rollback current transaction."""
        if not self.connection:
            raise RuntimeError("Not connected to Snowflake")
        
        self.connection.rollback()
        logger.warning("Transaction rolled back")
    
    def get_current_database(self) -> Optional[str]:
        """Get current database name."""
        result = self.execute_query("SELECT CURRENT_DATABASE()")
        return result[0][0] if result else None
    
    def get_current_schema(self) -> Optional[str]:
        """Get current schema name."""
        result = self.execute_query("SELECT CURRENT_SCHEMA()")
        return result[0][0] if result else None
    
    def table_exists(self, table_name: str, schema: Optional[str] = None) -> bool:
        """
        Check if table exists.
        
        Args:
            table_name: Name of table
            schema: Schema name (uses current if not provided)
            
        Returns:
            True if table exists
        """
        schema_name = schema or self.schema
        if not schema_name:
            raise ValueError("Schema must be provided or set in connector")
        
        query = """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = %s
        """
        
        result = self.execute_query(query, {"1": schema_name.upper(), "2": table_name.upper()})
        return result[0][0] > 0 if result else False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get current connection information.
        
        Returns:
            Dictionary with connection details
        """
        if not self.cursor:
            raise RuntimeError("Not connected to Snowflake")
        
        result = self.execute_query("""
            SELECT 
                CURRENT_USER() as user,
                CURRENT_ROLE() as role,
                CURRENT_WAREHOUSE() as warehouse,
                CURRENT_DATABASE() as database,
                CURRENT_SCHEMA() as schema,
                CURRENT_ACCOUNT() as account,
                CURRENT_REGION() as region
        """)
        
        if result:
            user, role, warehouse, database, schema, account, region = result[0]
            return {
                "platform": self.PLATFORM,
                "user": user,
                "role": role,
                "warehouse": warehouse,
                "database": database,
                "schema": schema,
                "account": account,
                "region": region,
                "connected": True
            }
        
        return {"platform": self.PLATFORM, "connected": False}
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type:
            logger.error(f"Error occurred: {exc_val}")
            if self.connection:
                self.rollback()
        
        self.close()
        return False
