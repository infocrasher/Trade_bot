import pandas as pd
from datetime import datetime, timedelta
import zoneinfo

KILLZONES = {
    "asian": {"start": "19:00", "end": "00:00"},       # 19h-00h NY (dimanche soir → lundi matin)
    "london": {"start": "02:00", "end": "05:00"},       # 2h-5h NY
    "london_close": {"start": "10:00", "end": "12:00"}, # London Close Killzone
    "ny_am": {"start": "07:00", "end": "10:00"},        # 7h-10h NY (Killzone principale)
    "ny_pm": {"start": "13:30", "end": "16:00"},        # 13h30-16h NY (Ajusté pour inclure NY PM)
}

SILVER_BULLET_WINDOWS = {
    "london_sb": {"start": "03:00", "end": "04:00"},    # 3h-4h NY
    "ny_am_sb": {"start": "10:00", "end": "11:00"},     # 10h-11h NY
    "ny_pm_sb": {"start": "14:00", "end": "15:00"},     # 14h-15h NY
}

MACROS = [
    {"id": "midnight_open",  "name": "Midnight Open Macro",  "start": "23:50", "end": "00:10",  "crosses_midnight": True},
    {"id": "london_open",    "name": "London Open Macro",    "start": "01:50", "end": "02:10",  "crosses_midnight": False},
    {"id": "london_am_1",    "name": "London AM Macro 1",    "start": "04:03", "end": "04:23",  "crosses_midnight": False},
    {"id": "london_am_2",    "name": "London AM Macro 2",    "start": "05:13", "end": "05:33",  "crosses_midnight": False},
    {"id": "ny_open",        "name": "NY Open Macro",        "start": "07:50", "end": "08:10",  "crosses_midnight": False},
    {"id": "ny_am_1",        "name": "NY AM Macro 1",        "start": "08:50", "end": "09:10",  "crosses_midnight": False},
    {"id": "ny_am_2",        "name": "NY AM Macro 2",        "start": "09:50", "end": "10:10", "crosses_midnight": False},
    {"id": "ny_am_3",        "name": "NY AM Macro 3",        "start": "10:50", "end": "11:10", "crosses_midnight": False},
    {"id": "ny_lunch",       "name": "NY Lunch Macro",       "start": "11:50", "end": "12:10", "crosses_midnight": False},
    {"id": "ny_pm_1",        "name": "NY PM Macro 1",        "start": "13:10", "end": "13:30", "crosses_midnight": False},
    {"id": "ny_pm_2",        "name": "NY PM Macro 2",        "start": "14:50", "end": "15:10", "crosses_midnight": False},
    {"id": "ny_close",       "name": "NY Close Macro",       "start": "15:15", "end": "15:45", "crosses_midnight": False},
]

# Filtres journaliers ICT
DAY_FILTERS = {
    0: {"name": "Monday", "quality": "setup", "note": "Weekly opening range — Accumulation phase. Fausses directions fréquentes. Seek & Destroy avant 10h. NE PAS trader les breakouts du lundi."},
    1: {"name": "Tuesday", "quality": "prime", "note": "Manipulation phase — H/L Weekly se forme ici dans 62-73% des cas (stats ICT). Judas Swing probable. Meilleur jour pour capter le vrai move."},
    2: {"name": "Wednesday", "quality": "prime", "note": "Distribution/Continuation — si le H/L Weekly n'est pas formé mardi, il se forme mercredi matin avant 10h NY dans 20% des cas supplémentaires."},
    3: {"name": "Thursday", "quality": "prime", "note": "Distribution finale — objectifs hebdo en cours d'atteinte. Trailing stops, pas de nouveaux setups majeurs."},
    4: {"name": "Friday", "quality": "caution", "note": "Clôture hebdo — retours fair value, prises de profits institutionnelles. Fermer les positions avant 14h NY."},
    5: {"name": "Saturday", "quality": "closed", "note": "Marché fermé"},
    6: {"name": "Sunday", "quality": "closed", "note": "Marché fermé (sauf ouverture dimanche soir)"},
}

def to_ny_time(broker_time: datetime, broker_utc_offset: int) -> datetime:
    """
    Convertit l'heure du broker (souvent UTC+2 ou UTC+3) en heure New York.
    broker_utc_offset : offset UTC du serveur MT5 (ex: 2 pour UTC+2, 3 pour UTC+3)
    Retourne l'heure en NY (EST = UTC-5, EDT = UTC-4).
    """
    try:
        # Essayer d'utiliser zoneinfo pour gérer EDT/EST automatiquement
        # On suppose que broker_time n'est pas timezone-aware.
        
        # 1. On passe l'heure du broker en UTC
        utc_time = broker_time - timedelta(hours=broker_utc_offset)
        # On rend l'heure utc timezone-aware
        utc_time = utc_time.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        
        # 2. Conversion vers NY
        ny_time = utc_time.astimezone(zoneinfo.ZoneInfo("America/New_York"))
        
        # On retourne une date naive pour faciliter les comparaisons (au format NY)
        return ny_time.replace(tzinfo=None)
        
    except Exception:
        # Fallback si zoneinfo plante : offset fixe UTC-5 (EST)
        utc_time = broker_time - timedelta(hours=broker_utc_offset)
        ny_time = utc_time - timedelta(hours=5)
        return ny_time

class TimeSessionAgent:
    def __init__(self, broker_utc_offset: int = 2):
        """
        broker_utc_offset : offset UTC du serveur MT5. 
        La plupart des brokers MT5 sont en UTC+2 (hiver) ou UTC+3 (été).
        """
        self.broker_utc_offset = broker_utc_offset

    def _is_time_in_window(self, ny_time: datetime, start_str: str, end_str: str) -> bool:
        """
        Vérifie si une heure donnée est dans une fenêtre (gère le passage à minuit pour l'Asian Killzone).
        """
        start_hour, start_minute = map(int, start_str.split(':'))
        end_hour, end_minute = map(int, end_str.split(':'))
        
        start_time = ny_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        end_time = ny_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        
        # Cas spécial pour Asian range qui traverse minuit (19:00 - 00:00)
        if end_time <= start_time:
            # Soit on est après start_time aujourd'hui, soit on est avant end_time aujourd'hui
            if ny_time >= start_time or ny_time < end_time:
                return True
            return False
            
        return start_time <= ny_time < end_time

    def _get_minutes_remaining(self, ny_time: datetime, end_str: str) -> int:
        end_hour, end_minute = map(int, end_str.split(':'))
        end_time = ny_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        
        # Si end_time est déjà passé, c'est que la fin est demain (cas Asian 00:00)
        if end_time < ny_time:
            end_time += timedelta(days=1)
            
        diff = end_time - ny_time
        return int(diff.total_seconds() / 60)

    def get_active_killzone(self, current_time_ny: datetime) -> dict:
        """
        Retourne la killzone active ou None.
        """
        for kz_id, times in KILLZONES.items():
            if self._is_time_in_window(current_time_ny, times["start"], times["end"]):
                minutes = self._get_minutes_remaining(current_time_ny, times["end"])
                
                # Vérifier si on est aussi dans un Silver Bullet
                sb_active = self.get_active_silver_bullet(current_time_ny) is not None
                
                name_map = {
                    "asian": "Asian Killzone",
                    "london": "London Killzone",
                    "london_close": "London Close",
                    "ny_am": "New York AM Killzone",
                    "ny_pm": "New York PM Killzone"
                }
                
                return {
                    "id": kz_id,
                    "name": name_map.get(kz_id, kz_id),
                    "start": times["start"],
                    "end": times["end"],
                    "minutes_remaining": minutes,
                    "is_silver_bullet": sb_active
                }
        return None

    def get_active_silver_bullet(self, current_time_ny: datetime) -> dict:
        """
        Retourne la fenêtre Silver Bullet active ou None.
        """
        for sb_id, times in SILVER_BULLET_WINDOWS.items():
             if self._is_time_in_window(current_time_ny, times["start"], times["end"]):
                 minutes = self._get_minutes_remaining(current_time_ny, times["end"])
                 
                 name_map = {
                     "london_sb": "London Silver Bullet",
                     "ny_am_sb": "NY AM Silver Bullet",
                     "ny_pm_sb": "NY PM Silver Bullet"
                 }
                 
                 return {
                     "id": sb_id,
                     "name": name_map.get(sb_id, sb_id),
                     "start": times["start"],
                     "end": times["end"],
                     "minutes_remaining": minutes
                 }
        return None

    def get_day_filter(self, current_time_ny: datetime) -> dict:
        """
        Retourne les infos sur le jour actuel.
        """
        weekday = current_time_ny.weekday() # 0 = Monday, 6 = Sunday
        day_info = DAY_FILTERS.get(weekday, {}).copy()
        
        # Exception pour l'ouverture du dimanche soir en Asie
        if weekday == 6 and current_time_ny.hour >= 17:
             day_info["quality"] = "setup" # On le traite comme monday setup
             day_info["note"] = "Ouverture asiatique (Dimanche soir)"
             
        # Seek & Destroy — Lundi avant 10h
        if weekday == 0:
             if current_time_ny.hour < 10:
                 day_info["quality"] = "seek_destroy"
                 day_info["note"] = "Lundi avant 10h: Seek & Destroy profile"
             else:
                 day_info["quality"] = "setup"
                 day_info["note"] = "Lundi après 10h: Setup profile"
             
        day_info["can_trade"] = day_info["quality"] in ["prime", "setup"]

        # Contexte AMD Weekly
        weekday = current_time_ny.weekday()
        if weekday == 0:
            day_info["amd_phase"] = "accumulation"
            day_info["amd_note"]  = "Range formation — attendre le Judas Swing"
        elif weekday == 1:
            day_info["amd_phase"] = "manipulation"
            day_info["amd_note"]  = "Judas Swing probable — H/L Weekly se forme (68% des cas)"
            day_info["amd_stat"]  = 0.68
        elif weekday == 2:
            day_info["amd_phase"] = "distribution"
            day_info["amd_note"]  = "Continuation ou reversal — H/L Weekly possible (20%)"
            day_info["amd_stat"]  = 0.20
        elif weekday == 3:
            day_info["amd_phase"] = "distribution"
            day_info["amd_note"]  = "Objectifs hebdo en cours — trailing uniquement"
        elif weekday == 4:
            day_info["amd_phase"] = "closing"
            day_info["amd_note"]  = "Fermer avant 14h NY — retours fair value"
        else:
            day_info["amd_phase"] = "closed"
            day_info["amd_note"]  = "Marché fermé"

        return day_info

    def get_asian_range(self, df: pd.DataFrame) -> dict:
        """
        Calcule le range asiatique du jour (19:00-00:00 NY du jour précédent).
        Il faut convertir chaque timestamp broker du DF en timestamp NY.
        """
        if df is None or len(df) == 0:
            return {"error": "No data"}
            
        # Créer une série NY time
        ny_times = df['time'].apply(lambda x: to_ny_time(x, self.broker_utc_offset))
        
        # Trouver la date de la séance actuelle (aujourd'hui)
        # Si on est le matin, on cherche la session asiatique qui a commencé la veille à 19h
        last_ny_time = ny_times.iloc[-1]
        
        # Soit on est pendant l'asian session aujourd'hui, soit elle est passée et on cherche celle qui s'est terminée à minuit
        asian_end_date = last_ny_time.date()
        if last_ny_time.hour >= 19:
             asian_end_date = last_ny_time.date() + timedelta(days=1)
             
        # Le range commence la veille à 19:00 et finit à 00:00 du jour de asian_end_date
        start_target = datetime(asian_end_date.year, asian_end_date.month, asian_end_date.day) - timedelta(days=1)
        start_target = start_target.replace(hour=19, minute=0, second=0)
        
        end_target = datetime(asian_end_date.year, asian_end_date.month, asian_end_date.day) 
        end_target = end_target.replace(hour=0, minute=0, second=0)
        
        # Filtrer le dataframe
        mask = (ny_times >= start_target) & (ny_times < end_target)
        session_df = df[mask]
        
        if len(session_df) == 0:
            return {
                "high": None, "low": None, "midpoint": None, 
                "range_pips": 0, "is_complete": False, "error": "Not enough data"
            }
            
        high = session_df['high'].max()
        low = session_df['low'].min()
        
        # Vérifier si la session est complète
        is_complete = last_ny_time >= end_target
        
        # Calcul simple en pips (assume paires forex classiques avec 4 décimales ou JPY avec 2)
        # On va utiliser une conversion générique basique pour l'illustration
        range_val = high - low
        
        return {
            "high": float(high),
            "low": float(low),
            "midpoint": float((high + low) / 2),
            "range_pips": round(range_val * 10000, 1) if high < 2 else round(range_val * 100, 1),
            "is_complete": is_complete
        }

    def get_po3_phase(self, current_time_ny: datetime, df: pd.DataFrame, asian_range: dict) -> dict:
        """
        Détermine la phase Power of 3 en cours basée sur l'heure et le prix.
        """
        if "error" in asian_range or not asian_range.get("is_complete", False):
             return {"phase": "accumulation", "description": "Asian Range en formation", "asian_range_broken": "none", "suggested_bias": "neutral"}
             
        ar_high = asian_range["high"]
        ar_low = asian_range["low"]
        
        ny_times = df['time'].apply(lambda x: to_ny_time(x, self.broker_utc_offset))
        
        # Heure de fin de l'asian range (minuit NY)
        ar_end = current_time_ny.replace(hour=0, minute=0, second=0, microsecond=0)
        if current_time_ny.hour >= 19:
            ar_end += timedelta(days=1)
            
        # Analyser depuis minuit
        post_asian_mask = (ny_times >= ar_end) & (ny_times <= current_time_ny)
        post_asian_df = df[post_asian_mask]
        
        broken_high = False
        broken_low = False
        
        if len(post_asian_df) > 0:
            broken_high = post_asian_df['high'].max() > ar_high
            broken_low = post_asian_df['low'].min() < ar_low
            
        asian_range_broken = "none"
        suggested_bias = "neutral"
        
        if broken_high and broken_low:
             asian_range_broken = "both"
             suggested_bias = "neutral" # chop/consolidation complexe
        elif broken_high:
             asian_range_broken = "high"
             suggested_bias = "bearish" # On chasse au-dessus pour vendre
        elif broken_low:
             asian_range_broken = "low"
             suggested_bias = "bullish" # On chasse en-dessous pour acheter
             
             
        kz = self.get_active_killzone(current_time_ny)
        
        if kz and kz["id"] == "asian":
            phase = "accumulation"
            desc = "Session asiatique — formation du range"
        elif kz and kz["id"] == "london":
             phase = "manipulation"
             desc = "London Killzone — stop hunt potentiel (Judas Swing)"
        elif kz and "ny" in kz["id"]:
             phase = "distribution"
             desc = "NY Session — vrai mouvement directionnel"
        else:
             phase = "transition"
             desc = "Hors horaires principaux ICT"
             
        return {
            "phase": phase,
            "description": desc,
            "asian_range_broken": asian_range_broken,
            "suggested_bias": suggested_bias
        }

    def detect_judas_swing(self, df: pd.DataFrame, asian_range: dict, current_time_ny: datetime) -> dict:
        """
        Détecte un Judas Swing pendant la London Killzone.
        """
        # Vérifie qu'on est en London KZ et qu'on a un range Asiatique
        kz = self.get_active_killzone(current_time_ny)
        if not kz or kz["id"] != "london":
             return {"detected": False, "reason": "Not in London Killzone"}
             
        if "error" in asian_range or not asian_range.get("is_complete", False):
             return {"detected": False, "reason": "Asian range not complete"}
             
        ar_high = asian_range["high"]
        ar_low = asian_range["low"]
        
        ny_times = df['time'].apply(lambda x: to_ny_time(x, self.broker_utc_offset))
        
        # Début London = 02:00 NY
        london_start = current_time_ny.replace(hour=2, minute=0, second=0, microsecond=0)
        
        london_mask = (ny_times >= london_start) & (ny_times <= current_time_ny)
        london_df = df[london_mask]
        
        if len(london_df) == 0:
            return {"detected": False, "reason": "No data in London"}
            
        current_price = london_df.iloc[-1]['close']
        london_high = london_df['high'].max()
        london_low = london_df['low'].min()
        
        judas_type = None
        sweep_level = None
        sweep_extreme = None
        reversal_confirmed = False
        
        # 1. Tester Bearish Judas (fausse cassure à la hausse)
        if london_high > ar_high:
            judas_type = "bearish_judas"
            sweep_level = ar_high
            sweep_extreme = london_high
            # Confirmé si le prix est revenu sous le haut du AR
            if current_price < ar_high:
                reversal_confirmed = True
                
        # 2. Tester Bullish Judas (fausse cassure à la baisse)
        elif london_low < ar_low:
             judas_type = "bullish_judas"
             sweep_level = ar_low
             sweep_extreme = london_low
             # Confirmé si le prix est revenu au-dessus du bas du AR
             if current_price > ar_low:
                 reversal_confirmed = True
                 
        if judas_type:
             return {
                 "detected": True,
                 "type": judas_type,
                 "sweep_level": float(sweep_level),
                 "sweep_extreme": float(sweep_extreme),
                 "reversal_confirmed": reversal_confirmed,
                 "time": current_time_ny.strftime("%Y-%m-%d %H:%M")
             }
             
        return {"detected": False, "reason": "No Asian range sweep"}


    def get_active_macro(self, ny_time: datetime) -> dict | None:
        """
        Vérifie si l'heure actuelle est dans une Macro algorithmique.
        """
        for macro in MACROS:
            if self._is_time_in_window(ny_time, macro["start"], macro["end"]):
                minutes = self._get_minutes_remaining(ny_time, macro["end"])
                return {
                    "id": macro["id"],
                    "name": macro["name"],
                    "minutes_remaining": minutes
                }
        return None

    def calculate_midnight_open(self, df_m5: pd.DataFrame) -> dict:
        """
        Identifie le prix à 00:00 NY (Midnight Open).
        """
        if df_m5 is None or len(df_m5) == 0:
            return {"midnight_open": None, "current_vs_midnight": "unknown"}
            
        ny_times = df_m5['time'].apply(lambda x: to_ny_time(x, self.broker_utc_offset))
        current_time_ny = ny_times.iloc[-1]
        
        # Le minuit actuel est le 00:00 du jour de current_time_ny
        midnight_target = current_time_ny.replace(hour=0, minute=0, second=0, microsecond=0)
        
        mask = ny_times >= midnight_target
        valid_df = df_m5[mask]
        
        if len(valid_df) == 0:
            return {"midnight_open": None, "current_vs_midnight": "unknown"}
            
        midnight_open_price = float(valid_df.iloc[0]['open'])
        current_price = float(df_m5.iloc[-1]['close'])
        
        current_vs_midnight = "discount" if current_price < midnight_open_price else "premium"
        
        return {
            "midnight_open": midnight_open_price,
            "current_vs_midnight": current_vs_midnight
        }

    def get_trade_quality(self, kz: dict, sb: dict, macro: dict, day_filter: dict, judas: dict) -> str:
        if not day_filter.get("can_trade", False) or kz is None:
            return "no_trade"
            
        if sb is not None and day_filter["quality"] == "prime" and judas.get("detected", False) and macro is not None:
            return "high"
        elif kz is not None and day_filter["quality"] in ["prime", "setup"] and macro is not None:
            return "medium"
        elif kz is not None:
            return "low"
            
        return "no_trade"

    def analyze(self, df: pd.DataFrame, current_broker_time: datetime = None) -> dict:
        """
        Analyse temporelle complète.
        """
        if current_broker_time is None:
             if df is not None and len(df) > 0:
                 current_broker_time = df.iloc[-1]['time']
             else:
                 current_broker_time = datetime.now()
                 
        current_time_ny = to_ny_time(current_broker_time, self.broker_utc_offset)
        
        kz = self.get_active_killzone(current_time_ny)
        sb = self.get_active_silver_bullet(current_time_ny)
        macro = self.get_active_macro(current_time_ny)
        day_filter = self.get_day_filter(current_time_ny)
        asian_range = self.get_asian_range(df)
        po3 = self.get_po3_phase(current_time_ny, df, asian_range)
        judas = self.detect_judas_swing(df, asian_range, current_time_ny)
        midnight_open = self.calculate_midnight_open(df)
        
        # Calcul Synthèse trade quality
        trade_quality = self.get_trade_quality(kz, sb, macro, day_filter, judas)
        can_trade = trade_quality != "no_trade"
        
        return {
            "current_time_ny": current_time_ny.strftime("%Y-%m-%d %H:%M"),
            "killzone": kz,
            "silver_bullet": sb,
            "active_macro": macro,
            "day_filter": day_filter,
            "asian_range": asian_range,
            "po3_phase": po3,
            "judas_swing": judas,
            "midnight_open": midnight_open,
            "can_trade": can_trade,
            "trade_quality": trade_quality
        }
