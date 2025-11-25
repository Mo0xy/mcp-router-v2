"""
Servizi business per il processamento dei CV.
Orchestrazione completa del flusso: API -> Anonimizzazione -> Matching -> DB.
"""
import logging
from typing import Set, Tuple, Optional

from api_client import CVScanAPIClient
from db_manager import DatabaseManager
from models import (
    CVRecord, JobRecord, CandidateRecord, ApplicationRecord,
    ProcessingResult, CVDetails, JobMatch
)
from utils import (
    generate_unique_name, generate_email,
    create_temp_file, delete_temp_file
)
from config import USED_NAMES


logger = logging.getLogger(__name__)


class CVProcessingService:
    """
    Servizio per il processamento completo di un CV.
    Coordina API client, database manager e utility.
    """
    
    def __init__(
        self,
        api_client: CVScanAPIClient,
        db_manager: DatabaseManager
    ):
        """
        Inizializza il servizio.
        
        Args:
            api_client: Client per le API CVScan
            db_manager: Manager del database
        """
        self.api_client = api_client
        self.db_manager = db_manager
        self.used_names: Set[Tuple[str, str]] = set(USED_NAMES)
    
    def process_cv(self, filename: str) -> ProcessingResult:
        """
        Processa un singolo CV dall'inizio alla fine.
        
        Flusso:
        1. Verifica se CV esiste già nel DB (skip se presente)
        2. Recupera dettagli CV dall'API
        3. Anonimizza il CV
        4. Inserisce CV nel DB
        5. Match CV con job posting
        6. Recupera dettagli job
        7. Inserisce/riusa job nel DB
        8. Genera candidato fittizio
        9. Inserisce candidato nel DB
        10. Crea application
        11. Commit transazione
        
        Args:
            filename: Nome del file CV da processare
            
        Returns:
            ProcessingResult con dettagli del processamento
        """
        temp_cv_file = None
        temp_anonymized_file = None
        
        try:
            # ========================================
            # STEP 1: Verifica se CV esiste già
            # ========================================
            if self.db_manager.cv_exists(filename):
                logger.info(f"CV {filename} già presente nel DB, skip")
                return ProcessingResult(
                    success=True,
                    cv_filename=filename,
                    skipped=True,
                    skip_reason="CV già presente nel database"
                )
            
            # ========================================
            # STEP 2: Recupera dettagli CV
            # ========================================
            logger.info(f"Recupero dettagli per CV: {filename}")
            cv_details: CVDetails = self.api_client.get_cv_details(filename)
            
            if not cv_details.cv_text:
                raise ValueError(f"CV {filename} non contiene testo")
            
            # ========================================
            # STEP 3: Anonimizza CV
            # ========================================
            logger.info(f"Anonimizzazione CV: {filename}")
            temp_cv_file = create_temp_file(cv_details.cv_text)
            anonymized_text = self.api_client.anonymize_cv(
                cv_details.cv_text,
                temp_cv_file
            )
            
            # ========================================
            # STEP 4: Inserisce CV nel DB
            # ========================================
            cv_id = self.db_manager.get_next_cv_id()
            cv_record = CVRecord(
                id=cv_id,
                cv_filename=filename,
                cv_content=anonymized_text,
                semantic_profile=cv_details.semantic_profile
            )
            
            logger.info(f"Inserimento CV nel DB: {cv_id}")
            self.db_manager.insert_cv(cv_record)
            
            # ========================================
            # STEP 5: Match CV con job posting
            # ========================================
            logger.info(f"Matching CV {cv_id} con job postings")
            temp_anonymized_file = create_temp_file(anonymized_text)
            job_match: Optional[JobMatch] = self.api_client.match_cv_to_jobs(
                temp_anonymized_file
            )

            if not job_match:
                logger.warning(f"Nessun job match trovato per CV {cv_id}, rollback")
                self.db_manager.rollback()
                return ProcessingResult(
                    success=False,
                    cv_filename=filename,
                    error_message="Nessun job match trovato per questo CV"
                )
            
            logger.info(
                f"Best match per CV {cv_id}: {job_match.title} "
                f"(score: {job_match.match_score})"
            )
            
            # ========================================
            # STEP 6: Recupera dettagli job
            # ========================================
            logger.info(f"Recupero dettagli job: {job_match.title}")
            job_details = self.api_client.search_job(job_match.title)
            
            # ========================================
            # STEP 7: Inserisce/riusa job nel DB
            # ========================================
            existing_job_id = self.db_manager.job_exists_by_title(job_details.title)
            
            if existing_job_id:
                logger.info(
                    f"Job '{job_details.title}' già presente con ID {existing_job_id}, "
                    "riutilizzo"
                )
                job_id = existing_job_id
            else:
                job_id = self.db_manager.get_next_job_id()
                job_record = JobRecord(
                    id=job_id,
                    title=job_details.title,
                    description=job_details.description
                )
                logger.info(f"Inserimento nuovo job nel DB: {job_id}")
                self.db_manager.insert_job(job_record)
            
            # ========================================
            # STEP 8-9: Genera e inserisce candidato
            # ========================================
            candidate_id = self.db_manager.get_next_candidate_id()
            first_name, last_name = generate_unique_name(self.used_names)
            self.used_names.add((first_name, last_name))
            email = generate_email(first_name, last_name)
            
            candidate_record = CandidateRecord(
                id=candidate_id,
                name=first_name,
                surname=last_name,
                email=email
            )
            
            logger.info(
                f"Inserimento candidato nel DB: {candidate_id} "
                f"({first_name} {last_name})"
            )
            self.db_manager.insert_candidate(candidate_record)
            
            # ========================================
            # STEP 10: Crea application
            # ========================================
            application_record = ApplicationRecord(
                candidate_id=candidate_id,
                applied_to=job_id,
                cv_id=cv_id
            )
            
            logger.info(
                f"Inserimento application: {candidate_id} -> {job_id} "
                f"con CV {cv_id}"
            )
            self.db_manager.insert_application(application_record)
            
            # ========================================
            # STEP 11: Commit transazione
            # ========================================
            self.db_manager.commit()
            logger.info(f"[OK] Processamento CV {filename} completato con successo")
            
            return ProcessingResult(
                success=True,
                cv_filename=filename,
                cv_id=cv_id,
                job_id=job_id,
                candidate_id=candidate_id
            )
            
        except Exception as e:
            # Rollback in caso di errore
            logger.error(f"[ERROR] Errore nel processamento CV {filename}: {e}")
            self.db_manager.rollback()
            
            return ProcessingResult(
                success=False,
                cv_filename=filename,
                error_message=str(e)
            )
            
        finally:
            # Pulizia file temporanei
            if temp_cv_file:
                delete_temp_file(temp_cv_file)
            if temp_anonymized_file:
                delete_temp_file(temp_anonymized_file)
