#!/usr/bin/env python3
"""
Script principale per il popolamento del database HR Recruit.

Esegue il processo completo:
1. Recupera lista CV dall'API
2. Per ogni CV (max 50):
   - Verifica se esiste già
   - Recupera dettagli e anonimizza
   - Inserisce nel DB
   - Trova job match migliore
   - Inserisce job e candidato
   - Crea application

Utilizzo:
    python populate_db.py
"""
import logging
import sys
from typing import List
from tqdm import tqdm

from config import MAX_CVS_TO_PROCESS
from api_client import CVScanAPIClient
from db_manager import DatabaseManager
from services import CVProcessingService
from models import ProcessingResult


# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('db_population.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Funzione principale per il popolamento del database."""
    
    logger.info("=" * 80)
    logger.info("AVVIO PROCESSO DI POPOLAMENTO DATABASE")
    logger.info("=" * 80)
    
    api_client = None
    db_manager = None
    
    try:
        # ========================================
        # INIZIALIZZAZIONE
        # ========================================
        logger.info("Inizializzazione client API e database manager...")
        api_client = CVScanAPIClient()
        db_manager = DatabaseManager()
        db_manager.connect()
        
        processing_service = CVProcessingService(api_client, db_manager)
        
        # ========================================
        # RECUPERO LISTA CV
        # ========================================
        logger.info("Recupero lista CV dall'API...")
        cv_list = api_client.get_cv_list()
        
        total_cvs = len(cv_list)
        logger.info(f"Trovati {total_cvs} CV totali")
        
        # Limita ai primi MAX_CVS_TO_PROCESS
        cv_filenames = list(cv_list.keys())[-MAX_CVS_TO_PROCESS:]
        logger.info(f"Processamento dei primi {len(cv_filenames)} CV")
        
        # ========================================
        # PROCESSAMENTO CV
        # ========================================
        results: List[ProcessingResult] = []
        
        print("\n")
        logger.info("Inizio processamento CV...")
        
        # Progress bar per monitoraggio
        with tqdm(total=len(cv_filenames), desc="Processamento CV", unit="cv") as pbar:
            for filename in cv_filenames:
                pbar.set_description(f"Processamento: {filename[:30]}...")
                
                # Processa singolo CV
                result = processing_service.process_cv(filename)
                results.append(result)
                
                # Aggiorna progress bar
                if result.success:
                    if result.skipped:
                        pbar.set_postfix(status="SKIPPED")
                    else:
                        pbar.set_postfix(
                            status="OK",
                            cv=result.cv_id,
                            job=result.job_id
                        )
                else:
                    pbar.set_postfix(status="ERROR")
                    # Se il commit fallisce, usciamo dal ciclo
                    if "commit" in result.error_message.lower():
                        logger.error(
                            "Errore critico nel commit, interruzione processo"
                        )
                        pbar.close()
                        break
                
                pbar.update(1)
        
        # ========================================
        # RIEPILOGO FINALE
        # ========================================
        print("\n")
        logger.info("=" * 80)
        logger.info("RIEPILOGO PROCESSAMENTO")
        logger.info("=" * 80)
        
        success_count = sum(1 for r in results if r.success and not r.skipped)
        skipped_count = sum(1 for r in results if r.skipped)
        error_count = sum(1 for r in results if not r.success)

        logger.info(f"Totale CV processati: {len(results)}")
        logger.info(f"  [OK] Successi:         {success_count}")
        logger.info(f"  [SKIP] Skippati:       {skipped_count}")
        logger.info(f"  [ERROR] Errori:        {error_count}")
        
        # Dettaglio errori
        if error_count > 0:
            logger.info("\nDettaglio errori:")
            for result in results:
                if not result.success:
                    logger.error(
                        f"  - {result.cv_filename}: {result.error_message}"
                    )
        
        # Statistiche finali
        logger.info("\nStatistiche finali:")
        logger.info(f"  Nuovi CV inseriti:        {success_count}")
        logger.info(f"  Nuovi candidati creati:   {success_count}")
        
        # Conta job unici creati
        unique_jobs = set(
            r.job_id for r in results 
            if r.success and not r.skipped and r.job_id
        )
        logger.info(f"  Job processati:           {len(unique_jobs)}")
        
        logger.info("=" * 80)
        logger.info("PROCESSO COMPLETATO")
        logger.info("=" * 80)
        
        return 0 if error_count == 0 else 1

    except KeyboardInterrupt:
        logger.warning("\n[WARNING] Processo interrotto dall'utente")
        return 130

    except Exception as e:
        logger.error(f"\n[ERROR] Errore fatale: {e}", exc_info=True)
        return 1
        
    finally:
        # ========================================
        # PULIZIA
        # ========================================
        if db_manager:
            db_manager.close()
        if api_client:
            api_client.close()
        
        logger.info("Risorse rilasciate")


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
