"""
Database Connection Manager.

Location: src/infrastructure/database/connection.py

Handles PostgreSQL connection pooling and configuration.
Supports both Docker and local environments.
"""

import os
import logging
from typing import Optional
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from dotenv import load_dotenv

from src.shared.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class DatabaseConnectionManager:
    """
    Manages PostgreSQL database connections with pooling.

    This class handles:
    - Connection pooling for better performance
    - Docker vs local environment detection
    - Connection lifecycle management
    """

    def __init__(
            self,
            min_connections: int = 1,
            max_connections: int = 10,
    ):
        """
        Initialize database connection manager.

        Args:
            min_connections: Minimum number of connections in pool
            max_connections: Maximum number of connections in pool
        """
        self.min_connections = min_connections
        self.max_connections = max_connections
        self._pool: Optional[pool.SimpleConnectionPool] = None

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """Load database configuration from environment variables."""
        self.db_name = os.getenv("DB_NAME")
        self.db_user = os.getenv("DB_USER")
        self.db_password = os.getenv("DB_PASS")
        self.db_port = os.getenv("DB_PORT", "5432")

        # Check if running in Docker
        is_docker = os.getenv("DOCKER", "0") == "1"
        self.db_host = (
            os.getenv("DB_HOST_DOCKER") if is_docker else os.getenv("DB_HOST")
        )

        logger.info(
            f"Database config: host={self.db_host}, port={self.db_port}, "
            f"db={self.db_name}, docker={is_docker}"
        )

    def initialize_pool(self) -> None:
        """
        Initialize connection pool.

        Raises:
            ConfigurationError: If required config is missing
        """
        if not all([self.db_name, self.db_user, self.db_password, self.db_host]):
            raise ConfigurationError(
                "Missing required database configuration. "
                "Check DB_NAME, DB_USER, DB_PASS, DB_HOST in .env"
            )

        try:
            self._pool = pool.SimpleConnectionPool(
                self.min_connections,
                self.max_connections,
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
            )
            logger.info(
                f"Connection pool initialized ({self.min_connections}-{self.max_connections} connections)"
            )
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise ConfigurationError(f"Database pool initialization failed: {e}") from e

    def close_pool(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None
            logger.info("Database connection pool closed")

    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool (context manager).

        Usage:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users")

        Yields:
            psycopg2 connection

        Raises:
            ConfigurationError: If pool not initialized
        """
        if self._pool is None:
            raise ConfigurationError(
                "Connection pool not initialized. Call initialize_pool() first."
            )

        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor):
        """
        Get a cursor from a pooled connection (context manager).

        Usage:
            with db_manager.get_cursor() as cursor:
                cursor.execute("SELECT * FROM users")
                result = cursor.fetchone()

        Args:
            cursor_factory: Cursor factory (default: RealDictCursor for dict results)

        Yields:
            psycopg2 cursor
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Cursor operation failed: {e}")
                raise
            finally:
                cursor.close()

    def get_simple_connection(self):
        """
        Get a simple connection (non-pooled) for one-off operations.

        Returns:
            psycopg2 connection

        Note:
            Caller is responsible for closing the connection.
        """
        try:
            return psycopg2.connect(
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
            )
        except Exception as e:
            logger.error(f"Failed to create simple connection: {e}")
            raise ConfigurationError(f"Database connection failed: {e}") from e

    def test_connection(self) -> bool:
        """
        Test database connectivity.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                logger.info("✓ Database connection test successful")
                return True
        except Exception as e:
            logger.error(f"✗ Database connection test failed: {e}")
            return False


# ============================================================================
# Global instance (singleton pattern)
# ============================================================================

_db_manager: Optional[DatabaseConnectionManager] = None


def get_db_manager() -> DatabaseConnectionManager:
    """
    Get global database manager instance (singleton).

    Returns:
        DatabaseConnectionManager instance
    """
    global _db_manager

    if _db_manager is None:
        _db_manager = DatabaseConnectionManager()
        _db_manager.initialize_pool()

    return _db_manager


def close_db_manager() -> None:
    """Close global database manager and connection pool."""
    global _db_manager

    if _db_manager is not None:
        _db_manager.close_pool()
        _db_manager = None