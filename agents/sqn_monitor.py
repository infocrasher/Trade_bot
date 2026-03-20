import math

def get_profile_weight_multiplier(profile_id: str, paper_history: list) -> float:
    """
    Calcule le multiplicateur de poids d'un profil basé sur son SQN (System Quality Number) récent.
    SQN = √(N) * (moyenne(PnL) / stdev(PnL))
    
    Règles de mise en quarantaine :
    - Si SQN ≥ 1.0 -> 1.0 (poids normal)
    - Si 0.5 ≤ SQN < 1.0 -> 0.5 (quarantaine 50%)
    - Si SQN < 0.5 -> 0.25 (quarantaine sévère)
    - Si moins de 10 trades -> 1.0 (pas assez de données)
    """
    # Filtre: trades fermés, appartenant à ce profil, avec un vrai PnL (TP ou SL)
    # On exclut expréssèment les expirés, trop loin, etc.
    valid_reasons = {"TP1", "TP2", "TP3", "SL", "TP1 (offline)", "SL (offline)"}
    
    profile_trades = []
    # On itère en sens inverse pour avoir les plus récents en premier
    # Si paper_history est chronologique, on reverse.
    sorted_history = sorted(paper_history, key=lambda x: x.get("closed_at", ""), reverse=True)
    
    for t in sorted_history:
        # Vérification du profil
        pid = t.get("profile_id", "")
        # Fallbacks pour les requêtes legacy
        if not pid and t.get("narrative", ""):
            if "MSS" in t.get("narrative", ""):
                pid = "pure_pa"
            else:
                pid = "ict_strict"
        
        # Mapping simple (ict_strict -> ict, etc.) ou correspondance exacte
        # Mais dans MetaConvergence / MetaOrchestrator, les écoles sont "ict", "elliott", "vsa", "pure_pa", "legacy"
        mapped_pid = pid
        if pid == "ict_strict": mapped_pid = "ict"
        elif pid == "pure_pa": mapped_pid = "pure_pa"
        elif pid == "elliott": mapped_pid = "elliott"
        elif pid == "vsa": mapped_pid = "vsa"
        
        if mapped_pid == profile_id and t.get("status") == "closed":
            # Uniquement TP ou SL
            reason = t.get("close_reason", "")
            if reason in valid_reasons or "TP" in reason or "SL" in reason:
                if "pnl_pips" in t:
                    profile_trades.append(float(t["pnl_pips"]))
        
        if len(profile_trades) >= 20:
            break

    n = len(profile_trades)
    if n < 10:
        return 1.0

    mean_pnl = sum(profile_trades) / n
    
    # Ecart-type (population stdev)
    variance = sum((x - mean_pnl) ** 2 for x in profile_trades) / n
    stdev_pnl = math.sqrt(variance)

    if stdev_pnl == 0:
        # Cas très rare: tous les trades ont exactement le même PnL
        sqn = float('inf') if mean_pnl > 0 else -float('inf')
    else:
        sqn = math.sqrt(n) * (mean_pnl / stdev_pnl)

    if sqn >= 1.0:
        return 1.0
    elif 0.5 <= sqn < 1.0:
        return 0.5
    else:
        return 0.25
