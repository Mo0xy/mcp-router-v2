"""
Configurazioni centralizzate per il modulo di popolamento database.
Contiene URL API, credenziali, limiti e costanti.
"""
import os
from typing import Final

# ========================================
# CONFIGURAZIONI API
# ========================================
API_BASE_URL: Final[str] = "https://openkeiretsu.it/cvscan-api/api"
API_PASSWORD: Final[str] = "pwd111"

# Endpoint API
ENDPOINT_CV_LIST: Final[str] = f"{API_BASE_URL}/VectorCv/list-titles"
ENDPOINT_CV_DETAILS: Final[str] = f"{API_BASE_URL}/VectorCv/cv-details"
ENDPOINT_ANONYMIZE: Final[str] = f"{API_BASE_URL}/CvMatching/anonymize"
ENDPOINT_MATCH_CV: Final[str] = f"{API_BASE_URL}/CvMatching/upload"
ENDPOINT_JOB_SEARCH: Final[str] = f"{API_BASE_URL}/Jobs/search"

# ========================================
# CONFIGURAZIONI DATABASE
# ========================================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "hrrecruit"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres")
}

# ========================================
# COSTANTI OPERAZIONALI
# ========================================
MAX_CVS_TO_PROCESS: Final[int] = 20
MAX_JOBS_MATCHING: Final[int] = 10

# ID di partenza per le tabelle
STARTING_CV_ID: Final[int] = 7  # CV003
STARTING_JOB_ID: Final[int] = 7  # J003
STARTING_CANDIDATE_ID: Final[int] = 7  # C003

# Pattern ID
CV_ID_PATTERN: Final[str] = "CV{:03d}"
JOB_ID_PATTERN: Final[str] = "J{:03d}"
CANDIDATE_ID_PATTERN: Final[str] = "C{:02d}"

# ========================================
# CONFIGURAZIONI RETRY E TIMEOUT
# ========================================
API_TIMEOUT: Final[int] = 60  # secondi
MAX_RETRIES: Final[int] = 3
RETRY_DELAY: Final[int] = 2  # secondi

# ========================================
# NOMI GIÀ UTILIZZATI (da escludere)
# ========================================
USED_NAMES: Final[set] = {
    ("Mario", "Rossi"),
    ("Sofia", "Verdi")
}
