#!/usr/bin/env python3
"""
Script di test per verificare connettività API e database.
Utile per diagnostica prima di eseguire il popolamento completo.
"""
import sys
import logging

from api_client import CVScanAPIClient
from db_manager import DatabaseManager
from config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_api_connection():
    """Testa la connessione all'API CVScan."""
    print("\n" + "=" * 60)
    print("TEST CONNESSIONE API")
    print("=" * 60)
    
    try:
        client = CVScanAPIClient()
        
        # Test recupero lista CV
        print("→ Recupero lista CV...")
        cv_list = client.get_cv_list()
        print(f"✓ Successo! Trovati {len(cv_list)} CV totali")
        
        # Mostra primi 5
        print("\nPrimi 5 CV:")
        for i, (filename, timestamp) in enumerate(list(cv_list.items())[:5], 1):
            print(f"  {i}. {filename} ({timestamp})")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"✗ Errore: {e}")
        return False


def test_database_connection():
    """Testa la connessione al database PostgreSQL."""
    print("\n" + "=" * 60)
    print("TEST CONNESSIONE DATABASE")
    print("=" * 60)
    
    try:
        db = DatabaseManager()
        
        print("→ Connessione al database...")
        print(f"  Host: {DB_CONFIG['host']}")
        print(f"  Database: {DB_CONFIG['database']}")
        print(f"  User: {DB_CONFIG['user']}")
        
        db.connect()
        print("✓ Connessione stabilita con successo")
        
        # Test query
        print("\n→ Verifica tabelle esistenti...")
        
        # Conta record in cvs
        db.cursor.execute("SELECT COUNT(*) as count FROM cvs")
        cvs_count = db.cursor.fetchone()['count']
        print(f"  - Tabella 'cvs': {cvs_count} record")
        
        # Conta record in jobs
        db.cursor.execute("SELECT COUNT(*) as count FROM jobs")
        jobs_count = db.cursor.fetchone()['count']
        print(f"  - Tabella 'jobs': {jobs_count} record")
        
        # Conta record in candidates
        db.cursor.execute("SELECT COUNT(*) as count FROM candidates")
        candidates_count = db.cursor.fetchone()['count']
        print(f"  - Tabella 'candidates': {candidates_count} record")
        
        # Conta record in candidate_applications
        db.cursor.execute("SELECT COUNT(*) as count FROM candidate_applications")
        applications_count = db.cursor.fetchone()['count']
        print(f"  - Tabella 'candidate_applications': {applications_count} record")
        
        print("\n✓ Tutte le tabelle sono accessibili")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ Errore: {e}")
        return False


def main():
    """Esegue tutti i test."""
    print("\n" + "=" * 60)
    print("VERIFICA PREREQUISITI PER POPOLAMENTO DATABASE")
    print("=" * 60)
    
    api_ok = test_api_connection()
    db_ok = test_database_connection()
    
    print("\n" + "=" * 60)
    print("RIEPILOGO TEST")
    print("=" * 60)
    print(f"API CVScan:   {'✓ OK' if api_ok else '✗ ERRORE'}")
    print(f"Database:     {'✓ OK' if db_ok else '✗ ERRORE'}")
    print("=" * 60)
    
    if api_ok and db_ok:
        print("\n✓ Tutti i test superati! Puoi procedere con populate_db.py")
        return 0
    else:
        print("\n✗ Alcuni test falliti. Verifica la configurazione.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
