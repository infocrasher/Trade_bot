import mt5_data as mt5_utils
from agents.agent_structure import StructureAgent

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
    
    agent = StructureAgent(symbol="EURUSD", structure_tf="H1", entry_tf="M5")
    
    print(f"Lancement de l'analyse sur {agent.symbol}...")
    report = agent.analyze()
    
    if "error" in report:
        print(f"Erreur d'analyse: {report['error']}")
        return
        
    print("\n" + "="*50)
    print("RAPPORT D'ANALYSE STRUCTURE")
    print("="*50)
    print(f"Symbole : {report['symbol']}")
    print(f"Structure TF : {report['structure_tf']}")
    print(f"Entry TF : {report['entry_tf']}")
    print(f"Timestamp : {report['timestamp']}")
    print(f"Biais Actuel : {report['bias'].upper()}")
    
    open_fvgs = [f for f in report['fvg'] if f['status'] == 'open']
    unmitigated_obs = [ob for ob in report['order_blocks'] if ob['status'] == 'unmitigated']
    last_bos_choch = report['bos_choch'][-1] if report['bos_choch'] else None
    
    print("\nRESUME :")
    print(f"- Swings détectés : {len(report['swings'])}")
    print(f"- Displacements : {len(report['displacements'])}")
    print(f"- FVG ouverts : {len(open_fvgs)}")
    print(f"- OB non mitigés : {len(unmitigated_obs)}")
    
    if last_bos_choch:
        print(f"- Dernier BOS/CHoCH : {last_bos_choch['type'].upper()} à {last_bos_choch['time']}")
    
    print(f"- Liquidity Sweeps : {len(report['liquidity_sweeps'])}")
    print("="*50)
    
if __name__ == "__main__":
    test()
