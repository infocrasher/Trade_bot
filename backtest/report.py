"""
report.py — Génère un rapport HTML standalone pour les résultats de backtest.

Sections :
    1. Résumé (WR, PF, SQN, Max DD, Sharpe, total PnL)
    2. Courbe d'equity (SVG inline)
    3. Performance par paire
    4. Performance par session (killzone)
    5. Performance par jour de la semaine
    6. Distribution des R-multiples
    7. Trades individuels (tableau)
    8. Gate analysis (setups bloqués)
    9. Critère d'arrêt (comparaison vs seuils)
"""

import os
import io
import base64
from datetime import datetime
from collections import defaultdict

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _MPL_AVAILABLE = True
except ImportError:
    _MPL_AVAILABLE = False


def _fig_to_base64(fig) -> str:
    """Convertit une figure matplotlib en base64 PNG."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                facecolor="#1a1a2e", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _make_equity_chart(equity_curve: list) -> str:
    """Génère le graphique de la courbe d'equity."""
    if not _MPL_AVAILABLE or len(equity_curve) < 2:
        return ""

    fig, ax = plt.subplots(figsize=(12, 4))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    x = range(len(equity_curve))
    ax.plot(x, equity_curve, color="#00d4aa", linewidth=1.5, label="Equity (pips)")
    ax.fill_between(x, equity_curve, alpha=0.15, color="#00d4aa")

    # Drawdown overlay
    peak = 0.0
    dd_curve = []
    for v in equity_curve:
        peak = max(peak, v)
        dd_curve.append(v - peak)
    ax.fill_between(x, dd_curve, alpha=0.3, color="#e74c3c", label="Drawdown")

    ax.set_xlabel("Trade #", color="#888")
    ax.set_ylabel("PnL Cumulé (pips)", color="#888")
    ax.tick_params(colors="#888")
    ax.legend(facecolor="#16213e", edgecolor="#333", labelcolor="#ccc")
    ax.grid(True, alpha=0.2, color="#333")

    for spine in ax.spines.values():
        spine.set_color("#333")

    return _fig_to_base64(fig)


def _make_r_distribution(trades: list) -> str:
    """Histogramme de la distribution des R-multiples."""
    if not _MPL_AVAILABLE or not trades:
        return ""

    r_values = [t.r_multiple for t in trades]

    fig, ax = plt.subplots(figsize=(8, 3))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    colors = ["#e74c3c" if r < 0 else "#00d4aa" for r in sorted(r_values)]
    ax.hist(r_values, bins=30, color="#00d4aa", edgecolor="#16213e", alpha=0.8)
    ax.axvline(x=0, color="#e74c3c", linestyle="--", alpha=0.5)

    mean_r = np.mean(r_values)
    ax.axvline(x=mean_r, color="#f39c12", linestyle="-", alpha=0.7, label=f"Mean R={mean_r:.2f}")

    ax.set_xlabel("R-Multiple", color="#888")
    ax.set_ylabel("Fréquence", color="#888")
    ax.tick_params(colors="#888")
    ax.legend(facecolor="#16213e", edgecolor="#333", labelcolor="#ccc")
    ax.grid(True, alpha=0.2, color="#333")

    for spine in ax.spines.values():
        spine.set_color("#333")

    return _fig_to_base64(fig)


def _compute_sharpe(trades: list) -> float:
    """Sharpe ratio approximatif basé sur les PnL quotidiens."""
    if not trades:
        return 0.0

    # Grouper les PnL par jour
    daily_pnl = defaultdict(float)
    for t in trades:
        day = t.entry_time[:10] if t.entry_time else "unknown"
        daily_pnl[day] += t.pnl_pips

    if len(daily_pnl) < 2:
        return 0.0

    returns = list(daily_pnl.values())
    mean_r = np.mean(returns)
    std_r = np.std(returns, ddof=1)
    if std_r == 0:
        return 0.0
    return float(mean_r / std_r * np.sqrt(252))


def _pair_stats(trades: list) -> list:
    """Statistiques par paire."""
    by_pair = defaultdict(list)
    for t in trades:
        by_pair[t.pair].append(t)

    stats = []
    for pair, pair_trades in sorted(by_pair.items()):
        wins = sum(1 for t in pair_trades if t.result == "WIN")
        total = len(pair_trades)
        pnl = sum(t.pnl_pips for t in pair_trades)
        gross_profit = sum(t.pnl_pips for t in pair_trades if t.pnl_pips > 0)
        gross_loss = abs(sum(t.pnl_pips for t in pair_trades if t.pnl_pips < 0))
        pf = gross_profit / gross_loss if gross_loss > 0 else 0.0
        stats.append({
            "pair": pair, "trades": total, "wins": wins,
            "wr": round(wins / total * 100, 1) if total else 0,
            "pnl": round(pnl, 1), "pf": round(pf, 2),
        })
    return stats


def _session_stats(trades: list) -> list:
    """Statistiques par session/killzone."""
    by_session = defaultdict(list)
    for t in trades:
        s = t.session if t.session else "unknown"
        by_session[s].append(t)

    stats = []
    for session, s_trades in sorted(by_session.items()):
        wins = sum(1 for t in s_trades if t.result == "WIN")
        total = len(s_trades)
        pnl = sum(t.pnl_pips for t in s_trades)
        stats.append({
            "session": session, "trades": total, "wins": wins,
            "wr": round(wins / total * 100, 1) if total else 0,
            "pnl": round(pnl, 1),
        })
    return stats


def _day_stats(trades: list) -> list:
    """Statistiques par jour de la semaine."""
    day_names = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    by_day = defaultdict(list)
    for t in trades:
        try:
            dt = datetime.fromisoformat(t.entry_time.replace(" ", "T")[:19])
            by_day[dt.weekday()].append(t)
        except Exception:
            pass

    stats = []
    for day_idx in range(5):  # Lundi à vendredi
        d_trades = by_day.get(day_idx, [])
        wins = sum(1 for t in d_trades if t.result == "WIN")
        total = len(d_trades)
        pnl = sum(t.pnl_pips for t in d_trades)
        stats.append({
            "day": day_names[day_idx], "trades": total, "wins": wins,
            "wr": round(wins / total * 100, 1) if total else 0,
            "pnl": round(pnl, 1),
        })
    return stats


def _gate_stats(blocked: list) -> list:
    """Statistiques par gate de blocage."""
    by_gate = defaultdict(lambda: {"total": 0, "won": 0})
    for b in blocked:
        gate = b.gate
        by_gate[gate]["total"] += 1
        if b.would_have_won:
            by_gate[gate]["won"] += 1

    stats = []
    for gate, data in sorted(by_gate.items()):
        regret = round(data["won"] / data["total"] * 100, 1) if data["total"] else 0
        stats.append({
            "gate": gate, "total": data["total"],
            "won": data["won"], "regret": regret,
        })
    return sorted(stats, key=lambda x: -x["total"])


def generate_html_report(result, output_path: str):
    """
    Génère un rapport HTML standalone.

    Args:
        result: BacktestResult
        output_path: chemin du fichier HTML de sortie
    """
    trades = result.trades
    blocked = result.blocked

    # Métriques globales
    total = len(trades)
    wins = len(result.wins)
    losses = len(result.losses)
    wr = result.win_rate
    pf = result.profit_factor
    sqn = result.sqn
    max_dd = result.max_drawdown_pips
    total_pnl = sum(t.pnl_pips for t in trades)
    avg_r = np.mean([t.r_multiple for t in trades]) if trades else 0
    sharpe = _compute_sharpe(trades)

    # Charts
    equity_b64 = _make_equity_chart(result.equity_curve())
    r_dist_b64 = _make_r_distribution(trades)

    # Stats détaillées
    pair_data = _pair_stats(trades)
    session_data = _session_stats(trades)
    day_data = _day_stats(trades)
    gate_data = _gate_stats(blocked)

    # Critère d'arrêt
    pf_ok = pf >= 1.1
    sqn_ok = sqn >= 0.5
    dd_ok = max_dd < 250  # 250 pips ≈ 25% sur $10k avec 1% risque

    # Couleurs
    wr_color = "#00d4aa" if wr >= 45 else "#f39c12" if wr >= 35 else "#e74c3c"
    pf_color = "#00d4aa" if pf >= 1.3 else "#f39c12" if pf >= 1.1 else "#e74c3c"
    sqn_color = "#00d4aa" if sqn >= 1.6 else "#f39c12" if sqn >= 0.5 else "#e74c3c"

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>TakeOption Backtest — {result.horizon} — {result.start_date} → {result.end_date}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0f0f23; color: #ccc; font-family: 'Segoe UI', system-ui, sans-serif; padding: 20px; }}
h1 {{ color: #00d4aa; margin-bottom: 5px; }}
h2 {{ color: #7c8aff; margin: 30px 0 15px; border-bottom: 1px solid #333; padding-bottom: 5px; }}
.subtitle {{ color: #888; margin-bottom: 20px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin: 20px 0; }}
.card {{ background: #1a1a2e; border-radius: 8px; padding: 15px; text-align: center; }}
.card .value {{ font-size: 28px; font-weight: bold; margin: 5px 0; }}
.card .label {{ font-size: 12px; color: #888; text-transform: uppercase; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
th {{ background: #1a1a2e; color: #7c8aff; text-align: left; padding: 8px 12px; font-size: 13px; }}
td {{ padding: 6px 12px; border-bottom: 1px solid #222; font-size: 13px; }}
tr:hover {{ background: #16213e; }}
.win {{ color: #00d4aa; }}
.loss {{ color: #e74c3c; }}
.neutral {{ color: #f39c12; }}
.chart {{ text-align: center; margin: 15px 0; }}
.chart img {{ max-width: 100%; border-radius: 8px; }}
.verdict {{ padding: 15px; border-radius: 8px; margin: 10px 0; font-size: 16px; font-weight: bold; }}
.verdict.pass {{ background: #0a2e1a; color: #00d4aa; border: 1px solid #00d4aa; }}
.verdict.fail {{ background: #2e0a0a; color: #e74c3c; border: 1px solid #e74c3c; }}
.verdict.warn {{ background: #2e2a0a; color: #f39c12; border: 1px solid #f39c12; }}
footer {{ margin-top: 40px; text-align: center; color: #555; font-size: 12px; }}
</style>
</head>
<body>

<h1>TakeOption Backtest Report</h1>
<p class="subtitle">{result.horizon.upper()} — {', '.join(result.pairs)} — {result.start_date} → {result.end_date}</p>

<!-- 1. RÉSUMÉ -->
<h2>1. Résumé</h2>
<div class="grid">
    <div class="card"><div class="label">Total Trades</div><div class="value">{total}</div></div>
    <div class="card"><div class="label">Win Rate</div><div class="value" style="color:{wr_color}">{wr:.1f}%</div></div>
    <div class="card"><div class="label">Profit Factor</div><div class="value" style="color:{pf_color}">{pf:.2f}</div></div>
    <div class="card"><div class="label">SQN</div><div class="value" style="color:{sqn_color}">{sqn:.2f}</div></div>
    <div class="card"><div class="label">Max Drawdown</div><div class="value" style="color:#e74c3c">{max_dd:.1f} pips</div></div>
    <div class="card"><div class="label">Sharpe Ratio</div><div class="value">{sharpe:.2f}</div></div>
    <div class="card"><div class="label">Total PnL</div><div class="value" style="color:{'#00d4aa' if total_pnl > 0 else '#e74c3c'}">{total_pnl:.1f} pips</div></div>
    <div class="card"><div class="label">Avg R-Multiple</div><div class="value">{avg_r:.2f}</div></div>
</div>

<!-- 2. COURBE D'EQUITY -->
<h2>2. Courbe d'Equity</h2>
<div class="chart">
    {"<img src='data:image/png;base64," + equity_b64 + "' alt='Equity curve'>" if equity_b64 else "<p>Pas assez de données pour le graphique</p>"}
</div>

<!-- 3. PERFORMANCE PAR PAIRE -->
<h2>3. Performance par Paire</h2>
<table>
<tr><th>Paire</th><th>Trades</th><th>Wins</th><th>WR%</th><th>PnL (pips)</th><th>PF</th></tr>
"""
    for p in pair_data:
        pnl_class = "win" if p["pnl"] > 0 else "loss"
        html += f'<tr><td>{p["pair"]}</td><td>{p["trades"]}</td><td>{p["wins"]}</td>'
        html += f'<td>{p["wr"]}%</td><td class="{pnl_class}">{p["pnl"]}</td><td>{p["pf"]}</td></tr>\n'

    html += """</table>

<!-- 4. PERFORMANCE PAR SESSION -->
<h2>4. Performance par Session</h2>
<table>
<tr><th>Session</th><th>Trades</th><th>Wins</th><th>WR%</th><th>PnL (pips)</th></tr>
"""
    for s in session_data:
        pnl_class = "win" if s["pnl"] > 0 else "loss"
        html += f'<tr><td>{s["session"]}</td><td>{s["trades"]}</td><td>{s["wins"]}</td>'
        html += f'<td>{s["wr"]}%</td><td class="{pnl_class}">{s["pnl"]}</td></tr>\n'

    html += """</table>

<!-- 5. PERFORMANCE PAR JOUR -->
<h2>5. Performance par Jour</h2>
<table>
<tr><th>Jour</th><th>Trades</th><th>Wins</th><th>WR%</th><th>PnL (pips)</th></tr>
"""
    for d in day_data:
        pnl_class = "win" if d["pnl"] > 0 else "loss"
        html += f'<tr><td>{d["day"]}</td><td>{d["trades"]}</td><td>{d["wins"]}</td>'
        html += f'<td>{d["wr"]}%</td><td class="{pnl_class}">{d["pnl"]}</td></tr>\n'

    html += f"""</table>

<!-- 6. DISTRIBUTION DES R-MULTIPLES -->
<h2>6. Distribution des R-Multiples</h2>
<div class="chart">
    {"<img src='data:image/png;base64," + r_dist_b64 + "' alt='R distribution'>" if r_dist_b64 else "<p>Pas assez de données</p>"}
</div>

<!-- 7. TRADES INDIVIDUELS -->
<h2>7. Trades ({total})</h2>
<table>
<tr><th>Date</th><th>Paire</th><th>Dir</th><th>Entry</th><th>SL</th><th>TP</th><th>Exit</th><th>PnL</th><th>R</th><th>Spread</th><th>Result</th></tr>
"""
    for t in trades:
        result_class = "win" if t.result == "WIN" else "loss"
        html += f'<tr><td>{t.entry_time[:16]}</td><td>{t.pair}</td><td>{t.direction}</td>'
        html += f'<td>{t.entry_price}</td><td>{t.stop_loss}</td><td>{t.tp1}</td>'
        html += f'<td>{t.exit_price}</td><td class="{result_class}">{t.pnl_pips}</td>'
        html += f'<td>{t.r_multiple}</td><td>{t.spread_pips}</td>'
        html += f'<td class="{result_class}">{t.result}</td></tr>\n'

    html += f"""</table>

<!-- 8. GATE ANALYSIS -->
<h2>8. Gate Analysis ({len(blocked)} setups bloqués)</h2>
<table>
<tr><th>Gate</th><th>Bloqués</th><th>Auraient gagné</th><th>Regret Rate</th></tr>
"""
    for g in gate_data:
        regret_class = "loss" if g["regret"] > 40 else "win"
        html += f'<tr><td>{g["gate"]}</td><td>{g["total"]}</td><td>{g["won"]}</td>'
        html += f'<td class="{regret_class}">{g["regret"]}%</td></tr>\n'

    html += """</table>

<!-- 9. CRITÈRE D'ARRÊT -->
<h2>9. Critère d'Arrêt</h2>
"""

    if total >= 200:
        if pf_ok and sqn_ok and dd_ok:
            html += '<div class="verdict pass">✅ EDGE VALIDÉ — PF ≥ 1.1, SQN ≥ 0.5, DD &lt; 25%. Continuer vers le live.</div>'
        elif not pf_ok:
            html += f'<div class="verdict fail">❌ ARRÊT — Profit Factor = {pf:.2f} &lt; 1.1 après {total} trades. Re-évaluer les fondamentaux.</div>'
        elif not sqn_ok:
            html += f'<div class="verdict fail">❌ ARRÊT — SQN = {sqn:.2f} &lt; 0.5. Résultats trop instables.</div>'
        elif not dd_ok:
            html += f'<div class="verdict fail">❌ ARRÊT IMMÉDIAT — Max Drawdown = {max_dd:.1f} pips &gt; 25%. Risque excessif.</div>'
    elif total >= 100:
        html += f'<div class="verdict warn">⏳ EN COURS — {total}/200 trades. PF={pf:.2f}, SQN={sqn:.2f}. Continuer le paper trading.</div>'
    else:
        html += f'<div class="verdict warn">⏳ INSUFFISANT — Seulement {total} trades. Minimum 200 requis pour conclure.</div>'

    html += f"""
<footer>
    Généré le {datetime.now().strftime('%Y-%m-%d %H:%M')} par TakeOption Backtester v0.1.0<br>
    Spreads réalistes inclus. Slippage 0.5 pips. SL prioritaire si SL+TP même bougie.
</footer>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
