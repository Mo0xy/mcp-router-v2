"""
Modelli di dati per le entità del dominio.
Utilizzano dataclass per una rappresentazione pulita e type-safe.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CVDetails:
    """Rappresenta i dettagli di un CV recuperato dall'API."""
    filename: str
    cv_text: str
    semantic_profile: str
    last_modified: str
    upload_date: str
    point_id: str
    content_hash: str
    file_size: int
    text_length: int
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'CVDetails':
        """
        Crea un'istanza CVDetails da una risposta API.
        
        Args:
            data: Dizionario dalla risposta API
            
        Returns:
            Istanza CVDetails
        """
        return cls(
            filename=data.get('filename', ''),
            cv_text=data.get('cvText', ''),
            semantic_profile=data.get('semanticProfile', ''),
            last_modified=data.get('lastModified', ''),
            upload_date=data.get('uploadDate', ''),
            point_id=data.get('pointId', ''),
            content_hash=data.get('contentHash', ''),
            file_size=data.get('fileSize', 0),
            text_length=data.get('textLength', 0)
        )


@dataclass
class JobMatch:
    """Rappresenta un match tra CV e job posting."""
    job_id: str
    title: str
    match_score: int
    reasoning: str
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'JobMatch':
        """
        Crea un'istanza JobMatch da una risposta API.
        
        Args:
            data: Dizionario dalla risposta API
            
        Returns:
            Istanza JobMatch
        """
        return cls(
            job_id=data.get('id', ''),
            title=data.get('title', ''),
            match_score=data.get('matchScore', 0),
            reasoning=data.get('reasoning', '')
        )


@dataclass
class JobDetails:
    """Rappresenta i dettagli di un job posting."""
    title: str
    description: str
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'JobDetails':
        """
        Crea un'istanza JobDetails da una risposta API.
        
        Args:
            data: Dizionario dalla risposta API
            
        Returns:
            Istanza JobDetails
        """
        # L'API potrebbe restituire una lista di job, prendiamo il primo
        if isinstance(data, list) and len(data) > 0:
            job_data = data[0]
        else:
            job_data = data
            
        return cls(
            title=job_data.get('title', ''),
            description=job_data.get('description', '')
        )


@dataclass
class CVRecord:
    """Rappresenta un record nella tabella cvs del database."""
    id: str
    cv_filename: str
    cv_content: str
    semantic_profile: str


@dataclass
class JobRecord:
    """Rappresenta un record nella tabella jobs del database."""
    id: str
    title: str
    description: str


@dataclass
class CandidateRecord:
    """Rappresenta un record nella tabella candidates del database."""
    id: str
    name: str
    surname: str
    email: str


@dataclass
class ApplicationRecord:
    """Rappresenta un record nella tabella candidate_applications del database."""
    candidate_id: str
    applied_to: str
    cv_id: str
    application_date: Optional[datetime] = None


@dataclass
class ProcessingResult:
    """Rappresenta il risultato del processamento di un singolo CV."""
    success: bool
    cv_filename: str
    cv_id: Optional[str] = None
    job_id: Optional[str] = None
    candidate_id: Optional[str] = None
    error_message: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
