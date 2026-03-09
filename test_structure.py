import sys, os
sys.path.insert(0, '.')
from data.yfinance_provider import YFinanceProvider
from agents.agent_structure import StructureAgent
from dashboard import extract_dataframes

print("Fetching data...")
yf = YFinanceProvider()
md = yf.get_market_data('EURUSD')

print(f"Data status: {md.get('status')} - source: {md.get('source')}")
dfs = extract_dataframes(md)

for tf in ['D1', 'H4']:
    df = dfs.get(tf)
    if df is not None:
        print(f"TF {tf}: {len(df)} candles")

agent1 = StructureAgent(symbol='EURUSD')
mtf_data = {'W1': dfs.get('W1'), 'D1': dfs.get('D1'), 'H4': dfs.get('H4')}
report = agent1.analyze_multi_tf(mtf_data)

print("\nHierarchical Report:")
for tf in ['D1', 'H4']:
    rep = report.get(tf)
    if rep:
        print(f"--- {tf} ---")
        print(f"Bias: {rep.get('bias')}")
        print(f"Swings: {len(rep.get('swings', []))}")
        print(f"BOS/CHoCH: {len(rep.get('bos_choch', []))}")

print(f"\nHTF Alignment: {report.get('htf_alignment')}")
