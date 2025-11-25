"""
Question Evaluator Module - STAR/BEI Compliance Version
========================================================

Valutazione delle domande di colloquio basata su standard professionali:
- Conformità STAR (Situation, Task, Action, Result)
- Conformità BEI (Behavioral Event Interview)
- Personalizzazione CV
- Pertinenza JD
- Verifica presenza effettiva di riferimenti

Basato su:
- McDaniel et al. (1994) - Structured interviews validity
- Zheng et al. (2023) - LLM-as-a-Judge per compliance checking
"""
import re
import json
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import numpy as np
from src.infrastructure.database.connection import get_db_manager
from src.infrastructure.database.repository import DatabaseRepository


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Question:
    """Struttura dati per una domanda di colloquio"""
    text: str
    competency: Optional[str] = None
    rationale: Optional[str] = None
    source_reference: Optional[str] = None


@dataclass
class STARCompliance:
    """Compliance ai componenti STAR"""
    situation_present: bool
    situation_quality: int  # 1-5
    situation_rationale: str

    task_present: bool
    task_quality: int  # 1-5
    task_rationale: str

    action_present: bool
    action_quality: int  # 1-5
    action_rationale: str

    result_present: bool
    result_quality: int  # 1-5
    result_rationale: str

    star_score: float  # Media quality dei componenti presenti
    components_present_count: int  # Quanti componenti sono presenti (0-4)

    def to_dict(self):
        return asdict(self)


@dataclass
class BEICompliance:
    """Compliance al framework Behavioral Event Interview"""
    past_behavior_focus: int  # 1-5: Focus su comportamento passato vs ipotetico
    past_behavior_rationale: str

    specificity: int  # 1-5: Specificità vs genericità
    specificity_rationale: str

    probing_depth: int  # 1-5: Profondità dell'indagine
    probing_depth_rationale: str

    job_relevance: int  # 1-5: Rilevanza per la posizione
    job_relevance_rationale: str

    bei_score: float  # Media delle 4 dimensioni

    def to_dict(self):
        return asdict(self)


@dataclass
class PersonalizationMetrics:
    """Metriche di personalizzazione sul CV"""
    integration_score: int  # 1-5: Quanto è personalizzata
    integration_rationale: str

    entities_mentioned: List[str]  # Entità specifiche dal CV
    entities_count: int

    biographical_references: int  # Numero riferimenti biografici

    has_specific_references: bool  # True se menziona dettagli specifici

    def to_dict(self):
        return asdict(self)


@dataclass
class RelevanceVerification:
    """Verifica presenza effettiva di riferimenti a CV e JD"""

    # Riferimenti CV
    cv_references_found: bool
    cv_specific_mentions: List[str]  # Cosa è menzionato dal CV
    cv_reference_quality: str  # "none", "generic", "specific"

    # Riferimenti JD
    jd_references_found: bool
    jd_competencies_mentioned: List[str]  # Competenze JD nella domanda
    jd_reference_quality: str  # "none", "generic", "specific"

    # Assessment complessivo
    is_well_grounded: bool  # True se ben ancorata a CV+JD
    grounding_rationale: str

    def to_dict(self):
        return asdict(self)


@dataclass
class OverallAssessment:
    """Valutazione complessiva della domanda"""
    star_score: float  # 0-5
    bei_score: float  # 0-5
    personalization_score: int  # 1-5

    final_score: float  # Media pesata dei 3 score
    quality_category: str  # "excellent", "good", "acceptable", "poor"

    meets_star_standard: bool  # True se star_score >= 3.5
    meets_bei_standard: bool  # True se bei_score >= 3.5
    meets_both_standards: bool  # True se entrambi >= 3.5

    strengths: List[str]
    weaknesses: List[str]
    improvement_suggestions: str

    def to_dict(self):
        return asdict(self)


@dataclass
class EvaluationResult:
    """Risultato completo della valutazione"""
    question: Question

    star_compliance: STARCompliance
    bei_compliance: BEICompliance
    personalization: PersonalizationMetrics
    relevance_verification: RelevanceVerification
    overall_assessment: OverallAssessment

    def to_dict(self):
        return {
            'question_text': self.question.text,
            'star_compliance': self.star_compliance.to_dict(),
            'bei_compliance': self.bei_compliance.to_dict(),
            'personalization': self.personalization.to_dict(),
            'relevance_verification': self.relevance_verification.to_dict(),
            'overall_assessment': self.overall_assessment.to_dict()
        }


# =============================================================================
# LLM CLIENT
# =============================================================================

class LLMClient:
    """Client generico per LLM su OpenRouter"""

    def __init__(self,
                 api_key: str,
                 model: str = "qwen/qwen3-vl-8b-instruct",
                 temperature: float = 0.2,
                 max_tokens: int = 8000):
        """
        Inizializza il client OpenRouter

        Args:
            api_key: Chiave API di OpenRouter
            model: Modello da utilizzare
            temperature: Temperatura per generazione (più bassa = più deterministica)
            max_tokens: Limite di token per risposta
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, prompt: str) -> str:
        """
        Invia prompt all'LLM e ritorna la risposta
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=90
            )
            response.raise_for_status()

            result = response.json()
            content = result['choices'][0]['message']['content'].strip()

            return content

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] API call failed: {e}")
            raise
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            raise


# =============================================================================
# STAR/BEI EVALUATOR
# =============================================================================

class STARBEIEvaluator:
    """
    Valutatore principale basato su standard STAR/BEI
    Usa LLM-as-a-Judge per compliance checking
    """

    def __init__(self, api_key: str, model: str = "qwen/qwen3-vl-8b-instruct"):
        """
        Inizializza l'evaluator

        Args:
            api_key: Chiave API OpenRouter
            model: Modello LLM da utilizzare
        """
        self.llm = LLMClient(api_key=api_key, model=model)
        print(f"[INFO] STARBEIEvaluator initialized with model: {model}")

    def evaluate(
            self,
            question: Question,
            cv_content: str,
            job_description: str,
            jd_competencies: Optional[List[str]] = None
    ) -> EvaluationResult:
        """
        Valuta una domanda secondo standard STAR/BEI

        Args:
            question: Domanda da valutare
            cv_content: Contenuto completo del CV
            job_description: Job description completa
            jd_competencies: Lista opzionale di competenze dalla JD

        Returns:
            EvaluationResult con valutazione completa
        """


        max_iter = 3
        i = 0
        while i < max_iter:
            print(f"\n[EVALUATING] Question: '{question.text[:80]}...'")

            # Crea il prompt completo per valutazione
            prompt = self._build_evaluation_prompt(
                question.text,
                cv_content,
                job_description,
                jd_competencies
            )

            # Chiamata all'LLM
            print("   [PROCESSING] LLM call in progress...")
            response = self.llm.chat(prompt)

            # Parse della risposta
            print("   [PARSING] Processing results...")
            try:
                evaluation_data = self._parse_response(response)

                # Costruisci risultato strutturato
                result = self._build_result(question, evaluation_data)

                print(f"   [COMPLETE] Evaluation completed - Score: {result.overall_assessment.final_score:.2f}/5")

                return result
            except Exception as e:
                print("    [ERROR] Evaluation failed, retrying... ")
                print(f"    [INFO] Iteration {i}")
                i += 1



    def _build_evaluation_prompt(
            self,
            question_text: str,
            cv: str,
            jd: str,
            jd_competencies: Optional[List[str]]
    ) -> str:
        """
        Costruisce il prompt per la valutazione LLM
        """

        # Limita lunghezza per evitare token eccessivi
        #cv_excerpt = cv[:3000] if len(cv) > 3000 else cv
        #jd_excerpt = jd[:2000] if len(jd) > 2000 else jd

        competencies_text = ""
        if jd_competencies:
            competencies_text = f"\n\nCOMPETENZE CHIAVE JD:\n" + "\n".join(f"- {comp}" for comp in jd_competencies)

        prompt = f"""Sei un esperto di colloqui strutturati e assessment HR. Devi valutare una domanda di colloquio secondo standard professionali consolidati: STAR e BEI (Behavioral Event Interview).

DOMANDA DA VALUTARE:
"{question_text}"

JOB DESCRIPTION (estratto):
{jd}{competencies_text}

CV CANDIDATO (estratto):
{cv}

---

COMPITO: Valuta la domanda secondo i seguenti criteri. Sii RIGOROSO e OGGETTIVO.

## 1. CONFORMITÀ STAR (Situation, Task, Action, Result)

Per ogni componente, valuta:
- **present**: true/false - è richiesto/menzionato nella domanda?
- **quality**: 1-5 - quanto è ben formulato se presente?
  - 1: Appena accennato, poco chiaro
  - 3: Presente in modo adeguato
  - 5: Formulato in modo eccellente, molto esplicito
- **rationale**: spiegazione breve (1 frase)

Componenti:
- **Situation**: Richiede descrizione di un contesto/scenario specifico?
- **Task**: Chiede quale fosse l'obiettivo/sfida/problema?
- **Action**: Richiede descrizione delle azioni intraprese?
- **Result**: Chiede risultati/esiti/impatto?

## 2. CONFORMITÀ BEI (Behavioral Event Interview)

Valuta su scala 1-5:

- **past_behavior_focus**: La domanda richiede esempi di comportamento PASSATO REALE (non scenari ipotetici)?
  - 1: Completamente ipotetica ("Cosa faresti se...")
  - 3: Mix di passato e ipotetico
  - 5: Chiaramente focalizzata su esperienze reali ("Raccontami di quando...")

- **specificity**: Quanto è specifica la domanda? Chiede dettagli concreti o è generica?
  - 1: Molto generica ("Parlami delle tue competenze")
  - 3: Moderatamente specifica
  - 5: Molto specifica con riferimenti precisi a esperienze/progetti

- **probing_depth**: La domanda incoraggia risposte dettagliate e verificabili?
  - 1: Risposta sì/no sufficiente
  - 3: Richiede qualche elaborazione
  - 5: Richiede risposta articolata con dettagli verificabili

- **job_relevance**: Quanto è rilevante per la posizione (basato su JD)?
  - 1: Irrilevante per la posizione
  - 3: Moderatamente rilevante
  - 5: Altamente rilevante per competenze chiave

## 3. PERSONALIZZAZIONE CV

- **integration_score** (1-5): Quanto è personalizzata sul background specifico del candidato?
  - 1: Domanda completamente generica, applicabile a chiunque
  - 3: Fa riferimento generico al settore/ruolo
  - 5: Menziona progetti/esperienze/competenze specifiche dal CV

- **entities_mentioned**: Lista le entità specifiche menzionate dal CV (nomi propri, progetti, tecnologie, luoghi, aziende). Se nessuna → lista vuota []

- **biographical_references**: Conta quanti riferimenti biografici espliciti ci sono (es: "nella tua tesi", "durante il tuo lavoro presso X", "nel progetto Y")

- **has_specific_references**: true se menziona almeno un elemento specifico dal CV, false altrimenti

## 4. VERIFICA PRESENZA RIFERIMENTI (MOLTO IMPORTANTE)

Analizza se la domanda effettivamente fa riferimento a CV e JD:

**CV References:**
- **cv_references_found**: true/false - ci sono riferimenti al CV?
- **cv_specific_mentions**: Lista cosa viene menzionato dal CV (se niente → [])
- **cv_reference_quality**: "none" / "generic" / "specific"
  - "none": nessun riferimento al CV
  - "generic": riferimento generico (es: "la tua esperienza")
  - "specific": riferimento specifico (es: "nella tua tesi su fitodepurazione")

**JD References:**
- **jd_references_found**: true/false - ci sono riferimenti alla JD?
- **jd_competencies_mentioned**: Lista competenze JD presenti nella domanda (se niente → [])
- **jd_reference_quality**: "none" / "generic" / "specific"
  - "none": non pertinente alla posizione
  - "generic": pertinente al settore generale
  - "specific": menziona competenze/responsabilità specifiche dalla JD

**Grounding Overall:**
- **is_well_grounded**: true se la domanda è ben ancorata sia a CV che a JD
- **grounding_rationale**: 1-2 frasi che spiegano la valutazione

## 5. ASSESSMENT COMPLESSIVO

- **quality_category**: "excellent" / "good" / "acceptable" / "poor"
  - excellent: star_score >= 4.0 AND bei_score >= 4.0
  - good: star_score >= 3.5 AND bei_score >= 3.5
  - acceptable: star_score >= 2.5 OR bei_score >= 2.5
  - poor: entrambi < 2.5

- **strengths**: Lista 2-3 punti di forza principali
- **weaknesses**: Lista 1-2 punti deboli principali (se ci sono)
- **improvement_suggestions**: 1-2 frasi su come migliorare la domanda

---

FORMATO RISPOSTA: Rispondi SOLO con un oggetto JSON valido, nient'altro. Usa questo formato esatto:

```json
{{
  "star_compliance": {{
    "situation": {{
      "present": true/false,
      "quality": 1-5,
      "rationale": "..."
    }},
    "task": {{
      "present": true/false,
      "quality": 1-5,
      "rationale": "..."
    }},
    "action": {{
      "present": true/false,
      "quality": 1-5,
      "rationale": "..."
    }},
    "result": {{
      "present": true/false,
      "quality": 1-5,
      "rationale": "..."
    }}
  }},
  "bei_compliance": {{
    "past_behavior_focus": {{
      "score": 1-5,
      "rationale": "..."
    }},
    "specificity": {{
      "score": 1-5,
      "rationale": "..."
    }},
    "probing_depth": {{
      "score": 1-5,
      "rationale": "..."
    }},
    "job_relevance": {{
      "score": 1-5,
      "rationale": "..."
    }}
  }},
  "personalization": {{
    "integration_score": 1-5,
    "integration_rationale": "...",
    "entities_mentioned": ["entità1", "entità2"],
    "biographical_references": 0-N,
    "has_specific_references": true/false
  }},
  "relevance_verification": {{
    "cv_references_found": true/false,
    "cv_specific_mentions": ["cosa1", "cosa2"],
    "cv_reference_quality": "none/generic/specific",
    "jd_references_found": true/false,
    "jd_competencies_mentioned": ["competenza1", "competenza2"],
    "jd_reference_quality": "none/generic/specific",
    "is_well_grounded": true/false,
    "grounding_rationale": "..."
  }},
  "overall": {{
    "quality_category": "excellent/good/acceptable/poor",
    "strengths": ["punto1", "punto2"],
    "weaknesses": ["punto1", "punto2"],
    "improvement_suggestions": "..."
  }}
}}
```

IMPORTANTE: 
- Sii RIGOROSO nella valutazione. Score alti vanno meritati.
- STAR/BEI completi e ben formulati sono rari - punteggi bassi sono accettabili.
- Verifica REALMENTE la presenza di riferimenti specifici - non assumere.
"""

        return prompt

    def _parse_response(self, response: str) -> Dict:
        """
        Parse della risposta JSON dall'LLM
        """
        # Pulisci response da markdown
        content = response.strip()

        # Rimuovi blocchi di codice markdown
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        try:
            data = json.loads(content)
            return data
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parsing failed: {e}")
            print(f"Content received: {content[:500]}")
            #raise

    def _build_result(self, question: Question, data: Dict) -> EvaluationResult:
        """
        Costruisce EvaluationResult strutturato dai dati parsed
        """
        try:
            # STAR Compliance
            star_data = data['star_compliance']
            components_present = sum([
                star_data['situation']['present'],
                star_data['task']['present'],
                star_data['action']['present'],
                star_data['result']['present']
            ])

            # Calcola media quality solo per componenti presenti
            star_qualities = []
            if star_data['situation']['present']:
                star_qualities.append(star_data['situation']['quality'])
            if star_data['task']['present']:
                star_qualities.append(star_data['task']['quality'])
            if star_data['action']['present']:
                star_qualities.append(star_data['action']['quality'])
            if star_data['result']['present']:
                star_qualities.append(star_data['result']['quality'])

            star_score = np.mean(star_qualities) if star_qualities else 0.0

            star_compliance = STARCompliance(
                situation_present=star_data['situation']['present'],
                situation_quality=star_data['situation']['quality'],
                situation_rationale=star_data['situation']['rationale'],
                task_present=star_data['task']['present'],
                task_quality=star_data['task']['quality'],
                task_rationale=star_data['task']['rationale'],
                action_present=star_data['action']['present'],
                action_quality=star_data['action']['quality'],
                action_rationale=star_data['action']['rationale'],
                result_present=star_data['result']['present'],
                result_quality=star_data['result']['quality'],
                result_rationale=star_data['result']['rationale'],
                star_score=float(star_score),
                components_present_count=components_present
            )

            # BEI Compliance
            bei_data = data['bei_compliance']
            bei_score = np.mean([
                bei_data['past_behavior_focus']['score'],
                bei_data['specificity']['score'],
                bei_data['probing_depth']['score'],
                bei_data['job_relevance']['score']
            ])

            bei_compliance = BEICompliance(
                past_behavior_focus=bei_data['past_behavior_focus']['score'],
                past_behavior_rationale=bei_data['past_behavior_focus']['rationale'],
                specificity=bei_data['specificity']['score'],
                specificity_rationale=bei_data['specificity']['rationale'],
                probing_depth=bei_data['probing_depth']['score'],
                probing_depth_rationale=bei_data['probing_depth']['rationale'],
                job_relevance=bei_data['job_relevance']['score'],
                job_relevance_rationale=bei_data['job_relevance']['rationale'],
                bei_score=float(bei_score)
            )

            # Personalization
            pers_data = data['personalization']
            personalization = PersonalizationMetrics(
                integration_score=pers_data['integration_score'],
                integration_rationale=pers_data['integration_rationale'],
                entities_mentioned=pers_data['entities_mentioned'],
                entities_count=len(pers_data['entities_mentioned']),
                biographical_references=pers_data['biographical_references'],
                has_specific_references=pers_data['has_specific_references']
            )

            # Relevance Verification
            rel_data = data['relevance_verification']
            relevance_verification = RelevanceVerification(
                cv_references_found=rel_data['cv_references_found'],
                cv_specific_mentions=rel_data['cv_specific_mentions'],
                cv_reference_quality=rel_data['cv_reference_quality'],
                jd_references_found=rel_data['jd_references_found'],
                jd_competencies_mentioned=rel_data['jd_competencies_mentioned'],
                jd_reference_quality=rel_data['jd_reference_quality'],
                is_well_grounded=rel_data['is_well_grounded'],
                grounding_rationale=rel_data['grounding_rationale']
            )

            # Overall Assessment
            overall_data = data['overall']

            # Calcola final score (media pesata)
            # Peso maggiore a BEI e STAR
            final_score = (
                    star_score * 0.35 +
                    bei_score * 0.35 +
                    pers_data['integration_score'] * 0.30
            )

            overall_assessment = OverallAssessment(
                star_score=float(star_score),
                bei_score=float(bei_score),
                personalization_score=pers_data['integration_score'],
                final_score=float(final_score),
                quality_category=overall_data['quality_category'],
                meets_star_standard=star_score >= 3.5,
                meets_bei_standard=bei_score >= 3.5,
                meets_both_standards=(star_score >= 3.5 and bei_score >= 3.5),
                strengths=overall_data['strengths'],
                weaknesses=overall_data['weaknesses'],
                improvement_suggestions=overall_data['improvement_suggestions']
            )

            return EvaluationResult(
                question=question,
                star_compliance=star_compliance,
                bei_compliance=bei_compliance,
                personalization=personalization,
                relevance_verification=relevance_verification,
                overall_assessment=overall_assessment
            )
        except Exception as e:
            print("[ERROR] Building EvaluationResult failed: {e}")
            print("skipping result construction...")
            return EvaluationResult(
                question=question,
                star_compliance=STARCompliance(
                    situation_present=False,
                    situation_quality=0,
                    situation_rationale="N/A",
                    task_present=False,
                    task_quality=0,
                    task_rationale="N/A",
                    action_present=False,
                    action_quality=0,
                    action_rationale="N/A",
                    result_present=False,
                    result_quality=0,
                    result_rationale="N/A",
                    star_score=0.0,
                    components_present_count=0
                ),
                bei_compliance=BEICompliance(
                    past_behavior_focus=0,
                    past_behavior_rationale="N/A",
                    specificity=0,
                    specificity_rationale="N/A",
                    probing_depth=0,
                    probing_depth_rationale="N/A",
                    job_relevance=0,
                    job_relevance_rationale="N/A",
                    bei_score=0.0
                ),
                personalization=PersonalizationMetrics(
                    integration_score=0,
                    integration_rationale="N/A",
                    entities_mentioned=[],
                    entities_count=0,
                    biographical_references=0,
                    has_specific_references=False
                ),
                relevance_verification=RelevanceVerification(
                    cv_references_found=False,
                    cv_specific_mentions=[],
                    cv_reference_quality="N/A",
                    jd_references_found=False,
                    jd_competencies_mentioned=[],
                    jd_reference_quality="N/A",
                    is_well_grounded=False,
                    grounding_rationale="N/A"
                ),
                overall_assessment=OverallAssessment(
                    star_score=0.0,
                    bei_score=0.0,
                    personalization_score=0,
                    final_score=0.0,
                    quality_category="fallback",
                    meets_star_standard=False,
                    meets_bei_standard=False,
                    meets_both_standards=False,
                    strengths=[],
                    weaknesses=[],
                    improvement_suggestions=""
                )
            )



# =============================================================================
# REPORT GENERATOR
# =============================================================================

def print_evaluation_report(result: EvaluationResult, detailed: bool = True):
    """
    Print evaluation report in formal tabular format (English)
    """
    oa = result.overall_assessment
    star = result.star_compliance
    bei = result.bei_compliance
    pers = result.personalization
    rel = result.relevance_verification

    print("\n" + "=" * 80)
    print("QUESTION EVALUATION REPORT")
    print("=" * 80)

    # Question Text
    print(f"\nQUESTION TEXT:")
    print(f"{result.question.text}")

    # Overall Summary Table
    print(f"\n{'=' * 80}")
    print("OVERALL ASSESSMENT")
    print("=" * 80)
    print(f"{'Metric':<30} {'Score':<15} {'Status':<15}")
    print("-" * 80)
    print(f"{'Final Score':<30} {oa.final_score:.2f}/5.00")
    print(f"{'Quality Category':<30} {oa.quality_category.upper()}")
    print(f"{'STAR Score':<30} {oa.star_score:.2f}/5.00     {'Yes' if oa.meets_star_standard else 'No':<15}")
    print(f"{'BEI Score':<30} {oa.bei_score:.2f}/5.00     {'Yes' if oa.meets_bei_standard else 'No':<15}")
    print(f"{'Personalization Score':<30} {oa.personalization_score}/5")
    print(f"{'Meets Both Standards':<30} {'Yes' if oa.meets_both_standards else 'No'}")

    if detailed:
        # STAR Compliance Table
        print(f"\n{'=' * 80}")
        print(f"STAR COMPLIANCE (Score: {star.star_score:.2f}/5.00)")
        print("=" * 80)
        print(f"Components Present: {star.components_present_count}/4")
        print()
        print(f"{'Component':<15} {'Present':<10} {'Quality':<10} {'Rationale'}")
        print("-" * 80)
        print(
            f"{'Situation':<15} {'Yes' if star.situation_present else 'No':<10} {star.situation_quality}/5      {star.situation_rationale}")
        print(
            f"{'Task':<15} {'Yes' if star.task_present else 'No':<10} {star.task_quality}/5      {star.task_rationale}")
        print(
            f"{'Action':<15} {'Yes' if star.action_present else 'No':<10} {star.action_quality}/5      {star.action_rationale}")
        print(
            f"{'Result':<15} {'Yes' if star.result_present else 'No':<10} {star.result_quality}/5      {star.result_rationale}")

        # BEI Compliance Table
        print(f"\n{'=' * 80}")
        print(f"BEI COMPLIANCE (Score: {bei.bei_score:.2f}/5.00)")
        print("=" * 80)
        print(f"{'Dimension':<25} {'Score':<10} {'Rationale'}")
        print("-" * 80)
        print(f"{'Past Behavior Focus':<25} {bei.past_behavior_focus}/5      {bei.past_behavior_rationale}")
        print(f"{'Specificity':<25} {bei.specificity}/5      {bei.specificity_rationale}")
        print(f"{'Probing Depth':<25} {bei.probing_depth}/5      {bei.probing_depth_rationale}")
        print(f"{'Job Relevance':<25} {bei.job_relevance}/5      {bei.job_relevance_rationale}")

        # Personalization Table
        print(f"\n{'=' * 80}")
        print(f"PERSONALIZATION (Score: {pers.integration_score}/5)")
        print("=" * 80)
        print(f"Rationale: {pers.integration_rationale}")
        print(f"\n{'Metric':<30} {'Value'}")
        print("-" * 80)
        print(f"{'Entities Mentioned Count':<30} {pers.entities_count}")
        if pers.entities_mentioned:
            print(f"{'Entities List':<30} {', '.join(pers.entities_mentioned)}")
        else:
            print(f"{'Entities List':<30} None")
        print(f"{'Biographical References':<30} {pers.biographical_references}")
        print(f"{'Has Specific References':<30} {'Yes' if pers.has_specific_references else 'No'}")

        # Relevance Verification Table
        print(f"\n{'=' * 80}")
        print("RELEVANCE VERIFICATION")
        print("=" * 80)
        print(f"Well-Grounded (CV+JD): {'Yes' if rel.is_well_grounded else 'No'}")
        print(f"Rationale: {rel.grounding_rationale}")
        print()
        print(f"{'Aspect':<25} {'Found':<10} {'Quality':<15} {'Details'}")
        print("-" * 80)
        cv_mentions = ', '.join(rel.cv_specific_mentions) if rel.cv_specific_mentions else 'None'
        print(
            f"{'CV References':<25} {'Yes' if rel.cv_references_found else 'No':<10} {rel.cv_reference_quality:<15} {cv_mentions}")
        jd_mentions = ', '.join(rel.jd_competencies_mentioned) if rel.jd_competencies_mentioned else 'None'
        print(
            f"{'JD References':<25} {'Yes' if rel.jd_references_found else 'No':<10} {rel.jd_reference_quality:<15} {jd_mentions}")

    # Strengths and Weaknesses
    print(f"\n{'=' * 80}")
    print("STRENGTHS")
    print("=" * 80)
    for i, strength in enumerate(oa.strengths, 1):
        print(f"{i}. {strength}")

    if oa.weaknesses:
        print(f"\n{'=' * 80}")
        print("WEAKNESSES")
        print("=" * 80)
        for i, weakness in enumerate(oa.weaknesses, 1):
            print(f"{i}. {weakness}")

    print(f"\n{'=' * 80}")
    print("IMPROVEMENT SUGGESTIONS")
    print("=" * 80)
    print(f"{oa.improvement_suggestions}")

    print("\n" + "=" * 80 + "\n")


def generate_aggregate_report(results: List[EvaluationResult]) -> Dict:
    """
    Genera report aggregato su più domande
    """
    if not results:
        return {}

    n = len(results)

    report = {
        'total_questions': n,

        # STAR metrics
        'star': {
            'avg_score': np.mean([r.overall_assessment.star_score for r in results]),
            'std_dev': np.std([r.overall_assessment.star_score for r in results]),
            'meets_standard_rate': sum(1 for r in results if r.overall_assessment.meets_star_standard) / n * 100,
            'situation_present_rate': sum(1 for r in results if r.star_compliance.situation_present) / n * 100,
            'task_present_rate': sum(1 for r in results if r.star_compliance.task_present) / n * 100,
            'action_present_rate': sum(1 for r in results if r.star_compliance.action_present) / n * 100,
            'result_present_rate': sum(1 for r in results if r.star_compliance.result_present) / n * 100,
            'avg_components_count': np.mean([r.star_compliance.components_present_count for r in results])
        },

        # BEI metrics
        'bei': {
            'avg_score': np.mean([r.overall_assessment.bei_score for r in results]),
            'std_dev': np.std([r.overall_assessment.bei_score for r in results]),
            'meets_standard_rate': sum(1 for r in results if r.overall_assessment.meets_bei_standard) / n * 100,
            'avg_past_behavior': np.mean([r.bei_compliance.past_behavior_focus for r in results]),
            'avg_specificity': np.mean([r.bei_compliance.specificity for r in results]),
            'avg_probing_depth': np.mean([r.bei_compliance.probing_depth for r in results]),
            'avg_job_relevance': np.mean([r.bei_compliance.job_relevance for r in results])
        },

        # Personalization metrics
        'personalization': {
            'avg_score': np.mean([r.personalization.integration_score for r in results]),
            'avg_entities_count': np.mean([r.personalization.entities_count for r in results]),
            'has_specific_refs_rate': sum(1 for r in results if r.personalization.has_specific_references) / n * 100
        },

        # Relevance verification
        'relevance': {
            'well_grounded_rate': sum(1 for r in results if r.relevance_verification.is_well_grounded) / n * 100,
            'cv_refs_found_rate': sum(1 for r in results if r.relevance_verification.cv_references_found) / n * 100,
            'jd_refs_found_rate': sum(1 for r in results if r.relevance_verification.jd_references_found) / n * 100,
            'specific_cv_quality_rate': sum(
                1 for r in results if r.relevance_verification.cv_reference_quality == 'specific') / n * 100,
            'specific_jd_quality_rate': sum(
                1 for r in results if r.relevance_verification.jd_reference_quality == 'specific') / n * 100
        },

        # Overall quality
        'overall': {
            'avg_final_score': np.mean([r.overall_assessment.final_score for r in results]),
            'std_dev': np.std([r.overall_assessment.final_score for r in results]),
            'meets_both_standards_rate': sum(1 for r in results if r.overall_assessment.meets_both_standards) / n * 100,
            'excellent_rate': sum(1 for r in results if r.overall_assessment.quality_category == 'excellent') / n * 100,
            'good_rate': sum(1 for r in results if r.overall_assessment.quality_category == 'good') / n * 100,
            'acceptable_rate': sum(
                1 for r in results if r.overall_assessment.quality_category == 'acceptable') / n * 100,
            'poor_rate': sum(1 for r in results if r.overall_assessment.quality_category == 'poor') / n * 100
        }
    }

    return report


def print_aggregate_report(report: Dict):
    """
    Print aggregate report in formal tabular format (English)
    """
    print("\n" + "=" * 80)
    print("AGGREGATE EVALUATION REPORT")
    print("=" * 80)
    print(f"\nTotal Questions Evaluated: {report['total_questions']}")

    # STAR Compliance Table
    print(f"\n{'=' * 80}")
    print("STAR COMPLIANCE SUMMARY")
    print("=" * 80)
    star = report['star']
    print(f"{'Metric':<40} {'Value'}")
    print("-" * 80)
    print(f"{'Average Score':<40} {star['avg_score']:.2f} +/- {star['std_dev']:.2f}")
    print(f"{'Meets Standard (>=3.5)':<40} {star['meets_standard_rate']:.1f}%")
    print(f"{'Average Components Present':<40} {star['avg_components_count']:.1f}/4")
    print()
    print(f"{'Component Presence Rates':>40}")
    print(f"{'  Situation':<40} {star['situation_present_rate']:.1f}%")
    print(f"{'  Task':<40} {star['task_present_rate']:.1f}%")
    print(f"{'  Action':<40} {star['action_present_rate']:.1f}%")
    print(f"{'  Result':<40} {star['result_present_rate']:.1f}%")

    # BEI Compliance Table
    print(f"\n{'=' * 80}")
    print("BEI COMPLIANCE SUMMARY")
    print("=" * 80)
    bei = report['bei']
    print(f"{'Metric':<40} {'Value'}")
    print("-" * 80)
    print(f"{'Average Score':<40} {bei['avg_score']:.2f} +/- {bei['std_dev']:.2f}")
    print(f"{'Meets Standard (>=3.5)':<40} {bei['meets_standard_rate']:.1f}%")
    print()
    print(f"{'Dimension Average Scores':>40}")
    print(f"{'  Past Behavior Focus':<40} {bei['avg_past_behavior']:.2f}/5")
    print(f"{'  Specificity':<40} {bei['avg_specificity']:.2f}/5")
    print(f"{'  Probing Depth':<40} {bei['avg_probing_depth']:.2f}/5")
    print(f"{'  Job Relevance':<40} {bei['avg_job_relevance']:.2f}/5")

    # Personalization Table
    print(f"\n{'=' * 80}")
    print("PERSONALIZATION SUMMARY")
    print("=" * 80)
    pers = report['personalization']
    print(f"{'Metric':<40} {'Value'}")
    print("-" * 80)
    print(f"{'Average Score':<40} {pers['avg_score']:.2f}/5")
    print(f"{'Average Entities Mentioned':<40} {pers['avg_entities_count']:.1f}")
    print(f"{'Questions with Specific References':<40} {pers['has_specific_refs_rate']:.1f}%")

    # Relevance Verification Table
    print(f"\n{'=' * 80}")
    print("RELEVANCE VERIFICATION SUMMARY")
    print("=" * 80)
    rel = report['relevance']
    print(f"{'Metric':<40} {'Value'}")
    print("-" * 80)
    print(f"{'Well-Grounded (CV+JD)':<40} {rel['well_grounded_rate']:.1f}%")
    print(f"{'Questions with CV References':<40} {rel['cv_refs_found_rate']:.1f}%")
    print(f"{'Questions with JD References':<40} {rel['jd_refs_found_rate']:.1f}%")
    print(f"{'CV References - Specific Quality':<40} {rel['specific_cv_quality_rate']:.1f}%")
    print(f"{'JD References - Specific Quality':<40} {rel['specific_jd_quality_rate']:.1f}%")

    # Overall Quality Table
    print(f"\n{'=' * 80}")
    print("OVERALL QUALITY SUMMARY")
    print("=" * 80)
    overall = report['overall']
    print(f"{'Metric':<40} {'Value'}")
    print("-" * 80)
    print(f"{'Average Final Score':<40} {overall['avg_final_score']:.2f} +/- {overall['std_dev']:.2f}")
    print(f"{'Meets Both Standards (STAR+BEI)':<40} {overall['meets_both_standards_rate']:.1f}%")
    print()
    print(f"{'Quality Distribution':>40}")
    print(f"{'  Excellent (>=4.0)':<40} {overall['excellent_rate']:.1f}%")
    print(f"{'  Good (3.5-3.99)':<40} {overall['good_rate']:.1f}%")
    print(f"{'  Acceptable (2.5-3.49)':<40} {overall['acceptable_rate']:.1f}%")
    print(f"{'  Poor (<2.5)':<40} {overall['poor_rate']:.1f}%")

    print("\n" + "=" * 80 + "\n")


def initialize_database() -> DatabaseRepository:
    """Initialize database connection and repository."""

    try:
        db_manager = get_db_manager()
        db_repo = DatabaseRepository(db_manager)

        # Test connection
        if db_repo.health_check():
            print("✓ Database connected successfully")
        else:
            print("✗ Database health check failed")

    except Exception as e:
        print(f"Failed to initialize database: {e}")
        raise

    return db_repo

def extract_question_groups(text: str):
    """
    Estrae le domande dal testo e le raggruppa in liste separate
    ogni volta che la numerazione riparte da 1.

    Ritorna: lista di liste
    """
    lines = text.splitlines()
    groups = []
    current_group = []

    # Pattern: **1.** oppure **2.** ecc.
    index_pattern = re.compile(r'^\s*\*\*([0-9]+)\.\*\*')

    # Pattern: *“ domanda ”*
    question_pattern = re.compile(r'\*\s*“(.*?)”\s*\*', flags=re.DOTALL)

    current_index = None

    for line in lines:
        # rileva inizio nuova domanda
        index_match = index_pattern.match(line)
        if index_match:
            idx = int(index_match.group(1))

            # Se ritorna a 1, inizia un nuovo gruppo
            if idx == 1 and current_group:
                groups.append(current_group)
                current_group = []

            current_index = idx

        # rileva il testo della domanda
        q_match = question_pattern.search(line)
        if q_match:
            question = q_match.group(1).strip()
            current_group.append(question)

    # Aggiunge l'ultimo gruppo
    if current_group:
        groups.append(current_group)

    return groups


def get_context_data_for_question_group(question_group) -> List[str]:
    db_repo: DatabaseRepository = initialize_database()
    cv_cont = []
    job_descript = []
    emails = ["mario.rossi@example.com", "sofia.verdi@example.com",
              "federica.lombardi@example.com", "simone.rizzo@example.com",
              "francesca.ricci@example.com", "giorgia.romano@example.com"]
    try:
        email = emails[question_group - 1]
    except Exception:
        raise
    if db_repo:
        try:
            user_data = db_repo.get_user_data_by_email(email)
            cv_cont = user_data.get('cv_content')
            job_descript = user_data.get('jobdescription')
            # semantic_profile = user_data.get('semantic_profile')
        except Exception as e:
            print(f"[ERROR] Failed to retrieve user data: {e}")
            cv_cont = "Default CV content for testing purposes."
            job_descript = "Default Job Description content for testing purposes."
            # semantic_profile = {}
    else:
        raise Exception("Database repository is not initialized.")
    print(f"[INFO] Retrieved context data for email: {email}")
    print(f"       CV length: {len(cv_cont)} characters")
    print(f"       Job Description length: {len(job_descript)} characters")
    print("\n")
    return [cv_cont, job_descript]


if __name__ == "__main__":
    print("""
================================================================================
            QUESTION EVALUATOR - STAR/BEI Compliance Version
================================================================================
  
  Evaluation of interview questions based on professional standards:
  - STAR Compliance (Situation, Task, Action, Result)
  - BEI Compliance (Behavioral Event Interview)
  - CV Personalization
  - Reference Verification
  
================================================================================
    """)

    # read questions from file

    with open("questions_to_eval.txt", "r", encoding="utf-8") as f:
        text = f.read()

    question_groups = extract_question_groups(text)
    # API KEY (sostituisci con la tua)
    api_key = "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"

    # Inizializza evaluator
    print("\n[INIT] Initializing evaluator...")
    evaluator = STARBEIEvaluator(api_key=api_key)
    final_report = []
    print("\n" + "=" * 30)
    print("TESTING GENERATED QUESTIONS")
    print("=" * 30)
    for group_index, group in enumerate(question_groups, start=1):
        # print(f"\n=== TESTING GROUP {group_index} ===")
        try:
            cv_content, job_description = get_context_data_for_question_group(
                group_index,
            )
        except Exception as e:
            # print(f"[ERROR] Could not get context data for group {group_index}: {e}")
            continue

        for q in group:
            eval_result = evaluator.evaluate(
                question=Question(text=q),
                cv_content=cv_content,
                job_description=job_description
            )

            #print_evaluation_report(eval_result, detailed=True)
            final_report.append(eval_result)

    # Report aggregato
    print("\n" + "=" * 80)
    print("AGGREGATE REPORT")
    print("=" * 80)
    aggregate_report = generate_aggregate_report(final_report)
    print_aggregate_report(aggregate_report)

    print("\nEvaluation completed.")
