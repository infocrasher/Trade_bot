import mt5_data as mt5_utils
from agents.agent_time_session import TimeSessionAgent

def test():
    print("Connexion à MT5...")
    try:
        if not mt5_utils.connect_mt5():
            print("Échec de l'initialisation de MT5.")
            return
    except Exception as e:
        print(f"Erreur de connexion MT5 : {e}")
        return
        
    print("Connexion réussie.")
    
    # On choisit M5 pour de la granularité dans l'analyse de temps
    try:
        df = mt5_utils.get_candles("EURUSD", mt5_utils.TIMEFRAMES["M5"], count=500)
    except Exception as e:
        print(f"Erreur lors de la récupération des bougies : {e}")
        return
        
    # La plupart des brokers (ex: IC Markets, FTMO, etc.) sont en UTC+2 ou UTC+3
    # On va simuler un broker_utc_offset de 2
    agent = TimeSessionAgent(broker_utc_offset=2)
    
    # Utilisons la dernière bougie comme heure "actuelle"
    current_broker_time = df.iloc[-1]['time']
    
    print(f"\nLancement de l'analyse Time & Session...")
    report = agent.analyze(df, current_broker_time)
    
    print("\n" + "="*50)
    print("RAPPORT D'ANALYSE TIME & SESSION (ICT)")
    print("="*50)
    print(f"Heure NY Actuelle : {report['current_time_ny']}")
    
    print("\n--- FILTRES DE TEMPS ---")
    kz = report['killzone']
    if kz:
        print(f"Killzone Active    : {kz['name']} ({kz['start']}-{kz['end']}) - Reste {kz['minutes_remaining']} min")
    else:
        print("Killzone Active    : Hors killzone")
        
    sb = report['silver_bullet']
    if sb:
        print(f"Silver Bullet      : {sb['name']} ({sb['start']}-{sb['end']})")
    else:
        print("Silver Bullet      : Aucune")
        
    df_filter = report['day_filter']
    print(f"Jour et Qualité    : {df_filter.get('name')} -> {df_filter.get('quality', '').upper()} ({df_filter.get('note', '')})")
    
    print("\n--- ANALYSE ASIAN RANGE & PO3 ---")
    ar = report['asian_range']
    if not ar.get('error'):
        print(f"Asian Range        : {ar['range_pips']} pips (High: {ar['high']}, Low: {ar['low']})")
        print(f"Session Complète   : {'Oui' if ar.get('is_complete') else 'Non'}")
    else:
        print(f"Asian Range        : {ar['error']}")
        
    po3 = report['po3_phase']
    print(f"Phase Power of 3   : {po3['phase'].upper()} ({po3['description']})")
    print(f"Asian Range Cassé  : {po3['asian_range_broken'].upper()}")
    print(f"Biais Suggéré (AR) : {po3['suggested_bias'].upper()}")
    
    print("\n--- JUDAS SWING ---")
    js = report['judas_swing']
    if js.get('detected', False):
        print(f"Détecté            : OUI ({js['type']})")
        print(f"Niveau Balayé      : {js['sweep_level']}")
        print(f"Extrême            : {js['sweep_extreme']}")
        print(f"Renversement Confirmé : {'Oui' if js['reversal_confirmed'] else 'Non'}")
    else:
        print(f"Détecté            : NON ({js.get('reason', '')})")
        
    print("\nVERDICT FINAL :")
    print(f"- Trade Autorisé   : {'OUI' if report['can_trade'] else 'NON'}")
    print(f"- Qualité du Trade : {report['trade_quality'].upper()}")
    print("="*50)

if __name__ == "__main__":
    test()
