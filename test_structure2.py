import sys, os
sys.path.insert(0, '.')
from data.yfinance_provider import YFinanceProvider
from agents.agent_structure import StructureAgent
from dashboard import extract_dataframes
yf = YFinanceProvider()
md = yf.get_market_data('EURUSD')
dfs = extract_dataframes(md)

agent1 = StructureAgent(symbol='EURUSD')
mtf_data = {'MN': dfs.get('MN'), 'W1': dfs.get('W1'), 'D1': dfs.get('D1')}
report = agent1.analyze_multi_tf(mtf_data)

for tf in ['MN', 'W1', 'D1']:
    rep = report.get(tf)
    if rep:
        print(f"--- {tf} ---")
        print(f"Candles: {len(dfs.get(tf))}")
        print(f"Bias: {rep.get('bias')}")
        print(f"Swings: {len(rep.get('swings', []))}")
        print(f"BOS/CHoCH: {len(rep.get('bos_choch', []))}")
print(f"HTF Alignment: {report.get('htf_alignment')}")
