"""
Gestione database PostgreSQL.
Gestisce connessioni, transazioni e operazioni CRUD sulle tabelle.
"""
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from config import (
    DB_CONFIG, CV_ID_PATTERN, JOB_ID_PATTERN,
    CANDIDATE_ID_PATTERN, STARTING_CV_ID,
    STARTING_JOB_ID, STARTING_CANDIDATE_ID
)
from models import CVRecord, JobRecord, CandidateRecord, ApplicationRecord


logger = logging.getLogger(__name__)


class DatabaseManager:
    """Gestisce le operazioni sul database PostgreSQL."""
    
    def __init__(self, db_config: Dict[str, Any] = None):
        """
        Inizializza il manager del database.
        
        Args:
            db_config: Configurazione database (usa DB_CONFIG se None)
        """
        self.db_config = db_config or DB_CONFIG
        self.connection = None
        self.cursor = None
        
        # Contatori per gli ID
        self._cv_counter = STARTING_CV_ID
        self._job_counter = STARTING_JOB_ID
        self._candidate_counter = STARTING_CANDIDATE_ID
    
    def connect(self) -> None:
        """
        Stabilisce la connessione al database.
        
        Raises:
            psycopg2.Error: Se la connessione fallisce
        """
        try:
            self.connection = psycopg2.connect(**self.db_config)
            self.cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            logger.info("Connessione al database stabilita con successo")
        except psycopg2.Error as e:
            logger.error(f"Errore nella connessione al database: {e}")
            raise
    
    def close(self) -> None:
        """Chiude la connessione al database."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Connessione al database chiusa")
    
    def commit(self) -> None:
        """Esegue il commit della transazione corrente."""
        if self.connection:
            self.connection.commit()
    
    def rollback(self) -> None:
        """Esegue il rollback della transazione corrente."""
        if self.connection:
            self.connection.rollback()
    
    # ========================================
    # GESTIONE CV
    # ========================================
    
    def cv_exists(self, filename: str) -> bool:
        """
        Verifica se un CV con il filename specificato esiste già.
        
        Args:
            filename: Nome del file CV
            
        Returns:
            True se esiste, False altrimenti
        """
        query = "SELECT COUNT(*) as count FROM cvs WHERE cv_filename = %s"
        self.cursor.execute(query, (filename,))
        result = self.cursor.fetchone()
        return result['count'] > 0
    
    def insert_cv(self, cv_record: CVRecord) -> bool:
        """
        Inserisce un nuovo CV nel database.
        
        Args:
            cv_record: Record CV da inserire
            
        Returns:
            True se l'inserimento ha successo
            
        Raises:
            psycopg2.Error: Se l'inserimento fallisce
        """
        query = """
            INSERT INTO cvs (id, cv_filename, cv_content, semantic_profile)
            VALUES (%s, %s, %s, %s)
        """
        
        try:
            self.cursor.execute(query, (
                cv_record.id,
                cv_record.cv_filename,
                cv_record.cv_content,
                cv_record.semantic_profile
            ))
            logger.info(f"CV {cv_record.id} inserito con successo")
            return True
        except psycopg2.Error as e:
            logger.error(f"Errore nell'inserimento del CV {cv_record.id}: {e}")
            raise
    
    def get_next_cv_id(self) -> str:
        """
        Genera il prossimo ID disponibile per un CV.
        
        Returns:
            ID formattato (es. CV003)
        """
        cv_id = CV_ID_PATTERN.format(self._cv_counter)
        self._cv_counter += 1
        return cv_id
    
    # ========================================
    # GESTIONE JOB
    # ========================================
    
    def job_exists_by_title(self, title: str) -> Optional[str]:
        """
        Verifica se un job con il titolo specificato esiste già.
        
        Args:
            title: Titolo del job
            
        Returns:
            ID del job se esiste, None altrimenti
        """
        query = "SELECT id FROM jobs WHERE title = %s"
        self.cursor.execute(query, (title,))
        result = self.cursor.fetchone()
        return result['id'] if result else None
    
    def insert_job(self, job_record: JobRecord) -> bool:
        """
        Inserisce un nuovo job nel database.
        
        Args:
            job_record: Record job da inserire
            
        Returns:
            True se l'inserimento ha successo
            
        Raises:
            psycopg2.Error: Se l'inserimento fallisce
        """
        query = """
            INSERT INTO jobs (id, title, description)
            VALUES (%s, %s, %s)
        """
        
        try:
            self.cursor.execute(query, (
                job_record.id,
                job_record.title,
                job_record.description
            ))
            logger.info(f"Job {job_record.id} inserito con successo")
            return True
        except psycopg2.Error as e:
            logger.error(f"Errore nell'inserimento del job {job_record.id}: {e}")
            raise
    
    def get_next_job_id(self) -> str:
        """
        Genera il prossimo ID disponibile per un job.
        
        Returns:
            ID formattato (es. J003)
        """
        job_id = JOB_ID_PATTERN.format(self._job_counter)
        self._job_counter += 1
        return job_id
    
    # ========================================
    # GESTIONE CANDIDATE
    # ========================================
    
    def candidate_exists(self, email: str) -> bool:
        """
        Verifica se un candidato con l'email specificata esiste già.
        
        Args:
            email: Email del candidato
            
        Returns:
            True se esiste, False altrimenti
        """
        query = "SELECT COUNT(*) as count FROM candidates WHERE email = %s"
        self.cursor.execute(query, (email,))
        result = self.cursor.fetchone()
        return result['count'] > 0
    
    def insert_candidate(self, candidate_record: CandidateRecord) -> bool:
        """
        Inserisce un nuovo candidato nel database.
        
        Args:
            candidate_record: Record candidato da inserire
            
        Returns:
            True se l'inserimento ha successo
            
        Raises:
            psycopg2.Error: Se l'inserimento fallisce
        """
        query = """
            INSERT INTO candidates (id, name, surname, email)
            VALUES (%s, %s, %s, %s)
        """
        
        try:
            self.cursor.execute(query, (
                candidate_record.id,
                candidate_record.name,
                candidate_record.surname,
                candidate_record.email
            ))
            logger.info(f"Candidate {candidate_record.id} inserito con successo")
            return True
        except psycopg2.Error as e:
            logger.error(f"Errore nell'inserimento del candidate {candidate_record.id}: {e}")
            raise
    
    def get_next_candidate_id(self) -> str:
        """
        Genera il prossimo ID disponibile per un candidato.
        
        Returns:
            ID formattato (es. C03)
        """
        candidate_id = CANDIDATE_ID_PATTERN.format(self._candidate_counter)
        self._candidate_counter += 1
        return candidate_id
    
    # ========================================
    # GESTIONE APPLICATION
    # ========================================
    
    def insert_application(self, application_record: ApplicationRecord) -> bool:
        """
        Inserisce una nuova application nel database.
        
        Args:
            application_record: Record application da inserire
            
        Returns:
            True se l'inserimento ha successo
            
        Raises:
            psycopg2.Error: Se l'inserimento fallisce
        """
        query = """
            INSERT INTO candidate_applications 
            (candidate_id, applied_to, cv_id, application_date)
            VALUES (%s, %s, %s, COALESCE(%s, CURRENT_DATE))
        """
        
        try:
            self.cursor.execute(query, (
                application_record.candidate_id,
                application_record.applied_to,
                application_record.cv_id,
                application_record.application_date
            ))
            logger.info(
                f"Application inserita: candidate {application_record.candidate_id} "
                f"-> job {application_record.applied_to}"
            )
            return True
        except psycopg2.Error as e:
            logger.error(f"Errore nell'inserimento dell'application: {e}")
            raise
