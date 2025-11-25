"""
Client per le chiamate API a CVScan.
Gestisce autenticazione, retry logic e parsing delle risposte.
"""
import requests
import time
import logging
from typing import Dict, List, Optional
from urllib.parse import quote

from config import (
    API_PASSWORD, ENDPOINT_CV_LIST, ENDPOINT_CV_DETAILS,
    ENDPOINT_ANONYMIZE, ENDPOINT_MATCH_CV, ENDPOINT_JOB_SEARCH,
    API_TIMEOUT, MAX_RETRIES, RETRY_DELAY, MAX_JOBS_MATCHING
)
from models import CVDetails, JobMatch, JobDetails


logger = logging.getLogger(__name__)


class CVScanAPIClient:
    """Client per interagire con l'API CVScan."""
    
    def __init__(self, password: str = API_PASSWORD):
        """
        Inizializza il client API.
        
        Args:
            password: Password per l'autenticazione API
        """
        self.password = password
        self.session = requests.Session()
        
    def _make_request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> requests.Response:
        """
        Esegue una richiesta HTTP con retry logic.
        
        Args:
            method: Metodo HTTP (GET, POST, ecc.)
            url: URL della richiesta
            **kwargs: Argomenti aggiuntivi per requests
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: Se tutti i tentativi falliscono
        """
        last_exception = None
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=API_TIMEOUT,
                    **kwargs
                )
                response.raise_for_status()
                return response
                
            except requests.RequestException as e:
                last_exception = e
                logger.warning(
                    f"Tentativo {attempt}/{MAX_RETRIES} fallito per {url}: {e}"
                )
                
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    
        logger.error(f"Tutti i tentativi falliti per {url}")
        raise last_exception
    
    def get_cv_list(self) -> Dict[str, str]:
        """
        Recupera la lista di tutti i CV disponibili.
        
        Returns:
            Dizionario {filename: timestamp}
            
        Raises:
            requests.RequestException: Se la richiesta fallisce
        """
        params = {"password": self.password}
        
        response = self._make_request_with_retry(
            "GET",
            ENDPOINT_CV_LIST,
            params=params
        )
        
        data = response.json()
        return data.get("titles", {})
    
    def get_cv_details(self, filename: str) -> CVDetails:
        """
        Recupera i dettagli di un CV specifico.
        
        Args:
            filename: Nome del file CV
            
        Returns:
            Oggetto CVDetails
            
        Raises:
            requests.RequestException: Se la richiesta fallisce
        """
        # URL-encode del filename per gestire caratteri speciali
        encoded_filename = quote(filename, safe='')
        url = f"{ENDPOINT_CV_DETAILS}/{encoded_filename}"
        params = {"password": self.password}
        
        response = self._make_request_with_retry(
            "GET",
            url,
            params=params
        )
        
        data = response.json()
        return CVDetails.from_api_response(data)
    
    def anonymize_cv(self, cv_text: str, temp_file_path: str) -> str:
        """
        Anonimizza un CV tramite l'API.
        
        Args:
            cv_text: Testo del CV da anonimizzare
            temp_file_path: Path del file temporaneo contenente il CV
            
        Returns:
            Testo del CV anonimizzato
            
        Raises:
            requests.RequestException: Se la richiesta fallisce
        """
        with open(temp_file_path, 'rb') as f:
            files = {
                'file': (temp_file_path, f, 'text/plain')
            }
            data = {
                'password': self.password
            }
            
            response = self._make_request_with_retry(
                "POST",
                ENDPOINT_ANONYMIZE,
                files=files,
                data=data
            )
        
        result = response.json()
        return result.get('anonymizedText', cv_text)

    def match_cv_to_jobs(self, anonymized_cv_path: str) -> Optional[JobMatch]:
        """
        Trova il job posting con il miglior match per un CV.
        
        Args:
            anonymized_cv_path: Path del file CV anonimizzato
            
        Returns:
            JobMatch con il punteggio più alto, o None se nessun match
            
        Raises:
            requests.RequestException: Se la richiesta fallisce
        """
        try:
            # Verifica dimensione file
            import os
            file_size = os.path.getsize(anonymized_cv_path)
            logger.info(f"Dimensione file CV: {file_size} bytes")

            with open(anonymized_cv_path, 'rb') as f:
                files = {
                    'file': (anonymized_cv_path, f, 'text/plain')
                }
                data = {
                    'password': self.password,
                    'maxJobs': str(MAX_JOBS_MATCHING),
                    'anonymize': 'false',
                    'location': ''
                }

                response = self._make_request_with_retry(
                    "POST",
                    ENDPOINT_MATCH_CV,
                    files=files,
                    data=data
                )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                logger.warning(
                    f"API returned 400 Bad Request. "
                    f"Possible issue with CV content or format. Skipping match."
                )
                return None
            raise
        except Exception as e:
            logger.error(f"Unexpected error during CV matching: {e}")
            return None

        result = response.json()

        # Estrai la lista di match dal secondo passaggio
        matches_data = result.get('secondPass', {}).get('matches', [])

        if not matches_data:
            logger.warning("Nessun match trovato per il CV")
            return None

        # Prendi il primo elemento (ha il match score più alto)
        best_match_data = matches_data[0]
        return JobMatch.from_api_response(best_match_data)
    
    def search_job(self, job_title: str) -> JobDetails:
        """
        Cerca i dettagli di un job per titolo.
        
        Args:
            job_title: Titolo del job da cercare
            
        Returns:
            Oggetto JobDetails
            
        Raises:
            requests.RequestException: Se la richiesta fallisce
        """
        # URL-encode del titolo per gestire caratteri speciali e spazi
        encoded_title = quote(job_title, safe='')
        url = f"{ENDPOINT_JOB_SEARCH}/{encoded_title}"
        
        response = self._make_request_with_retry(
            "GET",
            url
        )
        
        data = response.json()
        return JobDetails.from_api_response(data)
    
    def close(self):
        """Chiude la sessione HTTP."""
        self.session.close()
