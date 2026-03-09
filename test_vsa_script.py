import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

from agents.vsa.orchestrator import VSAOrchestrator
from config import GEMINI_API_KEY

orch = VSAOrchestrator(gemini_api_key=GEMINI_API_KEY, enable_charts=True)

pairs = ['EURUSD', 'XAUUSD', 'BTCUSD']
for symbol in pairs:
    result = orch.get_signal_for_meta(symbol, 'daily')
    print(f"\n{symbol}: score={result['score']} | {result['direction']} | {result['action']} | {result['signal']} | phase={result['wyckoff_phase']}")
