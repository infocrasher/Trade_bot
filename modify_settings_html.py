import re

with open("dashboard/templates/settings.html", "r") as f:
    text = f.read()

# 1. Insert new HTML blocks after Bot Core
html_to_insert = """
            <!-- SCORING (PROFILES) -->
            <div class="section">
                <div class="section-title">📊 Scoring Multi-Profils</div>
                <div class="form-row">
                    <div class="form-label">
                        <div class="name">Score minimum exécution</div>
                        <div class="desc">Score pour full size</div>
                    </div>
                    <div class="form-control">
                        <input type="number" id="score_min_exec" min="0" max="100" step="1">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-label">
                        <div class="name">Score minimum half-size</div>
                        <div class="desc">Score pour size réduite</div>
                    </div>
                    <div class="form-control">
                        <input type="number" id="score_min_half" min="0" max="100" step="1">
                    </div>
                </div>
            </div>

            <!-- GATES ICT -->
            <div class="section">
                <div class="section-title">🚦 Gates ICT (Filtres)</div>
                <div class="form-row">
                    <div class="form-label"><div class="name">R:R minimum</div><div class="desc">Ratio R:R</div></div>
                    <div class="form-control" style="display:flex;gap:10px;justify-content:flex-end;align-items:center;">
                        <input type="number" id="gate_rr_value" min="0" max="10" step="0.5" style="width:70px">
                        <div class="toggle-wrap">
                            <span class="toggle-label" id="gate_rr_label">ON</span>
                            <label class="toggle"><input type="checkbox" id="gate_rr_active"><span class="toggle-slider"></span></label>
                        </div>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-label"><div class="name">Score OB minimum</div><div class="desc">Qualité OB (0-5)</div></div>
                    <div class="form-control" style="display:flex;gap:10px;justify-content:flex-end;align-items:center;">
                        <input type="number" id="gate_ob_value" min="0" max="5" step="1" style="width:70px">
                        <div class="toggle-wrap">
                            <span class="toggle-label" id="gate_ob_label">ON</span>
                            <label class="toggle"><input type="checkbox" id="gate_ob_active"><span class="toggle-slider"></span></label>
                        </div>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-label"><div class="name">Spread max KS4</div><div class="desc">Spread toléré en pips</div></div>
                    <div class="form-control" style="display:flex;gap:10px;justify-content:flex-end;align-items:center;">
                        <input type="number" id="gate_spread_ks4_value" min="0" max="10" step="0.5" style="width:70px">
                        <div class="toggle-wrap">
                            <span class="toggle-label" id="gate_spread_label">ON</span>
                            <label class="toggle"><input type="checkbox" id="gate_spread_ks4_active"><span class="toggle-slider"></span></label>
                        </div>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-label"><div class="name">SL minimum</div><div class="desc">Minimum en pips</div></div>
                    <div class="form-control" style="display:flex;gap:10px;justify-content:flex-end;align-items:center;">
                        <input type="number" id="gate_sl_min_value" min="0" max="20" step="1" style="width:70px">
                        <div class="toggle-wrap">
                            <span class="toggle-label" id="gate_sl_min_label">ON</span>
                            <label class="toggle"><input type="checkbox" id="gate_sl_min_active"><span class="toggle-slider"></span></label>
                        </div>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-label"><div class="name">T-20 Malus</div></div>
                    <div class="form-control"><div class="toggle-wrap">
                        <span class="toggle-label" id="gate_t20_label">ON</span>
                        <label class="toggle"><input type="checkbox" id="gate_t20_malus_active"><span class="toggle-slider"></span></label>
                    </div></div>
                </div>
                <div class="form-row">
                    <div class="form-label"><div class="name">ENIGMA Obligatoire</div></div>
                    <div class="form-control"><div class="toggle-wrap">
                        <span class="toggle-label" id="gate_enigma_label">OFF</span>
                        <label class="toggle"><input type="checkbox" id="gate_enigma_mandatory_active"><span class="toggle-slider"></span></label>
                    </div></div>
                </div>
                <div class="form-row">
                    <div class="form-label"><div class="name">Gate SOD</div></div>
                    <div class="form-control"><div class="toggle-wrap">
                        <span class="toggle-label" id="gate_sod_label">ON</span>
                        <label class="toggle"><input type="checkbox" id="gate_sod_active"><span class="toggle-slider"></span></label>
                    </div></div>
                </div>
                <div class="form-row">
                    <div class="form-label"><div class="name">HTF Alignment</div><div class="desc">Strict alignment</div></div>
                    <div class="form-control" style="display:flex;gap:10px;justify-content:flex-end;align-items:center;">
                        <select id="gate_htf_strict_mode" style="background:#0f172a;color:#e2e8f0;border:1px solid #1e293b;border-radius:6px;padding:4px;">
                            <option value="D1+H4+H1">D1+H4+H1</option>
                            <option value="D1+H1">D1+H1</option>
                        </select>
                        <div class="toggle-wrap">
                            <span class="toggle-label" id="gate_htf_strict_label">ON</span>
                            <label class="toggle"><input type="checkbox" id="gate_htf_strict_active"><span class="toggle-slider"></span></label>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TEMPOREL -->
            <div class="section">
                <div class="section-title">⏱️ Temporel</div>
                <div class="form-row">
                    <div class="form-label"><div class="name">Killzones obligatoires</div></div>
                    <div class="form-control"><div class="toggle-wrap">
                        <span class="toggle-label" id="time_kz_label">ON</span>
                        <label class="toggle"><input type="checkbox" id="time_killzones_mandatory"><span class="toggle-slider"></span></label>
                    </div></div>
                </div>
                <div class="form-row">
                    <div class="form-label"><div class="name">Seek & Destroy Lundi</div></div>
                    <div class="form-control"><div class="toggle-wrap">
                        <span class="toggle-label" id="time_sd_label">ON</span>
                        <label class="toggle"><input type="checkbox" id="time_seek_destroy_monday"><span class="toggle-slider"></span></label>
                    </div></div>
                </div>
            </div>

            <!-- PURE PRICE ACTION -->
            <div class="section">
                <div class="section-title">📉 Pure Price Action</div>
                <div class="form-row">
                    <div class="form-label"><div class="name">MSS Obligatoire</div></div>
                    <div class="form-control"><div class="toggle-wrap">
                        <span class="toggle-label" id="pa_mss_label">ON</span>
                        <label class="toggle"><input type="checkbox" id="pa_mss_mandatory"><span class="toggle-slider"></span></label>
                    </div></div>
                </div>
                <div class="form-row">
                    <div class="form-label"><div class="name">FVG Obligatoire</div></div>
                    <div class="form-control"><div class="toggle-wrap">
                        <span class="toggle-label" id="pa_fvg_label">ON</span>
                        <label class="toggle"><input type="checkbox" id="pa_fvg_mandatory"><span class="toggle-slider"></span></label>
                    </div></div>
                </div>
            </div>

            <!-- SIZING -->
            <div class="section">
                <div class="section-title">📏 Sizing (Profil & Risque)</div>
                <div class="form-row">
                    <div class="form-label">
                        <div class="name">Risque % par trade</div>
                    </div>
                    <div class="form-control">
                        <input type="number" id="size_risk_pct" min="0.1" max="10" step="0.1">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-label"><div class="name">SOD Sizing Actif</div></div>
                    <div class="form-control"><div class="toggle-wrap">
                        <span class="toggle-label" id="size_sod_label">ON</span>
                        <label class="toggle"><input type="checkbox" id="size_sod_active"><span class="toggle-slider"></span></label>
                    </div></div>
                </div>
            </div>
"""

text = text.replace('            <!-- RISQUE -->', html_to_insert + '\n            <!-- RISQUE -->')

# 2. Insert JS to load values
js_load_insert = """
                // Profiles Settings
                const ps = d.profiles_settings || {};
                document.getElementById('score_min_exec').value = ps.score_min_exec;
                document.getElementById('score_min_half').value = ps.score_min_half;
                
                setToggle('gate_rr_active', ps.gate_rr_active, 'gate_rr_label', ['ON', 'OFF']);
                document.getElementById('gate_rr_value').value = ps.gate_rr_value;
                setToggle('gate_ob_active', ps.gate_ob_active, 'gate_ob_label', ['ON', 'OFF']);
                document.getElementById('gate_ob_value').value = ps.gate_ob_value;
                setToggle('gate_spread_ks4_active', ps.gate_spread_ks4_active, 'gate_spread_label', ['ON', 'OFF']);
                document.getElementById('gate_spread_ks4_value').value = ps.gate_spread_ks4_value;
                setToggle('gate_sl_min_active', ps.gate_sl_min_active, 'gate_sl_min_label', ['ON', 'OFF']);
                document.getElementById('gate_sl_min_value').value = ps.gate_sl_min_value;
                
                setToggle('gate_t20_malus_active', ps.gate_t20_malus_active, 'gate_t20_label', ['ON', 'OFF']);
                setToggle('gate_enigma_mandatory_active', ps.gate_enigma_mandatory_active, 'gate_enigma_label', ['ON', 'OFF']);
                setToggle('gate_sod_active', ps.gate_sod_active, 'gate_sod_label', ['ON', 'OFF']);
                
                setToggle('gate_htf_strict_active', ps.gate_htf_strict_active, 'gate_htf_strict_label', ['ON', 'OFF']);
                document.getElementById('gate_htf_strict_mode').value = ps.gate_htf_strict_mode;
                
                setToggle('time_killzones_mandatory', ps.time_killzones_mandatory, 'time_kz_label', ['ON', 'OFF']);
                setToggle('time_seek_destroy_monday', ps.time_seek_destroy_monday, 'time_sd_label', ['ON', 'OFF']);
                
                setToggle('pa_mss_mandatory', ps.pa_mss_mandatory, 'pa_mss_label', ['ON', 'OFF']);
                setToggle('pa_fvg_mandatory', ps.pa_fvg_mandatory, 'pa_fvg_label', ['ON', 'OFF']);
                
                document.getElementById('size_risk_pct').value = ps.size_risk_pct;
                setToggle('size_sod_active', ps.size_sod_active, 'size_sod_label', ['ON', 'OFF']);
"""
text = text.replace("                // Telegram", js_load_insert + "\n                // Telegram")

# 3. Insert JS to save values
js_save_insert = """
                profiles_settings: {
                    score_min_exec: parseInt(document.getElementById('score_min_exec').value || 65),
                    score_min_half: parseInt(document.getElementById('score_min_half').value || 65),
                    telegram_threshold: parseInt(document.getElementById('TELEGRAM_MIN_SCORE').value || 70),
                    gate_rr_active: document.getElementById('gate_rr_active').checked,
                    gate_rr_value: parseFloat(document.getElementById('gate_rr_value').value || 2.0),
                    gate_ob_active: document.getElementById('gate_ob_active').checked,
                    gate_ob_value: parseInt(document.getElementById('gate_ob_value').value || 3),
                    gate_spread_ks4_active: document.getElementById('gate_spread_ks4_active').checked,
                    gate_spread_ks4_value: parseFloat(document.getElementById('gate_spread_ks4_value').value || 3.0),
                    gate_sl_min_active: document.getElementById('gate_sl_min_active').checked,
                    gate_sl_min_value: parseFloat(document.getElementById('gate_sl_min_value').value || 3),
                    gate_t20_malus_active: document.getElementById('gate_t20_malus_active').checked,
                    gate_enigma_mandatory_active: document.getElementById('gate_enigma_mandatory_active').checked,
                    gate_sod_active: document.getElementById('gate_sod_active').checked,
                    gate_htf_strict_active: document.getElementById('gate_htf_strict_active').checked,
                    gate_htf_strict_mode: document.getElementById('gate_htf_strict_mode').value,
                    time_killzones_mandatory: document.getElementById('time_killzones_mandatory').checked,
                    time_seek_destroy_monday: document.getElementById('time_seek_destroy_monday').checked,
                    pa_mss_mandatory: document.getElementById('pa_mss_mandatory').checked,
                    pa_fvg_mandatory: document.getElementById('pa_fvg_mandatory').checked,
                    size_risk_pct: parseFloat(document.getElementById('size_risk_pct').value || 1.0),
                    size_sod_active: document.getElementById('size_sod_active').checked,
                },
"""
text = text.replace("                TELEGRAM_CHAT_ID: document.getElementById('TELEGRAM_CHAT_ID').value,", "                TELEGRAM_CHAT_ID: document.getElementById('TELEGRAM_CHAT_ID').value,\n" + js_save_insert)

with open("dashboard/templates/settings.html", "w") as f:
    f.write(text)

