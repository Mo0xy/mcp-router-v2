"""
Utilità per il popolamento database.
Include generazione nomi casuali, email e gestione file temporanei.
"""
import random
import tempfile
import os
from typing import Tuple, Set
from config import USED_NAMES


# Liste di nomi e cognomi italiani comuni
FIRST_NAMES = [
    "Luca", "Marco", "Giovanni", "Andrea", "Alessandro", "Francesco", "Matteo",
    "Lorenzo", "Davide", "Simone", "Federico", "Gabriele", "Riccardo", "Tommaso",
    "Maria", "Anna", "Francesca", "Laura", "Chiara", "Giulia", "Sara", "Alessia",
    "Elena", "Valentina", "Martina", "Federica", "Silvia", "Elisa", "Giorgia"
]

LAST_NAMES = [
    "Bianchi", "Ferrari", "Russo", "Romano", "Colombo", "Ricci", "Marino",
    "Greco", "Bruno", "Gallo", "Conti", "De Luca", "Costa", "Giordano",
    "Mancini", "Rizzo", "Lombardi", "Moretti", "Barbieri", "Fontana", "Santoro",
    "Mariani", "Rinaldi", "Caruso", "Ferrara", "Galli", "Martini", "Leone"
]


def generate_unique_name(used_names: Set[Tuple[str, str]]) -> Tuple[str, str]:
    """
    Genera un nome e cognome casuali non presenti nel set di nomi già utilizzati.
    
    Args:
        used_names: Set di tuple (nome, cognome) già utilizzate
        
    Returns:
        Tuple (nome, cognome) univoca
        
    Raises:
        ValueError: Se non è possibile generare un nome unico dopo 1000 tentativi
    """
    max_attempts = 1000
    attempts = 0
    
    while attempts < max_attempts:
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        
        if (first_name, last_name) not in used_names:
            return (first_name, last_name)
        
        attempts += 1
    
    raise ValueError("Impossibile generare un nome unico dopo 1000 tentativi")


def generate_email(first_name: str, last_name: str) -> str:
    """
    Genera un indirizzo email nel formato nome.cognome@example.com.
    
    Args:
        first_name: Nome
        last_name: Cognome
        
    Returns:
        Email formattata
    """
    # Rimuovi spazi e converti in minuscolo
    first_clean = first_name.strip().lower().replace(" ", "")
    last_clean = last_name.strip().lower().replace(" ", "")
    
    return f"{first_clean}.{last_clean}@example.com"


def create_temp_file(content: str, suffix: str = ".txt") -> str:
    """
    Crea un file temporaneo con il contenuto specificato.
    
    Args:
        content: Contenuto da scrivere nel file
        suffix: Estensione del file (default: .txt)
        
    Returns:
        Path del file temporaneo creato
    """
    fd, temp_path = tempfile.mkstemp(suffix=suffix, text=True)
    
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        return temp_path
    except Exception as e:
        os.close(fd)
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise e


def delete_temp_file(file_path: str) -> None:
    """
    Elimina un file temporaneo in modo sicuro.
    
    Args:
        file_path: Path del file da eliminare
    """
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        print(f"Warning: Impossibile eliminare il file temporaneo {file_path}: {e}")


def sanitize_filename(filename: str) -> str:
    """
    Sanitizza un nome file rimuovendo caratteri non validi.
    
    Args:
        filename: Nome file originale
        
    Returns:
        Nome file sanitizzato
    """
    # Rimuovi caratteri non validi per i filesystem
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    return filename.strip()
