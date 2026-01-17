import re
import os


def get_html(options_data, active_plugins_raw, icon_resolver):
    """Generates the full HTML5/CSS/JS string for the WebKit view."""

    if not isinstance(options_data, dict):
        options_data = {}

    active_set = set(
        active_plugins_raw.split()
        if isinstance(active_plugins_raw, str)
        else (active_plugins_raw or [])
    )

    local_plugin_path = os.getenv(
        "WAYFIRE_PLUGIN_PATH", os.path.expanduser("~/.local/lib/wayfire")
    )
    local_metadata_path = os.path.join(
        os.path.dirname(local_plugin_path), "share/wayfire/metadata"
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
    }
    body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding-bottom: 50px; }
    .header { position: sticky; top: 0; background: var(--bg); padding: 25px; z-index: 10; border-bottom: 1px solid var(--border); }
    .search { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--input); color: white; outline: none; }
    .container { max-width: 900px; margin: 0 auto; padding: 20px; }
    .block { background: var(--card); border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid var(--border); }
    .p-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; color: var(--accent); }
    .p-info { display: flex; align-items: center; gap: 10px; font-weight: bold; }
    .row { display: flex; align-items: flex-start; gap: 15px; padding: 12px 0; border-bottom: 1px solid lch(15% 1 260); }
    .label { flex: 1; font-family: monospace; font-size: 0.85rem; opacity: 0.7; padding-top: 8px; }
    .widget { width: 450px; display: flex; flex-direction: column; align-items: flex-end; position: relative; }
    
    input[type="text"], input[type="number"], textarea { 
        width: 100%; padding: 8px; background: var(--input); border: 1px solid var(--border); 
        color: white; border-radius: 4px; font-family: inherit; box-sizing: border-box; 
    }
    
    .suggestions {
        position: absolute; top: 100%; left: 0; right: 0; background: var(--suggest-bg);
        border: 1px solid var(--border); border-radius: 0 0 4px 4px; z-index: 100;
        max-height: 250px; overflow-y: auto; display: none; box-shadow: 0 8px 16px rgba(0,0,0,0.6);
    }
    .suggestion-item { padding: 8px 12px; cursor: pointer; font-family: monospace; font-size: 0.85rem; border-bottom: 1px solid var(--border); color: #ccc; }
    .suggestion-item:hover, .suggestion-item.active { background: var(--accent); color: white; }

    .switch { position: relative; width: 36px; height: 18px; flex-shrink: 0; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: var(--border); border-radius: 18px; transition: .2s; }
    .slider:before { position: absolute; content: ""; height: 12px; width: 12px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: .2s; }
    input:checked + .slider { background: var(--accent); }
    input:checked + .slider:before { transform: translateX(18px); }
    .hidden { display: none !important; }
    """

    js = """
    const MODS = ["<alt>", "<ctrl>", "<shift>", "<super>"];
    const KEYS = [
        "KEY_A", "KEY_B", "KEY_C", "KEY_D", "KEY_E", "KEY_F", "KEY_G", "KEY_H", "KEY_I", "KEY_J", "KEY_K", "KEY_L", "KEY_M", 
        "KEY_N", "KEY_O", "KEY_P", "KEY_Q", "KEY_R", "KEY_S", "KEY_T", "KEY_U", "KEY_V", "KEY_W", "KEY_X", "KEY_Y", "KEY_Z",
        "KEY_ENTER", "KEY_ESC", "KEY_SPACE", "KEY_BACKSPACE", "KEY_TAB", "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
        "KEY_F1", "KEY_F2", "KEY_F3", "KEY_F4", "KEY_F5", "KEY_F6", "KEY_F7", "KEY_F8", "KEY_F9", "KEY_F10", "KEY_F11", "KEY_F12",
        "KEY_KP0", "KEY_KP1", "KEY_KP2", "KEY_KP3", "KEY_KP4", "KEY_KP5", "KEY_KP6", "KEY_KP7", "KEY_KP8", "KEY_KP9",
        "BTN_LEFT", "BTN_RIGHT", "BTN_MIDDLE", "BTN_SIDE", "BTN_EXTRA"
    ];

    let activeIndex = -1;

    function sync(path, val, type) {
        let finalVal = val;
        if (type === 'list') {
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

        if (e) {
            if (e.key === "Tab" || e.key === "Enter") {
                if (suggestDiv.style.display === 'block') {
                    e.preventDefault();
                    const idx = activeIndex === -1 ? 0 : activeIndex;
                    if (suggestDiv.children[idx]) suggestDiv.children[idx].onmousedown(e);
                    return;
                }
            }
            if (e.key === "ArrowDown") {
                e.preventDefault();
                activeIndex = Math.min(activeIndex + 1, suggestDiv.children.length - 1);
                updateActive(suggestDiv);
                return;
            }
            if (e.key === "ArrowUp") {
                e.preventDefault();
                activeIndex = Math.max(activeIndex - 1, 0);
                updateActive(suggestDiv);
                return;
            }
        }

        // Show all matches (no slice limit)
        const matches = [...MODS, ...KEYS].filter(s => 
            s.toLowerCase().includes(lastWord) && !words.includes(s)
        );

        if (matches.length === 0 || (val.endsWith(' ') && !lastWord)) {
            suggestDiv.style.display = 'none';
            activeIndex = -1;
            return;
        }

        suggestDiv.innerHTML = '';
        suggestDiv.style.display = 'block';
        activeIndex = 0;

        matches.forEach((m, idx) => {
            const item = document.createElement('div');
            item.className = 'suggestion-item' + (idx === 0 ? ' active' : '');
            item.textContent = m;
            item.onmousedown = (event) => {
                if(event) event.preventDefault();
                words[words.length - 1] = m;
                input.value = words.join(' ') + ' ';
                suggestDiv.style.display = 'none';
                sync(path, input.value.trim(), 'string');
                input.focus();
            };
            suggestDiv.appendChild(item);
        });
    }

    function updateActive(div) {
        Array.from(div.children).forEach((child, i) => {
            child.classList.toggle('active', i === activeIndex);
            if (i === activeIndex) child.scrollIntoView({ block: 'nearest' });
        });
    }

    document.addEventListener('click', (e) => {
        if (!e.target.classList.contains('search-activator')) {
            document.querySelectorAll('.suggestions').forEach(s => s.style.display = 'none');
        }
    });

    function doSearch(q) {
        q = q.toLowerCase();
        document.querySelectorAll('.block').forEach(b => {
            const name = b.dataset.name.toLowerCase();
            let bMatch = name.includes(q);
            let hasVisibleRow = false;
            b.querySelectorAll('.row').forEach(r => {
                const k = r.dataset.key.toLowerCase();
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

    for plugin, opts in sorted(options_data.items()):
        if not isinstance(opts, dict) or (not opts and plugin != "core"):
            continue

        is_on = "checked" if plugin in active_set else ""
        html += f'<div class="block" data-name="{plugin}">'
        html += f'<div class="p-head"><div class="p-info">{icon_resolver(plugin)}<span>{plugin}</span></div>'
        if plugin in toggleable_plugins:
            html += f'<label class="switch"><input type="checkbox" {is_on} onchange="toggle(\'{plugin}\', this.checked)"><span class="slider"></span></label>'
        html += "</div>"

        for key, meta in sorted(opts.items()):
            if not isinstance(meta, dict):
                continue
            path = f"{plugin}/{key}"
            raw_val = meta.get("value", "")

            is_activator = (
                isinstance(meta, dict)
                and "value" in meta
                and "default" in meta
                and isinstance(meta["value"], str)
            )
            val = meta["value"] if is_activator else raw_val

            widget = ""
            if is_activator:
                widget = f"""
                <div style="width:100%; position:relative;">
                    <input type="text" class="search-activator" value='{val}' 
                           oninput="handleSuggest(this, '{path}', event); sync('{path}', this.value, 'string')" 
                           onkeydown="handleSuggest(this, '{path}', event)"
                           onfocus="handleSuggest(this, '{path}')"
                           autocomplete="off">
                    <div class="suggestions"></div>
                </div>
                """
            elif isinstance(val, list):
                widget = f"<textarea oninput=\"sync('{path}', this.value, 'list')\">{str(val)}</textarea>"
            elif isinstance(val, str) and re.match(r"^#[0-9A-Fa-f]{8}$", val):
                widget = f"<input type=\"color\" value=\"{val[:7]}\" onchange=\"sync('{path}', this.value+'FF', 'color')\">"
            elif str(val).lower() in ["true", "false"]:
                chk = "checked" if str(val).lower() == "true" else ""
                widget = f"<input type=\"checkbox\" {chk} onchange=\"sync('{path}', this.checked, 'bool')\">"
            elif isinstance(val, (int, float)) or (
                isinstance(val, str)
                and val.replace(".", "", 1).replace("-", "", 1).isdigit()
            ):
                widget = f'<input type="number" step="any" value="{val}" oninput="sync(\'{path}\', this.value, \'number\')">'
            else:
                widget = f"<input type=\"text\" value='{val}' oninput=\"sync('{path}', this.value, 'string')\">"

            html += f'<div class="row" data-key="{key}"><div class="label">{key}</div><div class="widget">{widget}</div></div>'
        html += "</div>"

    return html + "</div></body></html>"
