"""
Database Repository - Implementation of Repository Pattern.

Location: src/infrastructure/database/repository.py

This module implements the Repository Pattern, providing a clean abstraction
over database operations. It replaces the old dbAccess.py procedural code
with an object-oriented, testable, and maintainable approach.

REFACTORING FROM V1:
- V1: dbAccess.py with procedural functions (get_user_data_by_email, execute_query, etc.)
- V2: DatabaseRepository class with:
  * Dependency injection
  * Type-safe operations
  * Error handling
  * Connection pooling
  * Testability (can be mocked)
"""

import logging
from typing import Optional, Dict, Any, Tuple

from src.infrastructure.database.connection import DatabaseConnectionManager
from src.shared.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class DatabaseRepository:
    """
    Repository for database operations.

    This class encapsulates all database access logic, following the
    Repository Pattern for clean separation of concerns.

    Usage:
        db_repo = DatabaseRepository(db_manager)
        user_data = db_repo.get_user_data_by_email("user@example.com")
    """

    def __init__(self, db_manager: DatabaseConnectionManager):
        """
        Initialize repository with database manager.

        Args:
            db_manager: Database connection manager instance
        """
        self.db_manager = db_manager

    # ========================================================================
    # Generic Query Execution
    # ========================================================================

    def execute_query(
            self,
            query: str,
            params: Tuple = (),
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a generic database query.

        Args:
            query: SQL query string
            params: Query parameters tuple

        Returns:
            Query result as dict (for SELECT) or rowcount (for INSERT/UPDATE/DELETE)

        Raises:
            DatabaseError: If query execution fails
        """
        try:
            with self.db_manager.get_cursor() as cursor:
                cursor.execute(query, params)

                # For SELECT queries
                if query.strip().lower().startswith("select"):
                    result = cursor.fetchone()
                    return dict(result) if result else None

                # For INSERT/UPDATE/DELETE
                return {"rowcount": cursor.rowcount}

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise DatabaseError(f"Database query failed: {e}") from e

    # ========================================================================
    # User Data Queries
    # ========================================================================

    def get_user_data_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user data by email address.

        This method retrieves data from the candidate_applications_view,
        which combines information from candidate, job, and application tables.

        Args:
            email: User email address

        Returns:
            Dict with keys: name, surname, cv_content, jobdescription
            Returns None if not found or empty dict on error

        Raises:
            DatabaseError: If query fails

        Example:
            user_data = repo.get_user_data_by_email("mario.rossi@example.com")
            if user_data:
                print(f"Name: {user_data['name']} {user_data['surname']}")
                print(f"CV: {user_data['cv_content'][:100]}...")
        """
        query = "SELECT name, surname, cv_content, jobdescription FROM candidate_applications_view WHERE email = %s"

        try:
            result = self.execute_query(query, (email,))

            if result:
                logger.info(f"Found user data for email: {email}")
                return result

            logger.warning(f"No user data found for email: {email}")
            return {}

        except Exception as e:
            logger.error(f"Failed to get user data for {email}: {e}")
            return {}

    # ========================================================================
    # Candidate Queries
    # ========================================================================

    def get_candidate_data(self, candidate_id: str) -> Optional[Dict[str, str]]:
        """
        Get candidate name and surname by ID.

        This retrieves basic candidate information from the database.

        Args:
            candidate_id: Candidate ID (e.g., 'C01')

        Returns:
            Dict with keys: name, surname
            Returns empty dict on error

        Example:
            candidate = repo.get_candidate_data("C01")
            if candidate:
                print(f"Candidate: {candidate['name']} {candidate['surname']}")
        """
        query = "SELECT name, surname FROM candidate_applications_view WHERE candidate_id = %s"

        try:
            result = self.execute_query(query, (candidate_id,))
            if result:
                logger.info(f"Found candidate data for ID: {candidate_id}")
            else:
                logger.warning(f"No candidate found for ID: {candidate_id}")
            return result if result else {}
        except Exception as e:
            logger.error(f"Failed to get candidate data for {candidate_id}: {e}")
            return {}

    # ========================================================================
    # Job Queries
    # ========================================================================

    def get_job_requirements(self, job_id: str) -> Optional[Dict[str, str]]:
        """
        Get job description by ID.

        Args:
            job_id: Job ID (e.g., 'J001')

        Returns:
            Dict with key: jobdescription
            Returns empty dict on error

        Example:
            job = repo.get_job_requirements("J001")
            if job:
                print(f"Job Description: {job['jobdescription']}")
        """
        query = "SELECT jobdescription FROM candidate_applications_view WHERE job_id = %s"

        try:
            result = self.execute_query(query, (job_id,))
            if result:
                logger.info(f"Found job requirements for ID: {job_id}")
            else:
                logger.warning(f"No job found for ID: {job_id}")
            return result if result else {}
        except Exception as e:
            logger.error(f"Failed to get job requirements for {job_id}: {e}")
            return {}

    # ========================================================================
    # Health Check
    # ========================================================================

    def health_check(self) -> bool:
        """
        Perform database health check.

        Returns:
            True if database is accessible, False otherwise
        """
        return self.db_manager.test_connection()