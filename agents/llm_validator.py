"""
Agent 6 — LLM Validateur ICT (Claude Sonnet)
Valide ou rejette les signaux des 5 agents algorithmiques.
Ne peut jamais inventer un signal — seulement confirmer ou bloquer.
"""

import os
import json
import time
from datetime import datetime

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# ── Prompt système ICT compressé (~2000 tokens) ────────────────
ICT_SYSTEM_PROMPT = """Tu es un auditeur ICT (Inner Circle Trader) strict et méthodique.
Tu reçois un signal de trading généré par un algorithme. Tu dois VALIDER ou REJETER ce signal
en vérifiant la checklist ICT ci-dessous.

═══ RÈGLES ICT À VÉRIFIER ═══

1. STRUCTURE DE MARCHÉ
   - Un BOS (Break of Structure) doit avoir une CLÔTURE de corps au-delà du swing, pas juste une mèche
   - Un MSS (Market Structure Shift) nécessite: BOS + Displacement (bougies larges) + FVG créé
   - CHoCH = premier signal de retournement seulement, PAS une confirmation
   - Le biais HTF (D1/W1) doit être aligné avec le trade. Si D1 bearish → JAMAIS acheter sur M5

2. TIMING
   - Le trade DOIT être dans une Killzone valide:
     * Asia KZ: 20h-22h NYC | London KZ: 02h-05h NYC | NY AM KZ: 07h-10h NYC | NY PM: 10h-12h NYC
   - Bonus si dans une des 12 Macros algorithmiques (fenêtres de 20 min)
   - INTERDIT: Lundi avant 10h NYC (Seek & Destroy), Vendredi après 14h NYC, 30min avant FOMC/NFP
   - Pour du Swing/Position (H4/D1), le timing Killzone est moins critique

3. ZONE D'ENTRÉE
   - L'entrée doit être dans la zone OTE (62%-79% Fibonacci du dernier swing)
   - Le 70.5% est le point d'entrée idéal
   - ACHAT = zone Discount (sous 50% du swing) | VENTE = zone Premium (au-dessus de 50%)
   - Il faut une confluence: FVG + OB dans la même zone, ou FVG dans l'OTE
   - L'OB doit être "frais" (non revisité)

4. CIBLE ET R:R
   - Le Draw on Liquidity (DOL) doit être nommé précisément (ex: "PWH à 1.0950")
   - R:R minimum 1.5 pour scalp, 2.0 pour swing
   - Les cibles prioritaires: EQH/EQL > PDH/PDL > PWH/PWL > FVG HTF non comblé

5. STOP LOSS
   - SL doit être placé sous/sur l'OB ou FVG d'entrée (pas au milieu)
   - SL outside le dernier swing créé par le MSS
   - Max 20-30 pips pour scalp, 50-100 pips pour swing

6. CONFIRMATIONS
   - HTF et LTF doivent être alignés sur la même direction
   - SMT Divergence ne doit PAS contredire le signal
   - S'il y a un Displacement visible avec FVG créé = forte confirmation

7. RED FLAGS (rejet automatique)
   - Trade contre le biais D1/W1 sans raison valable
   - Pas de Displacement dans le mouvement de structure
   - Entrée hors de la zone OTE (ni Discount pour buy, ni Premium pour sell)
   - R:R < 1.5
   - HTF totalement conflicting sans explication
   - Aucun FVG ni OB dans la zone d'entrée

═══ FORMAT DE RÉPONSE (JSON strict) ═══

Réponds UNIQUEMENT avec ce JSON, rien d'autre:
{
  "verdict": "VALIDÉ" ou "REJETÉ",
  "confiance_llm": 0.0 à 1.0,
  "score_timing": 0 à 20,
  "score_structure": 0 à 20,
  "score_entree": 0 à 20,
  "score_cible": 0 à 20,
  "score_smt": 0 à 20,
  "total": 0 à 100,
  "raisons": ["raison 1", "raison 2"],
  "red_flags": ["flag 1"] ou [],
  "narrative_ict": "En 2-3 phrases: l'histoire du marché qui justifie ou invalide ce trade."
}
"""


class LLMValidatorAgent:
    """Agent 6 — Valide les signaux ICT via Claude Sonnet."""

    def __init__(self, api_key=None, model="claude-haiku-4-5-20251001"):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = None
        self.enabled = False
        self.last_call_time = 0
        self.min_interval = 10  # Minimum 10 secondes entre les appels

        if HAS_ANTHROPIC and self.api_key:
            try:
                self.client = anthropic.Anthropic(api_key=self.api_key)
                self.enabled = True
            except Exception as e:
                print(f"[LLM Validator] Erreur init Anthropic: {e}")

    def validate(self, structure_report, time_report, entry_signal,
                 macro_report, decision_obj, pair, horizon="scalp", force_analyze=False):
        """
        Valide un signal EXECUTE via Claude.
        Retourne un dict avec verdict, score, raisons.
        """
        if not self.enabled:
            return self._skip_result("LLM Validateur désactivé (pas de clé API)")

        # Rate limiting
        now = time.time()
        if now - self.last_call_time < self.min_interval:
            return self._skip_result("Rate limit — trop d'appels rapprochés")

        # Construire le message utilisateur avec les données des 5 agents
        user_message = self._build_user_message(
            structure_report, time_report, entry_signal,
            macro_report, decision_obj, pair, horizon,
            force_analyze=force_analyze
        )

        try:
            self.last_call_time = time.time()
            response = self.client.messages.create(
                model=self.model,
                max_tokens=800,
                system=[
                    {
                        "type": "text",
                        "text": ICT_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                messages=[{"role": "user", "content": user_message}]
            )

            raw_text = response.content[0].text.strip()

            # Parser le JSON
            # Nettoyer si le LLM ajoute des backticks
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            result = json.loads(raw_text)

            # Valider les champs attendus
            result.setdefault("verdict", "REJETÉ")
            result.setdefault("confiance_llm", 0.5)
            result.setdefault("total", 50)
            result.setdefault("raisons", [])
            result.setdefault("red_flags", [])
            result.setdefault("narrative_ict", "")
            result["source"] = "claude_sonnet"
            result["skipped"] = False

            # Coût estimé (Haiku pricing: $0.25/1M input, $1.25/1M output)
            # Prompt caching: $0.03/1M cache hit (90% reduction vs regular input)
            input_tokens = response.usage.input_tokens
            cache_read = getattr(response.usage, "cache_read_input_tokens", 0)
            cache_creation = getattr(response.usage, "cache_creation_input_tokens", 0)
            output_tokens = response.usage.output_tokens
            
            # Calcul précis avec cache — prix selon le modèle
            regular_input = input_tokens - cache_read - cache_creation
            if "haiku" in self.model:
                # Haiku: $0.80/M input, $4/M output, cache read $0.08/M
                cost = (regular_input * 0.80 / 1_000_000) + \
                       (cache_read * 0.08 / 1_000_000) + \
                       (cache_creation * 1.0 / 1_000_000) + \
                       (output_tokens * 4.0 / 1_000_000)
            else:
                # Sonnet: $3/M input, $15/M output, cache read $0.30/M
                cost = (regular_input * 3.0 / 1_000_000) + \
                       (cache_read * 0.30 / 1_000_000) + \
                       (cache_creation * 3.75 / 1_000_000) + \
                       (output_tokens * 15.0 / 1_000_000)
            
            result["tokens"] = {
                "input": input_tokens, 
                "cache_hit": cache_read,
                "output": output_tokens
            }
            result["cost_usd"] = round(cost, 5)

            return result

        except json.JSONDecodeError:
            return self._skip_result(f"Réponse LLM non-JSON: {raw_text[:200]}")
        except Exception as e:
            return self._skip_result(f"Erreur LLM: {str(e)}")

    def _build_user_message(self, structure_report, time_report,
                            entry_signal, macro_report, decision_obj,
                            pair, horizon, force_analyze=False):
        """Construit le message avec toutes les données des 5 agents."""

        bias = structure_report.get("bias", "neutral")
        htf = structure_report.get("htf_alignment", "unknown")
        n_swings = len(structure_report.get("swings", []))
        n_fvg = len(structure_report.get("fvg", []))
        n_ob = len(structure_report.get("order_blocks", []))
        n_bos = len(structure_report.get("bos_choch", []))
        n_sweeps = len(structure_report.get("liquidity_sweeps", []))
        key_levels = structure_report.get("key_levels", {})

        kz = time_report.get("killzone", {})
        kz_name = kz.get("name", "Hors KZ") if isinstance(kz, dict) else "Hors KZ"
        quality = time_report.get("trade_quality", "no_trade")
        can_trade = time_report.get("can_trade", False)
        macro_active = time_report.get("active_macro")
        po3_phase = time_report.get("po3_phase", {}).get("phase", "unknown")

        signal = entry_signal.get("signal", "NO_TRADE")
        entry_price = entry_signal.get("entry_price", 0)
        sl = entry_signal.get("stop_loss", 0)
        rr = entry_signal.get("rr_ratio", 0)
        confidence_entry = entry_signal.get("confidence", 0)
        pd_check = entry_signal.get("premium_discount", {})

        macro_bias = macro_report.get("macro_bias", "neutral")
        quarterly = macro_report.get("quarterly", {})

        dec = decision_obj.get("decision", "NO_TRADE")
        conf = decision_obj.get("global_confidence", 0)
        reasons = decision_obj.get("reasons", [])
        warnings = decision_obj.get("warnings", [])

        # Bandeau mode test : le LLM ne doit pas pénaliser le timing
        test_banner = ""
        if force_analyze:
            test_banner = """⚠️ MODE TEST ACTIVÉ — FORCE ANALYZE ON
Les Killzones et le timing sont IGNORÉS volontairement pour ce cycle.
Tu dois évaluer UNIQUEMENT la structure, l'entrée, le R:R et la cohérence du setup.
Ne rejette PAS ce signal à cause du timing ou des Killzones.
Score timing = 20/20 automatiquement.

"""

        msg = f"""{test_banner}═══ SIGNAL À VALIDER ═══

PAIRE: {pair} | HORIZON: {horizon} | DIRECTION: {signal}
DÉCISION ALGO: {dec} | CONFIANCE ALGO: {conf:.0%}

── Agent 1 (Structure) ──
Biais: {bias} | HTF Alignment: {htf}
Swings: {n_swings} | FVG: {n_fvg} | OB: {n_ob} | BOS/CHoCH: {n_bos} | Sweeps: {n_sweeps}
Niveaux clés: {json.dumps(key_levels)}

── Agent 2 (Timing) ──
Killzone: {kz_name} | Qualité: {quality} | Can Trade: {can_trade}
Macro active: {macro_active} | Phase PO3: {po3_phase}

── Agent 3 (Entrée) ──
Signal: {signal} | Entry: {entry_price} | SL: {sl} | R:R: {rr}
Confiance entrée: {confidence_entry} | Premium/Discount: {json.dumps(pd_check)}

── Agent 4 (Macro) ──
Biais macro: {macro_bias} | Quarterly: {json.dumps(quarterly)}

── Agent 5 (Orchestrateur) ──
Décision: {dec} | Confiance: {conf:.0%}
Raisons: {', '.join(reasons)}
Warnings: {', '.join(warnings) if warnings else 'Aucun'}

═══ VÉRIFIE CE SIGNAL SELON LA CHECKLIST ICT ET RÉPONDS EN JSON ═══"""

        return msg

    def _skip_result(self, reason):
        """Retourne un résultat neutre quand le LLM est indisponible."""
        return {
            "verdict": "SKIP",
            "confiance_llm": 0.5,
            "total": 0,
            "raisons": [reason],
            "red_flags": [],
            "narrative_ict": "",
            "source": "skip",
            "skipped": True,
            "tokens": {"input": 0, "output": 0},
            "cost_usd": 0,
        }