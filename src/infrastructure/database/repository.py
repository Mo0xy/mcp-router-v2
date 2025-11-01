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
from typing import Optional, List, Dict, Any, Tuple
from psycopg2.extras import RealDictRow

from src.infrastructure.database.connection import DatabaseConnectionManager
from src.infrastructure.database.models import (
    CandidateDB,
    JobDB,
    CandidateApplicationDB,
    UserDataByEmail,
)
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
            fetch_one: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a generic database query.

        Args:
            query: SQL query string
            params: Query parameters tuple
            fetch_one: If True, fetch single row; if False, return rowcount

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
                    if fetch_one:
                        result = cursor.fetchone()
                        return dict(result) if result else None
                    else:
                        results = cursor.fetchall()
                        return [dict(row) for row in results]

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

    def get_user_data_by_email(self, email: str) -> Optional[UserDataByEmail]:
        """
        Get complete user data by email address.

        This method retrieves aggregated data from the candidate_applications_view,
        which combines information from candidate, job, and application tables.

        Args:
            email: User email address

        Returns:
            UserDataByEmail model instance or None if not found

        Raises:
            DatabaseError: If query fails

        Example:
            user_data = repo.get_user_data_by_email("mario.rossi@example.com")
            if user_data:
                print(f"Name: {user_data.name} {user_data.surname}")
                print(f"CV: {user_data.cv_content[:100]}...")
        """
        query = """
            SELECT 
                name,
                surname,
                cv_content,
                jobdescription,
                email,
                phone,
                candidate_id,
                job_id
            FROM candidate_applications_view
            WHERE email = %s
            LIMIT 1
        """

        try:
            result = self.execute_query(query, (email,), fetch_one=True)

            if result:
                logger.info(f"Found user data for email: {email}")
                return UserDataByEmail.from_db_row(result)

            logger.warning(f"No user data found for email: {email}")
            return None

        except Exception as e:
            logger.error(f"Failed to get user data for {email}: {e}")
            raise DatabaseError(f"Failed to retrieve user data: {e}") from e

    # ========================================================================
    # Candidate Queries
    # ========================================================================

    def get_candidate_by_id(self, candidate_id: str) -> Optional[CandidateDB]:
        """
        Get candidate data by ID.

        Args:
            candidate_id: Candidate ID (e.g., 'C01')

        Returns:
            CandidateDB model or None if not found
        """
        query = """
            SELECT id, name, surname, email, phone, created_at, updated_at
            FROM candidates
            WHERE id = %s
        """

        try:
            result = self.execute_query(query, (candidate_id,), fetch_one=True)
            return CandidateDB(**result) if result else None
        except Exception as e:
            logger.error(f"Failed to get candidate {candidate_id}: {e}")
            raise DatabaseError(f"Failed to retrieve candidate: {e}") from e

    def get_candidate_data(self, candidate_id: str) -> Optional[Dict[str, str]]:
        """
        Get candidate name and surname by ID.

        This is a lighter query for cases where only basic info is needed.

        Args:
            candidate_id: Candidate ID

        Returns:
            Dict with 'name' and 'surname' keys, or None
        """
        query = """
            SELECT name, surname 
            FROM candidate_applications_view 
            WHERE candidate_id = %s
            LIMIT 1
        """

        try:
            result = self.execute_query(query, (candidate_id,), fetch_one=True)
            return result
        except Exception as e:
            logger.error(f"Failed to get candidate data for {candidate_id}: {e}")
            raise DatabaseError(f"Failed to retrieve candidate data: {e}") from e

    # ========================================================================
    # Job Queries
    # ========================================================================

    def get_job_by_id(self, job_id: str) -> Optional[JobDB]:
        """
        Get job data by ID.

        Args:
            job_id: Job ID (e.g., 'J001')

        Returns:
            JobDB model or None if not found
        """
        query = """
            SELECT id, title, description, requirements, created_at, updated_at
            FROM jobs
            WHERE id = %s
        """

        try:
            result = self.execute_query(query, (job_id,), fetch_one=True)
            return JobDB(**result) if result else None
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            raise DatabaseError(f"Failed to retrieve job: {e}") from e

    def get_job_requirements(self, job_id: str) -> Optional[Dict[str, str]]:
        """
        Get job description by ID.

        Args:
            job_id: Job ID

        Returns:
            Dict with 'jobdescription' key, or None
        """
        query = """
            SELECT jobdescription 
            FROM candidate_applications_view 
            WHERE job_id = %s
            LIMIT 1
        """

        try:
            result = self.execute_query(query, (job_id,), fetch_one=True)
            return result
        except Exception as e:
            logger.error(f"Failed to get job requirements for {job_id}: {e}")
            raise DatabaseError(f"Failed to retrieve job requirements: {e}") from e

    # ========================================================================
    # Application Queries
    # ========================================================================

    def get_applications_by_candidate(
            self, candidate_id: str
    ) -> List[CandidateApplicationDB]:
        """
        Get all applications for a candidate.

        Args:
            candidate_id: Candidate ID

        Returns:
            List of CandidateApplicationDB models
        """
        query = """
            SELECT 
                candidate_id, 
                job_id, 
                cv_filename, 
                cv_content,
                application_date,
                status
            FROM candidate_applications
            WHERE candidate_id = %s
            ORDER BY application_date DESC
        """

        try:
            results = self.execute_query(query, (candidate_id,), fetch_one=False)
            return [CandidateApplicationDB(**row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get applications for {candidate_id}: {e}")
            raise DatabaseError(f"Failed to retrieve applications: {e}") from e

    def get_applications_by_job(self, job_id: str) -> List[CandidateApplicationDB]:
        """
        Get all applications for a job.

        Args:
            job_id: Job ID

        Returns:
            List of CandidateApplicationDB models
        """
        query = """
            SELECT 
                candidate_id, 
                job_id, 
                cv_filename, 
                cv_content,
                application_date,
                status
            FROM candidate_applications
            WHERE job_id = %s
            ORDER BY application_date DESC
        """

        try:
            results = self.execute_query(query, (job_id,), fetch_one=False)
            return [CandidateApplicationDB(**row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get applications for job {job_id}: {e}")
            raise DatabaseError(f"Failed to retrieve applications: {e}") from e

    # ========================================================================
    # Write Operations (for future use)
    # ========================================================================

    def insert_candidate(self, candidate: CandidateDB) -> bool:
        """
        Insert a new candidate into the database.

        Args:
            candidate: CandidateDB model instance

        Returns:
            True if successful
        """
        query = """
            INSERT INTO candidates (id, name, surname, email, phone)
            VALUES (%s, %s, %s, %s, %s)
        """

        try:
            self.execute_query(
                query,
                (
                    candidate.id,
                    candidate.name,
                    candidate.surname,
                    candidate.email,
                    candidate.phone,
                ),
                fetch_one=False,
            )
            logger.info(f"Inserted candidate: {candidate.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to insert candidate: {e}")
            raise DatabaseError(f"Failed to insert candidate: {e}") from e

    def update_candidate_email(self, candidate_id: str, new_email: str) -> bool:
        """
        Update candidate email.

        Args:
            candidate_id: Candidate ID
            new_email: New email address

        Returns:
            True if successful
        """
        query = """
            UPDATE candidates
            SET email = %s, updated_at = NOW()
            WHERE id = %s
        """

        try:
            result = self.execute_query(query, (new_email, candidate_id), fetch_one=False)
            logger.info(f"Updated email for candidate {candidate_id}")
            return result["rowcount"] > 0
        except Exception as e:
            logger.error(f"Failed to update candidate email: {e}")
            raise DatabaseError(f"Failed to update candidate: {e}") from e

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