"""
Unified Game Hub Plugin for Waypanel.
Implements exact user-provided VDF parsing, recursive Steam icons,
and Heroic URI launching with specific icon paths.
"""


def get_plugin_metadata(panel):
    id = "org.waypanel.plugin.steam_heroic_hub"
    default_container = "right-panel-center"
    container, id = panel.config_handler.get_plugin_container(default_container, id)

    return {
        "id": id,
        "name": "Game Launcher",
        "version": "3.6.0",
        "enabled": True,
        "container": container,
        "index": 100,
        "deps": ["top_panel"],
        "description": "Unified launcher for Steam and Heroic games using exact local metadata discovery.",
    }


def get_plugin_class():
    import json
    import re
    from pathlib import Path
    from src.plugins.core._base import BasePlugin

    class GameLauncher(BasePlugin):
        def __init__(self, panel_instance):
            super().__init__(panel_instance)

            # Paths
            self.STEAM_BASES = [
                Path.home() / ".local/share/Steam",
                Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam",
            ]
            self.HEROIC_LEGENDARY_INSTALLED = (
                Path.home() / ".config/heroic/legendaryConfig/legendary/installed.json"
            )
            self.HEROIC_ICONS_DIR = Path.home() / ".config/heroic/icons"

            # Filtering
            self.BLACKLIST = {
                "proton",
                "runtime",
                "works",
                "server",
                "sdk",
                "tool",
                "drive_c",
                "dosdevices",
                "pfx",
            }

            # Settings
            self.popover_width = self.get_plugin_setting_add_hint(
                ["layout", "popover_width"], 560, "Width."
            )
            self.max_cols = self.get_plugin_setting_add_hint(
                ["layout", "columns"], 4, "Columns."
            )

            self.popover = None
            self.flowbox = None
            self.search_entry = None
            self.main_button = None

        def on_start(self):
            """Registers the main widget for the panel."""
            self.main_button = self.gtk.Button.new_from_icon_name("input-gaming")
            self.main_button.connect("clicked", self._on_toggle_launcher)
            self._init_ui()
            self.main_widget = (self.main_button, "append")

        def _init_ui(self):
            """Constructs the GTK4 UI."""
            self.popover = self.create_popover(
                parent_widget=self.main_button, css_class="steam-launcher-popover"
            )

            container = self.gtk.Box.new(self.gtk.Orientation.VERTICAL, 10)
            for m in ["top", "bottom", "start", "end"]:
                getattr(container, f"set_margin_{m}")(15)

            self.search_entry = self.gtk.SearchEntry.new()
            self.search_entry.set_placeholder_text("Search library...")
            self.search_entry.connect(
                "search_changed", lambda _: self.flowbox.invalidate_filter()
            )
            container.append(self.search_entry)

            scroll = self.gtk.ScrolledWindow()
            scroll.set_min_content_height(480)
            scroll.set_min_content_width(self.popover_width)
            scroll.set_propagate_natural_height(True)

            self.flowbox = self.gtk.FlowBox()
            self.flowbox.set_max_children_per_line(self.max_cols)
            self.flowbox.set_selection_mode(self.gtk.SelectionMode.NONE)
            self.flowbox.set_filter_func(self._filter_logic)

            scroll.set_child(self.flowbox)
            container.append(scroll)
            self.popover.set_child(container)

        def _parse_vdf(self, path):
            """User-provided stack-based VDF parser."""
            root = {}
            stack = [root]
            last_key = None
            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("//"):
                            continue
                        if line == "{":
                            if last_key is not None:
                                d = {}
                                stack[-1][last_key] = d
                                stack.append(d)
                                last_key = None
                            continue
                        if line == "}":
                            if len(stack) > 1:
                                stack.pop()
                            continue
                        parts = re.findall(r'"([^"]*)"', line)
                        if not parts:
                            continue
                        if len(parts) == 1:
                            last_key = parts[0]
                        elif len(parts) == 2:
                            stack[-1][parts[0]] = parts[1]
                        else:
                            last_key = parts[0]
            except Exception:
                return {}
            return root

        def _find_library_folders(self, steam_root):
            libs = []
            vdf = steam_root / "steamapps/libraryfolders.vdf"
            if not vdf.exists():
                return libs
            data = self._parse_vdf(vdf)
            lf = data.get("libraryfolders")
            if not isinstance(lf, dict):
                return libs
            for entry in lf.values():
                if isinstance(entry, dict) and "path" in entry:
                    libs.append(Path(entry["path"]) / "steamapps")
                elif isinstance(entry, str):
                    libs.append(Path(entry) / "steamapps")
            return libs

        def _find_steam_icon(self, steam_root, appid):
            """Recursive icon discovery including nested hash folders."""
            cache = steam_root / "appcache/librarycache" / appid
            if not cache.exists():
                return None
            logo = cache / "logo.png"
            if logo.exists():
                return str(logo)
            try:
                for entry in cache.iterdir():
                    if entry.is_dir():
                        p = entry / "logo.png"
                        if p.exists():
                            return str(p)
            except Exception:
                pass
            return None

        def _detect_games(self):
            """Consolidated discovery engine."""
            games = []
            seen_ids = set()

            # 1. Steam Detection
            for steam in self.STEAM_BASES:
                if not steam.exists():
                    continue
                libs = [steam / "steamapps"] + self._find_library_folders(steam)
                for lib in libs:
                    if not lib.exists():
                        continue
                    for mf in lib.glob("appmanifest_*.acf"):
                        meta = self._parse_vdf(mf).get("AppState")
                        if not isinstance(meta, dict):
                            continue
                        appid = meta.get("appid")
                        name = meta.get("name")
                        installdir = meta.get("installdir")
                        state = meta.get("StateFlags")

                        if not appid or not name or not installdir:
                            continue
                        if state != "4" or appid in seen_ids:
                            continue
                        if any(x in name.lower() for x in self.BLACKLIST):
                            continue

                        game_path = lib / "common" / installdir
                        if not game_path.exists():
                            continue

                        seen_ids.add(appid)
                        games.append(
                            {
                                "name": name,
                                "cmd": f"steam -silent -applaunch {appid}",
                                "icon": self._find_steam_icon(steam, appid),
                            }
                        )

            # 2. Heroic Detection (Legendary installed.json + Specific Icon Path)
            if self.HEROIC_LEGENDARY_INSTALLED.exists():
                try:
                    data = json.loads(
                        self.HEROIC_LEGENDARY_INSTALLED.read_text(encoding="utf-8")
                    )
                    for key, info in data.items():
                        if key in seen_ids:
                            continue

                        install_path = Path(info.get("install_path", ""))
                        if not install_path.exists():
                            continue

                        icon_path = self.HEROIC_ICONS_DIR / f"{key}.jpg"

                        seen_ids.add(key)
                        games.append(
                            {
                                "name": info.get("title")
                                or info.get("app_name")
                                or install_path.name,
                                "cmd": f"xdg-open 'heroic://launch?appName={key}&runner=legendary'",
                                "icon": str(icon_path) if icon_path.exists() else None,
                            }
                        )
                except Exception:
                    pass

            return sorted(games, key=lambda g: g["name"].lower())

        def _refresh_library(self):
            """Clears and repopulates the flowbox grid."""
            while child := self.flowbox.get_first_child():
                self.flowbox.remove(child)

            for game in self._detect_games():
                tile_wrapper = self.gtk.Box.new(self.gtk.Orientation.VERTICAL, 0)
                tile_wrapper.GAME_NAME = game["name"].lower()

                btn = self.gtk.Button()
                btn.add_css_class("steam-tile-button")
                btn.connect("clicked", lambda *_, c=game["cmd"]: self._launch(c))

                content = self.gtk.Box.new(self.gtk.Orientation.VERTICAL, 6)
                for m in ["top", "bottom", "start", "end"]:
                    getattr(content, f"set_margin_{m}")(8)

                if game["icon"] and Path(game["icon"]).exists():
                    image = self.gtk.Image.new_from_file(game["icon"])
                else:
                    image = self.gtk.Image.new_from_icon_name(
                        "steam" if "steam" in game["cmd"] else "heroic"
                    )

                image.add_css_class("steam-game-icon")
                image.set_pixel_size(64)

                label = self.gtk.Label.new(game["name"])
                label.add_css_class("steam-tile-label")
                label.set_ellipsize(self.pango.EllipsizeMode.END)
                label.set_max_width_chars(12)

                content.append(image)
                content.append(label)
                btn.set_child(content)
                tile_wrapper.append(btn)
                self.flowbox.append(tile_wrapper)

        def _launch(self, cmd):
            """Launches the selected game and closes the popover."""
            self.cmd.run(cmd)
            self.popover.popdown()

        def _filter_logic(self, child):
            """Filters the grid based on search entry text."""
            q = self.search_entry.get_text().strip().lower()
            return q in child.get_child().GAME_NAME if q else True

        def _on_toggle_launcher(self, _):
            """Toggles popover visibility and refreshes content."""
            if not self.popover.get_visible():
                self._refresh_library()
                self.popover.popup()
                self.search_entry.grab_focus()
            else:
                self.popover.popdown()

    return GameLauncher
