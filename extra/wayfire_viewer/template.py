import re


def get_html(options_data, active_plugins_raw, icon_resolver):
    """Generates the full HTML5/CSS/JS string for the WebKit view."""

    active_set = set(
        active_plugins_raw.split()
        if isinstance(active_plugins_raw, str)
        else active_plugins_raw
    )

    toggleable_plugins = {
        "alpha",
        "core",
        "fisheye",
        "input",
        "preserve-output",
        "show-cursor",
        "window-rules",
        "ammen99-bench",
        "crt-effect-vk",
        "follow-cursor-bindings",
        "invert",
        "primary-monitor-switch",
        "simple-tile",
        "wm-actions",
        "ammen99-debugging",
        "crt-effect",
        "foreign-toplevel",
        "ipc-rules",
        "resize",
        "switcher",
        "wobbly",
        "animate",
        "cube",
        "grid",
        "ipc",
        "scale-title-filter",
        "switch-kb-layouts",
        "workarounds",
        "autostart",
        "decoration",
        "gtk-shell",
        "move",
        "scale",
        "tablet-mode",
        "wrot",
        "blur-to-background",
        "expo",
        "idle",
        "oswitch",
        "security-context-v1",
        "vswipe",
        "wsets",
        "blur",
        "extra-gestures",
        "input-device",
        "output",
        "session-lock",
        "vswitch",
        "xdg-activation",
        "command",
        "fast-switcher",
        "input-method-v1",
        "place",
        "shortcuts-inhibit",
        "wayfire-shell",
        "zoom",
        "inertial-view-vk",
        "ipc-extra",
        "simple-text",
        "workspace-names",
    }

    css = """
    :root {
        --bg: lch(8% 1 260);
        --card: lch(12% 2 260);
        --text: lch(98% 0 0);
        --accent: lch(70% 40 270);
        --border: lch(20% 4 260);
        --input: lch(4% 0 0);
    }
    body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; }
    .header { position: sticky; top: 0; background: var(--bg); padding: 25px; z-index: 10; border-bottom: 1px solid var(--border); }
    .search { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--input); color: white; outline: none; }
    .container { max-width: 900px; margin: 0 auto; padding: 20px; }
    .block { background: var(--card); border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid var(--border); }
    .p-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; color: var(--accent); }
    .p-info { display: flex; align-items: center; gap: 10px; font-weight: bold; }
    .row { display: flex; align-items: flex-start; gap: 15px; padding: 12px 0; border-bottom: 1px solid lch(15% 1 260); }
    .label { flex: 1; font-family: monospace; font-size: 0.85rem; opacity: 0.7; padding-top: 8px; }
    .widget { width: 450px; display: flex; justify-content: flex-end; }
    input[type="text"], input[type="number"], textarea { width: 100%; padding: 8px; background: var(--input); border: 1px solid var(--border); color: white; border-radius: 4px; font-family: inherit; }
    textarea { height: 100px; resize: vertical; font-family: monospace; font-size: 0.8rem; }
    .switch { position: relative; width: 36px; height: 18px; flex-shrink: 0; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: var(--border); border-radius: 18px; transition: .2s; }
    .slider:before { position: absolute; content: ""; height: 12px; width: 12px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: .2s; }
    input:checked + .slider { background: var(--accent); }
    input:checked + .slider:before { transform: translateX(18px); }
    .hidden { display: none !important; }
    """

    js = """
    function sync(path, val, type) {
        let finalVal = val;
        if (type === 'list') {
            try {
                finalVal = JSON.parse(val.replace(/'/g, '"'));
            } catch (e) {
                console.error("Failed to parse list binding", e);
                return;
            }
        }
        window.webkit.messageHandlers.wayfire.postMessage({ msg_type: 'update', path, value: finalVal, type });
    }
    function toggle(plugin, state) {
        window.webkit.messageHandlers.wayfire.postMessage({ msg_type: 'toggle_plugin', plugin, state });
    }
    function doSearch(q) {
        q = q.toLowerCase();
        document.querySelectorAll('.block').forEach(b => {
            const name = b.dataset.name.toLowerCase();
            let hasMatch = name.includes(q);
            b.querySelectorAll('.row').forEach(r => {
                const k = r.dataset.key.toLowerCase();
                if (hasMatch || k.includes(q)) { r.classList.remove('hidden'); hasMatch = true; }
                else { r.classList.add('hidden'); }
            });
            b.classList.toggle('hidden', !hasMatch);
        });
    }
    """

    html = f"<html><head><meta charset='utf-8'><style>{css}</style><script>{js}</script></head><body>"
    html += '<div class="header"><input class="search" placeholder="Search config..." oninput="doSearch(this.value)"></div>'
    html += '<div class="container">'

    for plugin, opts in sorted(options_data.items()):
        if not opts and plugin != "core":
            continue

        is_on = "checked" if plugin in active_set else ""
        html += f'<div class="block" data-name="{plugin}">'
        html += f'<div class="p-head"><div class="p-info">{icon_resolver(plugin)}<span>{plugin}</span></div>'
        if plugin in toggleable_plugins:
            html += f'<label class="switch"><input type="checkbox" {is_on} onchange="toggle(\'{plugin}\', this.checked)"><span class="slider"></span></label>'
        html += "</div>"

        for key, meta in sorted((opts or {}).items()):
            path, val = f"{plugin}/{key}", meta.get("value", "")
            widget = ""

            # Specific handling for the 'bindings' or list types (like command/bindings)
            if isinstance(val, list):
                # Format the list nicely for the textarea
                list_str = str(val)
                widget = f"<textarea oninput=\"sync('{path}', this.value, 'list')\">{list_str}</textarea>"
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
