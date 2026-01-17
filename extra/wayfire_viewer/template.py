import re
import os


def get_html(options_data, active_plugins_raw, icon_resolver, raw_config=None):
    """Generates the full HTML5/CSS/JS string for the WebKit view."""
    if not isinstance(options_data, dict):
        options_data = {}
    if raw_config is None:
        raw_config = {}

    active_set = set(
        active_plugins_raw.split()
        if isinstance(active_plugins_raw, str)
        else (active_plugins_raw or [])
    )

    local_plugin_path = os.getenv(
        "WAYFIRE_PLUGIN_PATH", os.path.expanduser("~/.local/lib/wayfire")
    )
    local_metadata_path = os.path.join(
        os.path.dirname(os.path.dirname(local_plugin_path)), "share/wayfire/metadata"
    )

    metadata_paths = [
        "/usr/share/wayfire/metadata/",
        local_metadata_path,
        os.path.expanduser("~/.local/share/wayfire/metadata/"),
    ]

    toggleable_plugins = set()
    for path in metadata_paths:
        if os.path.exists(path):
            for f in os.listdir(path):
                if f.endswith(".xml"):
                    toggleable_plugins.add(f.replace(".xml", ""))

    css = """
    :root {
        --bg: lch(8% 1 260);
        --card: lch(12% 2 260);
        --text: lch(98% 0 0);
        --accent: lch(70% 40 270);
        --border: lch(20% 4 260);
        --input: lch(4% 0 0);
        --suggest-bg: lch(15% 5 260);
        --danger: lch(50% 50 20);
    }
    body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding-bottom: 50px; }
    .header { position: sticky; top: 0; background: var(--bg); padding: 25px; z-index: 10; border-bottom: 1px solid var(--border); }
    .search { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--input); color: white; outline: none; }
    .container { max-width: 900px; margin: 0 auto; padding: 20px; }
    .block { background: var(--card); border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid var(--border); }
    .p-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; color: var(--accent); }
    .p-info { display: flex; align-items: center; gap: 10px; font-weight: bold; }
    .p-actions { display: flex; align-items: center; gap: 15px; }
    .row { display: flex; align-items: flex-start; gap: 15px; padding: 12px 0; border-bottom: 1px solid lch(15% 1 260); }
    .label { flex: 1; font-family: monospace; font-size: 0.85rem; opacity: 0.7; padding-top: 8px; }
    .widget { width: 450px; display: flex; flex-direction: column; align-items: flex-end; position: relative; }
    .input-wrapper { width: 100%; display: flex; gap: 8px; align-items: center; position: relative; }
    input[type="text"], input[type="number"], textarea { 
        width: 100%; padding: 8px; background: var(--input); border: 1px solid var(--border); 
        color: white; border-radius: 4px; font-family: inherit; box-sizing: border-box; 
    }
    textarea:placeholder-shown, input:placeholder-shown { border: 1px dashed var(--danger); }
    textarea.manual-edit { height: 100px; resize: vertical; font-family: monospace; font-size: 0.8rem; }
    .suggestions {
        position: absolute; top: 100%; left: 0; right: 0; background: var(--suggest-bg);
        border: 1px solid var(--border); border-radius: 0 0 4px 4px; z-index: 100;
        max-height: 250px; overflow-y: auto; display: none; box-shadow: 0 8px 16px rgba(0,0,0,0.6);
    }
    .suggestion-item { padding: 8px 12px; cursor: pointer; font-family: monospace; font-size: 0.85rem; border-bottom: 1px solid var(--border); color: #ccc; }
    .suggestion-item:hover, .suggestion-item.active { background: var(--accent); color: white; }
    .reset-btn, .add-btn, .del-btn, .browse-btn { background: none; border: none; color: var(--accent); cursor: pointer; font-size: 1.1rem; padding: 5px; opacity: 0.6; }
    .del-btn { color: var(--danger); }
    .reset-btn:hover, .add-btn:hover, .del-btn:hover, .browse-btn:hover { opacity: 1; }
    .switch { position: relative; width: 36px; height: 18px; flex-shrink: 0; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: var(--border); border-radius: 18px; transition: .2s; }
    .slider:before { position: absolute; content: ""; height: 12px; width: 12px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: .2s; }
    input:checked + .slider { background: var(--accent); }
    input:checked + .slider:before { transform: translateX(18px); }
    .hidden { display: none !important; }
    """

    js = """
    let timers = {};

    function debouncedSync(path, val, type, delay = 500) {
        if (timers[path]) clearTimeout(timers[path]);
        timers[path] = setTimeout(() => {
            sync(path, val, type);
            delete timers[path];
        }, delay);
    }

    function syncManual(section, key, val) {
        const path = section + '_' + key;
        if (timers[path]) clearTimeout(timers[path]);
        timers[path] = setTimeout(() => {
            window.webkit.messageHandlers.wayfire.postMessage({ msg_type: 'manual_update', section, key, value: val });
            delete timers[path];
        }, 500);
    }

    function updateFilePath(targetId, path) {
        const el = document.getElementById(targetId);
        if (!el) return;
        el.value = path;
        el.dispatchEvent(new Event('input'));
    }

    function pickFile(targetId) {
        window.webkit.messageHandlers.wayfire.postMessage({ msg_type: 'pick_file', target_id: targetId });
    }

    function addManualRow(section) {
        const key = prompt("Enter key name:");
        if (!key) return;
        const block = document.querySelector(`.block[data-name="${section}"]`);
        const row = document.createElement('div');
        row.className = 'row';
        row.dataset.key = key;
        const targetId = `input_${section}_${key}`.replace(/[^a-zA-Z0-9]/g, '_');
        row.innerHTML = `
            <div class="label">${key}</div>
            <div class="widget">
                <div class="input-wrapper">
                    <textarea id="${targetId}" class="manual-edit" placeholder="Value required..." oninput="syncManual('${section}', '${key}', this.value)"></textarea>
                    <button class="browse-btn" onclick="pickFile('${targetId}')">📂</button>
                    <button class="del-btn" onclick="deleteManualRow('${section}', '${key}', this.closest('.row'))">🗑</button>
                </div>
            </div>
        `;
        block.appendChild(row);
    }

    function deleteManualRow(section, key, element) {
        if (!confirm(`Delete ${key}?`)) return;
        window.webkit.messageHandlers.wayfire.postMessage({ msg_type: 'manual_delete', section, key });
        element.remove();
    }

    function resetSection(pluginName) {
        const block = document.querySelector(`.block[data-name="${pluginName}"]`);
        const rows = block.querySelectorAll('.row');
        const updates = {};
        rows.forEach(row => {
            const path = row.dataset.path;
            const defVal = row.dataset.default;
            const input = row.querySelector('input, textarea');
            if (input) {
                if (input.type === 'checkbox') input.checked = (defVal === 'true');
                else input.value = defVal;
            }
            updates[path] = defVal;
        });
        window.webkit.messageHandlers.wayfire.postMessage({ msg_type: 'section_reset', plugin: pluginName, updates: updates });
    }

    function resetToDefault(path, defaultValue, type) {
        const row = document.querySelector(`[data-path="${path}"]`);
        if (!row) return;
        const input = row.querySelector('input, textarea');
        if (input) {
            if (input.type === 'checkbox') input.checked = (defaultValue === 'true');
            else input.value = defaultValue;
        }
        sync(path, defaultValue, type);
    }

    function sync(path, val, type) {
        if (typeof val === 'string' && val.trim() === '' && type !== 'string') {
            const row = document.querySelector(`[data-path="${path}"]`);
            if (row) resetToDefault(path, row.dataset.default, type);
            return;
        }
        let finalVal = val;
        if (type === 'list' && typeof val === 'string') {
            try { finalVal = JSON.parse(val.replace(/'/g, '"')); } catch (e) { return; }
        }
        window.webkit.messageHandlers.wayfire.postMessage({ msg_type: 'update', path, value: finalVal, type });
    }

    function toggle(plugin, state) {
        window.webkit.messageHandlers.wayfire.postMessage({ msg_type: 'toggle_plugin', plugin, state });
    }

    function handleSuggest(input, path, e) {
        const suggestDiv = input.nextElementSibling;
        const val = input.value;
        const words = val.split(/\\s+/);
        const lastWord = words[words.length - 1].toLowerCase();
        const MODS = ["<alt>", "<ctrl>", "<shift>", "<super>"];
        const KEYS = ["KEY_A", "KEY_B", "KEY_ENTER", "KEY_ESC", "KEY_SPACE", "BTN_LEFT", "BTN_RIGHT"];
        
        if (e && (e.key === "Tab" || e.key === "Enter") && suggestDiv.style.display === 'block') {
            e.preventDefault();
            const item = suggestDiv.querySelector('.active') || suggestDiv.firstChild;
            if (item) item.onmousedown(e);
            return;
        }
        const matches = [...MODS, ...KEYS].filter(s => s.toLowerCase().includes(lastWord) && !words.includes(s));
        if (matches.length === 0 || (val.endsWith(' ') && !lastWord)) {
            suggestDiv.style.display = 'none'; return;
        }
        suggestDiv.innerHTML = ''; suggestDiv.style.display = 'block';
        matches.forEach((m, idx) => {
            const item = document.createElement('div');
            item.className = 'suggestion-item' + (idx === 0 ? ' active' : '');
            item.textContent = m;
            item.onmousedown = (event) => {
                event.preventDefault();
                words[words.length - 1] = m;
                input.value = words.join(' ') + ' ';
                suggestDiv.style.display = 'none';
                sync(path, input.value.trim(), 'string');
                input.focus();
            };
            suggestDiv.appendChild(item);
        });
    }

    function doSearch(q) {
        q = q.toLowerCase();
        document.querySelectorAll('.block').forEach(b => {
            const name = b.dataset.name.toLowerCase();
            let bMatch = name.includes(q);
            let hasVisibleRow = false;
            b.querySelectorAll('.row').forEach(r => {
                const k = r.dataset.key ? r.dataset.key.toLowerCase() : r.dataset.path.toLowerCase();
                if (bMatch || k.includes(q)) {
                    r.classList.remove('hidden');
                    hasVisibleRow = true;
                } else {
                    r.classList.add('hidden');
                }
            });
            b.classList.toggle('hidden', !hasVisibleRow && !bMatch);
        });
    }
    """

    html = f"<html><head><meta charset='utf-8'><style>{css}</style><script>{js}</script></head><body>"
    html += '<div class="header"><input class="search" placeholder="Search config..." oninput="doSearch(this.value)"></div>'
    html += '<div class="container">'

    manual_sections = {"window-rules", "command", "autostart"}
    all_sections = sorted(set(options_data.keys()) | manual_sections)

    for plugin in all_sections:
        is_manual = plugin in manual_sections
        opts = options_data.get(plugin, {})

        if not is_manual and (
            not isinstance(opts, dict) or (not opts and plugin != "core")
        ):
            continue

        html += f'<div class="block" data-name="{plugin}">'
        html += f'<div class="p-head"><div class="p-info">{icon_resolver(plugin)}<span>{plugin}</span></div>'
        html += '<div class="p-actions">'

        if is_manual:
            html += f'<button class="add-btn" onclick="addManualRow(\'{plugin}\')" title="Add New Row">+</button>'
        else:
            html += f'<button class="reset-btn" onclick="resetSection(\'{plugin}\')" title="Reset Section Defaults">↺ Section</button>'
            if plugin in toggleable_plugins:
                is_on = "checked" if plugin in active_set else ""
                html += f'<label class="switch"><input type="checkbox" {is_on} onchange="toggle(\'{plugin}\', this.checked)"><span class="slider"></span></label>'

        html += "</div></div>"

        if is_manual:
            section_data = raw_config.get(plugin, {})
            for key, val in section_data.items():
                low_key, target_id = (
                    key.lower(),
                    f"input_{plugin}_{key}".replace("-", "_"),
                )
                if isinstance(val, bool):
                    chk = "checked" if val else ""
                    widget = f'<label class="switch"><input type="checkbox" {chk} onchange="syncManual(\'{plugin}\', \'{key}\', this.checked)"><span class="slider"></span></label>'
                elif any(x in low_key for x in ["path", "file", "dir", "image"]):
                    widget = f'<div class="input-wrapper"><textarea id="{target_id}" class="manual-edit" placeholder="Value required..." oninput="syncManual(\'{plugin}\', \'{key}\', this.value)">{val}</textarea><button class="browse-btn" onclick="pickFile(\'{target_id}\')">📂</button></div>'
                else:
                    widget = f'<textarea class="manual-edit" placeholder="Value required..." oninput="syncManual(\'{plugin}\', \'{key}\', this.value)">{val}</textarea>'

                html += f'''
                <div class="row" data-key="{key}">
                    <div class="label">{key}</div>
                    <div class="widget">
                        <div class="input-wrapper">
                            {widget}
                            <button class="del-btn" onclick="deleteManualRow('{plugin}', '{key}', this.closest('.row'))">🗑</button>
                        </div>
                    </div>
                </div>'''
        else:
            for key, meta in sorted(opts.items()):
                if not isinstance(meta, dict):
                    continue
                path, val, default = (
                    f"{plugin}/{key}",
                    meta.get("value", ""),
                    meta.get("default", ""),
                )
                low_key = key.lower()
                if isinstance(val, dict):
                    val = val.get("value", "")
                if isinstance(default, dict):
                    default = default.get("value", "")
                vtype, js_default = "string", str(default).replace("'", "\\'")

                if isinstance(val, bool) or str(val).lower() in ["true", "false"]:
                    vtype, chk = "bool", "checked" if str(val).lower() == "true" else ""
                    widget = f'<label class="switch"><input type="checkbox" {chk} onchange="sync(\'{path}\', this.checked, \'bool\')"><span class="slider"></span></label>'
                elif any(x in low_key for x in ["path", "file", "dir"]):
                    target_id = path.replace("/", "_")
                    widget = f'<div class="input-wrapper"><input type="text" id="{target_id}" value="{val}" oninput="sync(\'{path}\', this.value, \'string\')"><button class="browse-btn" onclick="pickFile(\'{target_id}\')">📂</button></div>'
                elif "default" in meta and isinstance(meta.get("value"), str):
                    widget = f'<input type="text" class="search-activator" value="{val}" oninput="handleSuggest(this, \'{path}\', event); debouncedSync(\'{path}\', this.value, \'string\')" onkeydown="handleSuggest(this, \'{path}\', event)" autocomplete="off"><div class="suggestions"></div>'
                elif isinstance(val, list):
                    vtype, widget = (
                        "list",
                        f"<textarea oninput=\"debouncedSync('{path}', this.value, 'list')\">{str(val)}</textarea>",
                    )
                elif isinstance(val, str) and re.match(r"^#[0-9A-Fa-f]{8}$", val):
                    vtype, widget = (
                        "color",
                        f"<input type=\"color\" value=\"{val[:7]}\" onchange=\"sync('{path}', this.value+'FF', 'color')\">",
                    )
                elif isinstance(val, (int, float)) or (
                    isinstance(val, str)
                    and val.replace(".", "", 1).replace("-", "", 1).isdigit()
                ):
                    vtype, widget = (
                        "number",
                        f'<input type="number" step="any" value="{val}" oninput="debouncedSync(\'{path}\', this.value, \'number\')">',
                    )
                else:
                    widget = f'<input type="text" value="{val}" oninput="debouncedSync(\'{path}\', this.value, \'string\')">'

                html += f'<div class="row" data-path="{path}" data-default="{js_default}" data-key="{key}"><div class="label">{key}</div><div class="widget"><div class="input-wrapper">{widget}<button class="reset-btn" onclick="resetToDefault(\'{path}\', \'{js_default}\', \'{vtype}\')">↺</button></div></div></div>'

        html += "</div>"

    return html + "</div></body></html>"
