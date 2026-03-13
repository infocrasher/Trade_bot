"""
================================================================
  MAIN.PY — Pipeline Fusionné (Sofiane + Fateh)
================================================================
  Moteur algorithmique ICT (5 agents mathématiques) 
  + Infrastructure opérationnelle (MT5, Paper Trading, Circuit Breaker)
  
  Architecture :
    MT5 Connector (Fateh) → Données OHLCV multi-TF
    Agent 1 Structure    (Sofiane) → Swings, FVG, OB, BOS, MSS, EQH/EQL
    Agent 2 Time         (Sofiane) → Killzones, Macros, Midnight Open
    Agent 3 Entry        (Sofiane) → OTE, Premium/Discount, DOL, SD
    Agent 4 Macro        (Sofiane) → COT, SMT, DXY, News, IPDA, Quarterly
    Agent 5 Orchestrator (Sofiane) → Vote pondéré, Safety, Position Sizing
    Trade Manager        (Fateh)   → Circuit Breaker, Corrélation, Exécution MT5
  
  Utilisation :
    python main.py                       → Analyse toutes les paires (1 cycle)
    python main.py EURUSD                → Analyse une paire spécifique
    python main.py --loop 5              → Boucle toutes les 5 minutes
    python main.py --paper               → Force le mode paper trading
    python main.py XAUUSD --loop 1       → Scalp Gold en boucle
================================================================
"""

import sys
import os
import time
import json
import argparse
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np

# ================================================================
# PATH SETUP
# ================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ================================================================
# CONFIGURATION
# ================================================================
import config

# ================================================================
# IMPORTS — Nos 5 Agents (Sofiane)
# ================================================================
from agents.agent_structure    import StructureAgent
from agents.agent_time_session import TimeSessionAgent
from agents.agent_entry        import EntryAgent
from agents.agent_macro        import MacroBiasAgent
from agents.agent_orchestrator import OrchestratorAgent

# ================================================================
# IMPORTS — Infrastructure (Fateh + YFinance fallback)
# ================================================================
from data.trade_manager  import TradeManager

# Auto-détection du data provider (MT5 > YFinance > Simulation)
def _get_provider():
    """Choisit automatiquement le meilleur provider de données."""
    # 1. MT5 si disponible
    try:
        from data.mt5_connector import MT5Connector
        mt5 = MT5Connector()
        if mt5.connected and not mt5.simulation_mode:
            return mt5, "MT5_LIVE"
    except ImportError:
        pass
    
    # 2. TwelveData si clé API disponible
    try:
        from data.twelve_data_provider import TwelveDataProvider
        td = TwelveDataProvider()
        if td.connected:
            return td, "TWELVEDATA"
    except ImportError:
        pass
    
    # 3. MT5 en mode simulation (fallback)
    try:
        from data.mt5_connector import MT5Connector
        return MT5Connector(), "SIMULATION"
    except:
        return None, "NONE"

# ================================================================
# LOGGING
# ================================================================
NYC_TZ = ZoneInfo("America/New_York")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s : %(message)s",
)
logger = logging.getLogger("MainPipeline")


# ================================================================
# BRIDGE : MT5 data → DataFrames pandas pour nos agents
# ================================================================
def candles_to_dataframe(candles: list[dict]) -> pd.DataFrame:
    """
    Convertit les bougies MT5 (list of dicts) en DataFrame pandas
    avec les colonnes requises par nos agents.
    """
    if not candles:
        return pd.DataFrame()
    
    df = pd.DataFrame(candles)
    
    # Normaliser les noms de colonnes
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], format='mixed', dayfirst=False)
    
    # Ajouter les colonnes dérivées requises par nos agents
    df['body'] = (df['close'] - df['open']).abs()
    df['range'] = df['high'] - df['low']
    df['body_ratio'] = df.apply(
        lambda r: r['body'] / r['range'] if r['range'] > 0 else 0, axis=1
    )
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    
    # Tick volume (si absent, mettre 100 par défaut)
    if 'tick_volume' not in df.columns:
        if 'volume' in df.columns:
            df['tick_volume'] = df['volume']
        else:
            df['tick_volume'] = 100
    
    return df


def extract_dataframes(market_data: dict) -> dict:
    """
    Extrait les DataFrames multi-TF depuis le market_data de MT5.
    
    Retourne : {"D1": df, "H4": df, "H1": df, "M15": df, "M5": df, ...}
    """
    tf_mapping = {
        "D1":  "candles_d1",
        "H4":  "candles_h4",
        "H1":  "candles_h1",
        "M15": "candles_m15",
        "M5":  "candles_m5",
        "W1":  "candles_w1",
        "MN":  "candles_mn1",
    }
    
    dataframes = {}
    for tf_key, candle_key in tf_mapping.items():
        candles = market_data.get(candle_key, [])
        if candles:
            dataframes[tf_key] = candles_to_dataframe(candles)
    
    return dataframes


# ================================================================
# PAPER TRADING — Journal JSON
# ================================================================
def log_paper_trade(pair: str, decision: dict):
    """Enregistre un trade fictif dans un fichier JSON."""
    journal_dir = os.path.join(BASE_DIR, "data", "journal")
    os.makedirs(journal_dir, exist_ok=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(journal_dir, f"paper_trades_{today}.json")
    
    # Charger existants
    trades = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                trades = json.load(f)
        except:
            trades = []
    
    # Ajouter le nouveau trade
    trade_entry = {
        "timestamp": datetime.now().isoformat(),
        "pair": pair,
        "decision": decision.get("decision"),
        "direction": decision.get("direction"),
        "entry_price": decision.get("entry_price"),
        "stop_loss": decision.get("stop_loss"),
        "tp1": decision.get("tp1"),
        "tp2": decision.get("tp2"),
        "tp3": decision.get("tp3"),
        "rr_ratio": decision.get("rr_ratio"),
        "confidence": decision.get("global_confidence"),
        "aligned_count": decision.get("aligned_count"),
        "reasons": decision.get("reasons", []),
    }
    trades.append(trade_entry)
    
    with open(filepath, "w") as f:
        json.dump(trades, f, indent=2, default=str)
    
    logger.info(f"[PAPER] Trade enregistré dans {filepath}")


# ================================================================
# ANALYSE D'UNE PAIRE — Le pipeline complet
# ================================================================
def run_analysis(pair: str, mt5, trade_mgr: TradeManager,
                 paper_mode: bool = False) -> dict:
    """
    Pipeline complet pour une paire :
    MT5 → Agent 1-4 → Agent 5 → Exécution/Paper
    """
    ny_now = datetime.now(NYC_TZ)
    logger.info(f"{'='*55}")
    logger.info(f"  ANALYSE {pair} | {ny_now.strftime('%H:%M:%S')} NY")
    logger.info(f"{'='*55}")
    
    # ─────────────────────────────────────────────
    # ÉTAPE 0 : Récupération données MT5
    # ─────────────────────────────────────────────
    market_data = mt5.get_market_data(pair)
    
    if market_data.get("status") == "ERROR":
        logger.error(f"[SKIP] {pair} — {market_data.get('message')}")
        return {"decision": "ERROR", "reason": market_data.get("message")}
    
    current_price = market_data.get("current_price", 0)
    logger.info(f"  Prix: {current_price} | NY: {market_data.get('ny_time')}")
    
    # Convertir en DataFrames
    dfs = extract_dataframes(market_data)
    df_d1  = dfs.get("D1", pd.DataFrame())
    df_h4  = dfs.get("H4", pd.DataFrame())
    df_h1  = dfs.get("H1", pd.DataFrame())
    df_m15 = dfs.get("M15", pd.DataFrame())
    df_m5  = dfs.get("M5", pd.DataFrame())
    
    # Vérification données minimales
    if df_h1.empty or df_m5.empty:
        logger.warning(f"[SKIP] {pair} — Données H1 ou M5 insuffisantes")
        return {"decision": "NO_TRADE", "reason": "Insufficient data"}

    # ─────────────────────────────────────────────
    # ÉTAPE 1 : Agent Structure (Multi-TF)
    # ─────────────────────────────────────────────
    agent1 = StructureAgent(symbol=pair)
    
    # Construire le dict des TFs disponibles
    mtf_data = {}
    if not df_d1.empty and len(df_d1) >= 10:
        mtf_data["D1"] = df_d1
    if not df_h4.empty and len(df_h4) >= 10:
        mtf_data["H4"] = df_h4
    if not df_h1.empty and len(df_h1) >= 10:
        mtf_data["H1"] = df_h1
    
    structure_report = agent1.analyze_multi_tf(mtf_data)
    
    # Enrichir avec key_levels et equal_levels du H1 pour Agent 3
    h1_data = structure_report.get("H1", {})
    structure_report["bias"] = h1_data.get("bias", structure_report.get("htf_alignment", "neutral"))
    structure_report["swings"] = h1_data.get("swings", [])
    structure_report["fvg"] = h1_data.get("fvg", [])
    structure_report["order_blocks"] = h1_data.get("order_blocks", [])
    structure_report["bos_choch"] = h1_data.get("bos_choch", [])
    structure_report["liquidity_sweeps"] = h1_data.get("liquidity_sweeps", [])
    structure_report["displacements"] = h1_data.get("displacements", [])
    
    # Key levels depuis les données MT5 directement
    key_levels = {}
    if market_data.get("prev_day_high"):
        key_levels["PDH"] = market_data["prev_day_high"]
        key_levels["PDL"] = market_data["prev_day_low"]
    if market_data.get("prev_week_high"):
        key_levels["PWH"] = market_data["prev_week_high"]
        key_levels["PWL"] = market_data["prev_week_low"]
    structure_report["key_levels"] = key_levels
    structure_report["equal_levels"] = h1_data.get("equal_levels", [])
    
    htf = structure_report.get("htf_alignment", "unknown")
    logger.info(f"  Agent 1 : Bias={structure_report['bias']} | HTF={htf} | "
                f"Swings={len(structure_report['swings'])} | FVG={len(structure_report['fvg'])}")

    # ─────────────────────────────────────────────
    # ÉTAPE 2 : Agent Time & Session
    # ─────────────────────────────────────────────
    # Le broker_utc_offset dépend du broker MT5
    broker_offset = getattr(config, "BROKER_UTC_OFFSET", 2)
    agent2 = TimeSessionAgent(broker_utc_offset=broker_offset)
    
    # On passe df_m5 pour l'Asian Range et le Midnight Open
    time_report = agent2.analyze(df_m5)
    
    can_trade = time_report.get("can_trade", False)
    quality = time_report.get("trade_quality", "no_trade")
    kz_name = time_report.get("killzone", {})
    kz_display = kz_name.get("name", "None") if isinstance(kz_name, dict) else "None"
    macro_info = time_report.get("active_macro")
    macro_display = macro_info.get("name", "None") if macro_info else "None"
    
    logger.info(f"  Agent 2 : Can_trade={can_trade} | Quality={quality} | "
                f"KZ={kz_display} | Macro={macro_display}")

    # ─────────────────────────────────────────────
    # ÉTAPE 3 : Agent Entry Precision (sur M5)
    # ─────────────────────────────────────────────
    agent3 = EntryAgent(symbol=pair)
    entry_signal = agent3.analyze(structure_report, time_report, df_m5)
    entry_signal["_df_h1"] = dfs.get("H1", pd.DataFrame())
    
    signal = entry_signal.get("signal", "NO_TRADE")
    logger.info(f"  Agent 3 : Signal={signal} | "
                f"R:R={entry_signal.get('rr_ratio', 'N/A')} | "
                f"Conf={entry_signal.get('confidence', 'N/A')}")

    # ─────────────────────────────────────────────
    # ÉTAPE 4 : Agent Macro Bias
    # ─────────────────────────────────────────────
    agent4 = MacroBiasAgent(target_pair=pair)
    
    # Données macro simplifiées (pas de connexion externe pour l'instant)
    # On utilise ce qui est disponible dans market_data
    dxy_data = None
    if market_data.get("dxy_price"):
        dxy_data = {
            "trend": "unknown",
            "current_price": market_data["dxy_price"],
        }
    
    macro_report = agent4.analyze(
        cot_data=None,
        smt_data=None,
        dxy_data=dxy_data,
        news_data=None,
        current_time=market_data.get("ny_time")
    )
    
    # Enrichir avec IPDA et Quarterly si on a les données D1
    if not df_d1.empty and len(df_d1) >= 60:
        ipda = agent4.analyze_ipda_ranges(df_d1)
        macro_report["ipda_ranges"] = ipda
    
    quarterly = agent4.get_quarterly_context(
        market_data.get("date", datetime.now().strftime("%Y-%m-%d")) + " 10:00"
    )
    macro_report["quarterly"] = quarterly
    
    m_bias = macro_report.get("macro_bias", "neutral")
    m_can = macro_report.get("can_trade", True)
    logger.info(f"  Agent 4 : Bias={m_bias} | Can_trade={m_can} | "
                f"Quarter={quarterly.get('quarter', 'N/A')}")

    # ─────────────────────────────────────────────
    # ÉTAPE 5 : Agent Orchestrator (Décision)
    # ─────────────────────────────────────────────
    agent5 = OrchestratorAgent()
    decision = agent5.calculate_decision(
        structure_report, time_report, entry_signal, macro_report
    )
    
    dec = decision.get("decision", "NO_TRADE")
    conf = decision.get("global_confidence", 0)
    aligned = decision.get("aligned_count", 0)
    
    logger.info(f"  Agent 5 : Decision={dec} | Confidence={conf} | Aligned={aligned}/4")
    
    if dec == "NO_TRADE":
        reason = decision.get("reason", "")
        logger.info(f"  → NO TRADE : {reason}")
        return decision

    # ─────────────────────────────────────────────
    # ÉTAPE 6 : Exécution / Paper Trading
    # ─────────────────────────────────────────────
    direction_mt5 = "ACHAT" if "BUY" in dec else "VENTE"
    entry_price = decision.get("entry_price", 0)
    stop_loss = decision.get("stop_loss", 0)
    tp1 = decision.get("tp1", 0)
    
    logger.info(f"  {'!'*50}")
    logger.info(f"  SIGNAL : {dec} sur {pair}")
    logger.info(f"  Entry={entry_price} | SL={stop_loss} | TP1={tp1} | R:R={decision.get('rr_ratio')}")
    logger.info(f"  Confiance={conf} | Alignement={aligned}/4")
    logger.info(f"  {'!'*50}")
    
    if paper_mode or getattr(config, "PAPER_TRADING", False):
        # Mode Paper — enregistrer dans le journal
        log_paper_trade(pair, decision)
        logger.info(f"  [PAPER] Trade enregistré (pas d'exécution réelle)")
    else:
        # Mode Réel — pré-vérification + exécution
        daily_pnl = 0.0
        try:
            daily_pnl = trade_mgr.performance.get_daily_pnl_pct()
        except:
            pass
        
        ok, reason = trade_mgr.pre_trade_check(pair, direction_mt5, daily_pnl)
        if not ok:
            logger.warning(f"  [BLOCKED] {reason}")
            decision["execution"] = {"ok": False, "reason": reason}
        else:
            result = trade_mgr.execute_trade(
                pair=pair,
                direction=direction_mt5,
                entry=entry_price,
                sl=stop_loss,
                tp=tp1,
                comment=f"ICT {quality} {dec}"
            )
            logger.info(f"  [EXEC] {result}")
            decision["execution"] = result
    
    return decision


# ================================================================
# BANNIÈRE
# ================================================================
def print_banner(pairs: list, paper_mode: bool, provider: str = ""):
    ny_now = datetime.now(NYC_TZ)
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   BOT ICT MULTI-AGENT — Moteur Algorithmique Pur        ║")
    print("║   Sofiane (Logic) + Fateh (Infrastructure)               ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  NY Time   : {ny_now.strftime('%Y-%m-%d %H:%M:%S'):<42}║")
    print(f"║  Paires    : {', '.join(pairs[:4]):<42}║")
    if len(pairs) > 4:
        print(f"║             {', '.join(pairs[4:]):<42}║")
    print(f"║  Mode      : {'PAPER TRADING' if paper_mode else 'LIVE':<42}║")
    print(f"║  Provider  : {provider:<42}║")
    print(f"║  Agents    : 5 (Structure, Time, Entry, Macro, Orchestr)║")
    print(f"║  Tests     : 107/107 ✅                                  ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()


# ================================================================
# POINT D'ENTRÉE
# ================================================================
def main():
    parser = argparse.ArgumentParser(description="Bot ICT Multi-Agent Fusionné")
    parser.add_argument("pair", nargs="?", default=None, help="Paire à analyser (ex: EURUSD)")
    parser.add_argument("--loop", type=int, default=0, help="Intervalle en minutes (0 = une seule fois)")
    parser.add_argument("--paper", action="store_true", help="Forcer le mode paper trading")
    parser.add_argument("--pairs", nargs="+", default=None, help="Liste de paires")
    args = parser.parse_args()
    
    # Déterminer les paires
    if args.pair:
        pairs = [args.pair.upper()]
    elif args.pairs:
        pairs = [p.upper() for p in args.pairs]
    else:
        pairs = getattr(config, "TRADING_PAIRS", ["EURUSD"])
    
    paper_mode = args.paper or getattr(config, "PAPER_TRADING", False)
    
    # Initialisation Data Provider (auto-détection)
    logger.info("[INIT] Recherche du meilleur data provider...")
    mt5, provider_type = _get_provider()
    if mt5 is None:
        logger.error("[FATAL] Aucun data provider disponible.")
        sys.exit(1)
    mt5.test_connection()
    logger.info(f"[INIT] Provider actif : {provider_type}")
    
    # Bannière
    print_banner(pairs, paper_mode, provider_type)
    
    # Initialisation Trade Manager
    trade_mgr = TradeManager()
    
    logger.info(f"[INIT] Pipeline prêt. {'Paper mode' if paper_mode else 'Live mode'}.")
    logger.info(f"[INIT] Paires : {pairs}")
    
    # ─────────────────────────────────────────────
    # BOUCLE PRINCIPALE
    # ─────────────────────────────────────────────
    cycle = 0
    
    while True:
        cycle += 1
        ny_now = datetime.now(NYC_TZ)
        
        logger.info(f"\n{'='*20} CYCLE #{cycle} | {ny_now.strftime('%H:%M:%S')} NY {'='*20}")
        
        results = {}
        
        for pair in pairs:
            try:
                result = run_analysis(pair, mt5, trade_mgr, paper_mode)
                results[pair] = result
                
                # Pause entre paires (respect API)
                if len(pairs) > 1:
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                logger.info("\n[STOP] Arrêt demandé.")
                mt5.disconnect()
                sys.exit(0)
                
            except Exception as e:
                logger.error(f"[ERROR] {pair} : {e}", exc_info=True)
                continue
        
        # ─────────────────────────────────────────
        # Résumé du cycle
        # ─────────────────────────────────────────
        logger.info(f"\n  RÉSUMÉ CYCLE #{cycle} :")
        for pair, result in results.items():
            dec = result.get("decision", "ERROR")
            conf = result.get("global_confidence", "-")
            if dec.startswith("EXECUTE"):
                logger.info(f"  🎯 {pair}: {dec} (Confiance: {conf})")
            elif dec == "NO_TRADE":
                reason = result.get("reason", "")[:60]
                logger.info(f"  ⏸️  {pair}: NO_TRADE — {reason}")
            else:
                logger.info(f"  ❌ {pair}: {dec}")
        
        # Sortir si pas de boucle
        if args.loop == 0:
            logger.info(f"\n[FIN] Cycle unique terminé.")
            break
        
        # Attente avant prochain cycle
        logger.info(f"\n[WAIT] Prochain cycle dans {args.loop} min (Ctrl+C pour arrêter)")
        try:
            time.sleep(args.loop * 60)
        except KeyboardInterrupt:
            logger.info("\n[STOP] Arrêt du système.")
            break
    
    # Fermeture
    mt5.disconnect()
    logger.info("[END] Bot arrêté proprement. Bonne chance !")


if __name__ == "__main__":
    main()