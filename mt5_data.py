class MT5Mock:
    TIMEFRAME_H4 = 16388
    TIMEFRAME_H1 = 16385
    TIMEFRAME_M15 = 15
    TIMEFRAME_M5 = 5
    def initialize(self): return True
    def last_error(self): return "Mocked MT5"
    def copy_rates_from_pos(self, *args, **kwargs): return None

mt5 = MT5Mock()
import pandas as pd

SYMBOLS = [
    "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD",
    "USDCHF", "NZDUSD", "EURJPY", "GBPJPY", "EURGBP",
    "US100", "US500", "XAUUSD", "USOIL"
]

TIMEFRAMES = {
    "H4": mt5.TIMEFRAME_H4,
    "H1": mt5.TIMEFRAME_H1,
    "M15": mt5.TIMEFRAME_M15,
    "M5": mt5.TIMEFRAME_M5,
}

def connect_mt5():
    if not mt5.initialize():
        raise ConnectionError(f"MT5 init failed: {mt5.last_error()}")
    return True

def get_candles(symbol: str, timeframe: int, count: int = 500) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        raise ValueError(f"No data for {symbol} on {timeframe}")
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['body'] = abs(df['close'] - df['open'])
    df['range'] = df['high'] - df['low']
    df['body_ratio'] = df['body'] / df['range'].replace(0, float('nan'))
    return df
