"""
TakeOption Offline Backtester
=============================
Rejoue des données historiques OHLCV à travers le pipeline ICT existant
(A1 Structure → A2 Time → A3 Entry → A4 Macro → A5 Orchestrator)
pour mesurer l'edge algorithmique sans risquer de capital.

Modules :
    download_history : Télécharge M5/H1/H4/D1 via TwelveData → Parquet
    engine           : Moteur de replay bar-by-bar avec anti-lookahead
    report           : Rapport HTML standalone (WR, PF, SQN, Max DD, equity curve)

Usage :
    python -m backtest.download_history --all --months 6
    python -m backtest.engine --pairs EURUSD GBPUSD --horizon scalp --months 6
"""

__version__ = "0.1.0"
