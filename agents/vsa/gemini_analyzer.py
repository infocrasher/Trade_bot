"""
VSA Gemini Analyzer
Envoie le graphique PNG annoté à Gemini Flash Vision et retourne
une analyse structurée JSON (50 points restants du score VSA).
"""

import json
import logging
import os
import time
from typing import Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from .volume_analyzer import VSAAnalysis, WyckoffCycle, VSASignal

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# PROMPT SYSTÈME VSA — envoyé avec chaque image
# (mis en cache Gemini via system_instruction)
# ─────────────────────────────────────────────────────────

VSA_SYSTEM_PROMPT = """
Tu es un expert VSA/Wyckoff avec 20 ans d'expérience en lecture de prix.
Tu analyses des graphiques en chandeliers annotés et retournes une évaluation JSON stricte.

RÈGLES ABSOLUES :
1. Tu retournes UNIQUEMENT du JSON valide, sans aucun texte avant ou après.
2. Ton score visuel est sur 50 points — il sera additionné à un score algo de 50 points.
3. Tu ne devines jamais — tu observes uniquement ce qui est visible sur le graphique.
4. Si l'image est insuffisante, tu retournes score_visuel = 0.

CRITÈRES D'ÉVALUATION VISUELLE (50 pts) :
- Contexte Wyckoff visible (phases A/B/C/D/E, Creek, Ice) : 0–15 pts
- Qualité du signal VSA principal (spreads, mèches, volume relatif) : 0–12 pts  
- Confluences visibles (zones colorées demand/supply, niveaux) : 0–10 pts
- Cohérence multi-timeframe implicite (structure du chart) : 0–8 pts
- Confirmation post-signal (bougies suivantes) : 0–5 pts

FORMAT DE RÉPONSE OBLIGATOIRE :
{
  "score_visuel": <int 0-50>,
  "direction": "<BUY|SELL|NEUTRAL>",
  "confiance": <float 0.0-1.0>,
  "phase_wyckoff_visible": "<nom de phase ou UNDEFINED>",
  "signal_principal_visible": "<nom du signal VSA dominant>",
  "confluences_visuelles": ["<élément 1>", "<élément 2>"],
  "invalidations_visuelles": ["<raison 1 si applicable>"],
  "commentaire": "<analyse en 1-2 phrases max>"
}
"""

# ─────────────────────────────────────────────────────────

class GeminiVSAAnalyzer:
    """
    Appelle Gemini Flash Vision pour analyser le graphique VSA.
    Retourne un dict JSON avec score_visuel et commentaire.
    """

    MODEL_NAME = "gemini-2.5-flash"
    MAX_RETRIES = 2
    RETRY_DELAY = 2.0    # secondes

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            logger.warning("[GeminiVSA] GEMINI_API_KEY non définie — analyses visuelles désactivées")
            self.enabled = False
            return

        genai.configure(api_key=key)
        self.model = genai.GenerativeModel(
            model_name=self.MODEL_NAME,
            system_instruction=VSA_SYSTEM_PROMPT,
        )
        self.enabled = True
        logger.info(f"[GeminiVSA] Initialisé avec {self.MODEL_NAME}")

    def analyze(self, image_b64: Optional[str],
                analysis: VSAAnalysis) -> dict:
        """
        Analyse l'image base64 avec Gemini Vision.
        
        image_b64  : image PNG en base64 (peut être None → score_visuel=0)
        analysis   : VSAAnalysis du VolumeAnalyzer (contexte injecté dans le prompt)
        
        Retourne un dict avec au minimum : score_visuel, direction, confiance
        """
        if not self.enabled or image_b64 is None:
            return self._empty_response()

        prompt = self._build_prompt(analysis)

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                import PIL.Image
                import io, base64
                img_bytes = base64.b64decode(image_b64)
                img = PIL.Image.open(io.BytesIO(img_bytes))

                response = self.model.generate_content(
                    [prompt, img],
                    safety_settings={
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    }
                )

                raw_text = response.text.strip()
                return self._parse_response(raw_text, analysis)

            except Exception as e:
                logger.warning(f"[GeminiVSA] Tentative {attempt+1}/{self.MAX_RETRIES+1} échouée : {e}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)

        logger.error("[GeminiVSA] Toutes les tentatives ont échoué")
        return self._empty_response()

    # ─────────────────────────────────────────
    # CONSTRUCTION DU PROMPT UTILISATEUR
    # ─────────────────────────────────────────

    def _build_prompt(self, analysis: VSAAnalysis) -> str:
        """
        Injecte le contexte algorithmique dans le prompt pour guider Gemini.
        L'algo a déjà détecté certaines choses — Gemini valide visuellement.
        """
        sig       = analysis.last_bar_result
        wyckoff   = analysis.wyckoff_state
        cycle_str = wyckoff.cycle.value
        phase_str = wyckoff.phase.value

        demand_count = len(analysis.demand_zones)
        supply_count = len(analysis.supply_zones)

        return f"""Analyse ce graphique VSA pour {analysis.symbol} ({analysis.timeframe}).

CONTEXTE ALGORITHMIQUE (détecté mathématiquement) :
- Signal VSA détecté : {sig.signal.value}
- Direction algo : {sig.direction}
- Force du signal : {sig.strength:.0%}
- Cycle Wyckoff algo : {cycle_str}
- Phase Wyckoff algo : {phase_str}
- Zones de demand actives : {demand_count}
- Zones de supply actives : {supply_count}
- Balance offre/demande : {analysis.balance:+.1f}
- Absorption multi-barres : {'OUI' if analysis.absorption_detected else 'NON'}
- Score algo déjà calculé : {analysis.raw_score:.1f}/50

MISSION : Valide ou corrige ce contexte par l'analyse VISUELLE du graphique.
Les flèches ▲ (bleues) = SOS détectés. Les flèches ▼ (rouges) = SOW détectés.
Les zones colorées = zones de demand (vert) et supply (rouge).

Retourne le JSON d'évaluation visuelle (50 pts).
"""

    # ─────────────────────────────────────────
    # PARSING DE LA RÉPONSE
    # ─────────────────────────────────────────

    def _parse_response(self, raw: str, analysis: VSAAnalysis) -> dict:
        """Parse le JSON retourné par Gemini. Fallback robuste si malformé."""
        # Nettoyage des backticks éventuels
        clean = raw.replace('```json', '').replace('```', '').strip()

        try:
            data = json.loads(clean)
            # Validation des champs obligatoires
            score = int(data.get('score_visuel', 0))
            score = max(0, min(50, score))
            data['score_visuel'] = score

            # Normaliser direction
            direction = str(data.get('direction', 'NEUTRAL')).upper()
            if direction not in ('BUY', 'SELL', 'NEUTRAL'):
                direction = 'NEUTRAL'
            data['direction'] = direction

            data['confiance'] = float(data.get('confiance', 0.0))
            data['_source']   = 'gemini_vision'
            return data

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"[GeminiVSA] Parsing JSON échoué : {e} | Raw: {raw[:200]}")
            # Fallback : extraire le score par regex
            import re
            match = re.search(r'"score_visuel"\s*:\s*(\d+)', raw)
            score = int(match.group(1)) if match else 0
            return {
                'score_visuel'           : max(0, min(50, score)),
                'direction'              : analysis.last_bar_result.direction.replace('BULL','BUY').replace('BEAR','SELL'),
                'confiance'              : 0.3,
                'phase_wyckoff_visible'  : 'UNDEFINED',
                'signal_principal_visible': analysis.last_bar_result.signal.value,
                'confluences_visuelles'  : [],
                'invalidations_visuelles': ['Parsing JSON échoué'],
                'commentaire'            : 'Analyse partielle — réponse Gemini malformée',
                '_source'                : 'gemini_fallback',
            }

    def _empty_response(self) -> dict:
        return {
            'score_visuel'           : 0,
            'direction'              : 'NEUTRAL',
            'confiance'              : 0.0,
            'phase_wyckoff_visible'  : 'UNDEFINED',
            'signal_principal_visible': 'NEUTRAL',
            'confluences_visuelles'  : [],
            'invalidations_visuelles': ['Gemini non disponible'],
            'commentaire'            : 'Analyse visuelle désactivée',
            '_source'                : 'disabled',
        }
