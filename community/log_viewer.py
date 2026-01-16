def get_plugin_metadata(panel):
    id = "org.waypanel.plugin.log_dashboard"
    default_container = "right-panel-center"
    container, id = panel.config_handler.get_plugin_container(default_container, id)
    return {
        "id": id,
        "name": "HIG Log Dashboard",
        "version": "5.3.0",
        "enabled": True,
        "hidden": False,
        "container": container,
        "index": 10,
    }


def get_plugin_class():
    import re
    import os
    import html
    import json
    import subprocess
    import sys
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("WebKit", "6.0")
    from gi.repository import Gtk, WebKit
    from src.plugins.core._base import BasePlugin

    try:
        import markdown
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "markdown"])
        import markdown

    class LogDashboardPlugin(BasePlugin):
        """
        Plugin managing a standalone log viewer window with non-blocking lifecycle.
        """

        def __init__(self, panel_instance):
            super().__init__(panel_instance)
            self.window = None
            self.web_view = None
            self.toggle_button = None
            self._filters_disabled = False
            self._config_dir = os.path.expanduser(
                "~/.local/share/waypanel/plugins/log_dashboard"
            )
            self._config_file = os.path.join(self._config_dir, "config.json")
            os.makedirs(self._config_dir, exist_ok=True)
            self._log_path = os.path.expanduser("~/.config/waypanel/waypanel.log")
            self._ignore_list = []
            self._theme_mode = "light"
            self._sync_config()

        def on_start(self):
            """
            Initializes the panel button trigger.
            """
            self.toggle_button = Gtk.Button(icon_name="utilities-log-viewer")
            self.toggle_button.connect("clicked", self._on_toggle_clicked)
            self.main_widget = (self.toggle_button, "append")

        def _on_toggle_clicked(self, button):
            """
            Creates or presents the log viewer window.
            """
            if self.window is None:
                self._create_window()
            self._update_log_view()
            self.window.present()

        def _create_window(self):
            """
            Constructs a stable Gtk.Window for the dashboard.
            """
            self.window = Gtk.Window(title="Log Dashboard")
            self.window.set_default_size(950, 800)
            if self.toggle_button.get_root():
                self.window.set_transient_for(self.toggle_button.get_root())
            self.window.connect("close-request", self._on_close_request)
            layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            layout.set_margin_end(12)
            config_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self.path_entry = Gtk.Entry(text=self._log_path, hexpand=True)
            browse_btn = Gtk.Button(icon_name="folder-open-symbolic")
            browse_btn.connect("clicked", self._on_browse_clicked)
            save_btn = Gtk.Button(label="Set Path")
            save_btn.connect("clicked", self._on_save_path_request)
            refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
            refresh_btn.connect("clicked", lambda _: self._update_log_view())
            config_box.append(self.path_entry)
            config_box.append(browse_btn)
            config_box.append(save_btn)
            config_box.append(refresh_btn)
            layout.append(config_box)
            ignore_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self.ignore_entry = Gtk.Entry(
                placeholder_text="Ignore string...", hexpand=True
            )
            add_ignore_btn = Gtk.Button(label="Add")
            add_ignore_btn.connect("clicked", self._on_add_ignore)
            self.filter_toggle_btn = Gtk.Button(label="Disable Filters")
            self.filter_toggle_btn.connect("clicked", self._on_toggle_filters)
            ignore_box.append(self.ignore_entry)
            ignore_box.append(add_ignore_btn)
            ignore_box.append(self.filter_toggle_btn)
            layout.append(ignore_box)
            scroll = Gtk.ScrolledWindow(vexpand=True)
            self.web_view = WebKit.WebView()
            manager = self.web_view.get_user_content_manager()
            manager.register_script_message_handler("themeHandler")
            manager.connect(
                "script-message-received::themeHandler", self._on_theme_message_received
            )
            scroll.set_child(self.web_view)
            layout.append(scroll)
            self.window.set_child(layout)

        def _on_close_request(self, window):
            """
            Properly destroy window and clear reference to avoid hanging.
            """
            self.window.destroy()
            self.window = None
            self._filters_disabled = False
            return True

        def _on_browse_clicked(self, button):
            """
            Opens file picker safely.
            """
            dialog = Gtk.FileDialog(title="Select Log File")

            def on_file_picked(dialog, result):
                try:
                    file = dialog.open_finish(result)
                    if file:
                        path = file.get_path()
                        self.path_entry.set_text(path)
                        self._log_path = path
                        self._save_config()
                        self._update_log_view()
                except Exception:
                    pass

            dialog.open(self.window, None, on_file_picked)

        def _on_theme_message_received(self, manager, message):
            self._theme_mode = message.get_body().get_string()
            self._save_config()

        def _on_toggle_filters(self, button):
            self._filters_disabled = not self._filters_disabled
            button.set_label(
                "Enable Filters" if self._filters_disabled else "Disable Filters"
            )
            self._update_log_view()

        def _update_log_view(self):
            if not self.window or not os.path.exists(self._log_path):
                return
            md_content = self._parse_logs()
            html_body = markdown.markdown(md_content, extensions=["tables"])
            full_html = self._apply_hig_template(html_body)
            self.web_view.load_html(
                full_html, f"file://{os.path.dirname(self._log_path)}/"
            )

        def _parse_logs(self) -> str:
            try:
                with open(self._log_path, "r", encoding="utf-8") as f:
                    raw_lines = [l.strip() for l in f if l.strip()]
            except:
                return "Error reading file"
            lines = (
                raw_lines
                if self._filters_disabled
                else [
                    l
                    for l in raw_lines
                    if not any(ign in l for ign in self._ignore_list)
                ]
            )
            rows = []
            for line in lines:
                match = re.search(r"(?:^|\[)(\w{2,5})(?:\]|\s)", line)
                lvl = match.group(1).upper() if match else "LOG"
                rows.append(
                    f'<tr class="log-row"><td><input type="checkbox" class="log-check"></td><td>{lvl}</td><td class="log-msg-cell">{self._colorize(line)}</td></tr>'
                )
            return f'<table id="main-table"><thead><tr><th><input type="checkbox" onclick="toggleAll(this)"></th><th>Lvl</th><th>Message</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'

        def _colorize(self, line: str) -> str:
            line = html.escape(line)
            match = re.match(r"^(\w+)\s+([\d\-\s:\.]+)\s+-\s+(\[.*?\])?(.*)$", line)
            if not match:
                return f'<span class="dim">{line}</span>'
            lvl, ts, ctx, msg = match.groups()
            ctx_h = f"<span class='ctx'>[{ctx}]</span>" if ctx else ""
            return f'<span class="lvl-{lvl.lower()}">{lvl}</span> <span class="ts">{ts}</span> {ctx_h} <span class="msg">{msg.strip()}</span>'

        def _apply_hig_template(self, content: str) -> str:
            dark_class = 'class="dark-mode"' if self._theme_mode == "dark" else ""
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    :root {{
                        --bg: lch(98% 0 0); --card: lch(92% 1 260); --text: lch(10% 0 0);
                        --accent: lch(50% 60 260); --red: lch(50% 70 25); --border: lch(85% 1 260);
                    }}
                    body.dark-mode {{
                        --bg: lch(5% 0 0); --card: lch(12% 2 260); --text: lch(95% 0 0);
                        --accent: lch(60% 55 260); --red: lch(55% 70 25); --border: lch(18% 1 260);
                    }}
                    body {{ background: var(--bg); color: var(--text); font-family: sans-serif; padding: 0; margin: 0; transition: background 0.2s; }}
                    .toolbar {{
                        display: flex; gap: 8px; padding: 12px 15px; position: sticky; top: 0;
                        background: var(--bg); z-index: 100; border-bottom: 2px solid var(--border);
                    }}
                    .btn {{ background: var(--card); color: var(--text); border: 1px solid var(--border); padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; }}
                    td, th {{ padding: 10px 15px; border-bottom: 1px solid var(--border); font-family: monospace; font-size: 11px; text-align: left; }}
                    th {{ background: var(--card); position: sticky; top: 54px; z-index: 90; }}
                    .ts {{ color: lch(40% 40 145); opacity: 0.8; }}
                    body.dark-mode .ts {{ color: lch(80% 40 145); }}
                </style>
            </head>
            <body {dark_class}>
                <div class="toolbar">
                    <input type="text" id="search" placeholder="Search..." onkeyup="filterLogs()" autofocus>
                    <button class="btn" onclick="toggleTheme()">🌓</button>
                    <button class="btn" onclick="window.scrollTo(0,0)">Start</button>
                    <button class="btn" onclick="window.scrollTo(0,document.body.scrollHeight)">End</button>
                    <button class="btn" onclick="copySelected()">Copy</button>
                </div>
                <div style="padding: 0 15px;">{content}</div>
                <script>
                    function toggleTheme() {{
                        document.body.classList.toggle('dark-mode');
                        window.webkit.messageHandlers.themeHandler.postMessage(document.body.classList.contains('dark-mode') ? "dark" : "light");
                    }}
                    function filterLogs() {{
                        let val = document.getElementById('search').value.toLowerCase();
                        document.querySelectorAll('.log-row').forEach(r => r.style.display = r.innerText.toLowerCase().includes(val) ? '' : 'none');
                    }}
                    function toggleAll(m) {{ document.querySelectorAll('.log-check').forEach(c => c.checked = m.checked); }}
                    async function copySelected() {{
                        let s = []; document.querySelectorAll('.log-check:checked').forEach(c => s.push(c.closest('tr').querySelector('.log-msg-cell').innerText));
                        if(s.length) await navigator.clipboard.writeText(s.join('\\n'));
                    }}
                </script>
            </body>
            </html>
            """

        def _on_save_path_request(self, _):
            self._log_path = self.path_entry.get_text().strip()
            self._save_config()
            self._update_log_view()

        def _on_add_ignore(self, _):
            t = self.ignore_entry.get_text().strip()
            if t and t not in self._ignore_list:
                self._ignore_list.append(t)
                self._save_config()
                self._update_log_view()

        def _sync_config(self):
            if os.path.exists(self._config_file):
                try:
                    with open(self._config_file, "r") as f:
                        d = json.load(f)
                        self._log_path = d.get("log_path", self._log_path)
                        self._ignore_list = d.get("ignore_list", [])
                        self._theme_mode = d.get("theme_mode", "light")
                except:
                    pass

        def _save_config(self):
            with open(self._config_file, "w") as f:
                json.dump(
                    {
                        "log_path": self._log_path,
                        "ignore_list": self._ignore_list,
                        "theme_mode": self._theme_mode,
                    },
                    f,
                )

        def on_stop(self):
            if self.window:
                self.window.destroy()
            if self.toggle_button:
                self.remove_widget(self.toggle_button)

    return LogDashboardPlugin
