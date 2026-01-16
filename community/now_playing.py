def get_plugin_metadata(panel):
    """
    Metadata for the Player Calendar Integration plugin.
    Integrates media player metadata into the Calendar plugin's popover.
    """
    return {
        "id": "org.waypanel.plugin.player_calendar",
        "name": "Player Calendar Integration",
        "version": "2.0.0",
        "description": "Adds a dynamic list of active media players to the calendar popover.",
        "author": "Architect Prime",
        "container": "background",
        "deps": ["calendar"],
        "enabled": True,
    }


def get_plugin_class():
    """
    Returns the PlayerCalendarPlugin class.
    Imports are deferred to comply with waypanel architecture.
    """
    import gi
    from gi.repository import Gtk, GLib, GdkPixbuf, Gdk

    try:
        gi.require_version("Playerctl", "2.0")
        from gi.repository import Playerctl
    except ValueError:
        Playerctl = None

    from src.plugins.core._base import BasePlugin

    class PlayerRow(Gtk.Box):
        """
        Encapsulated UI component representing a single media player row.
        Handles its own state, events, and async art loading.
        """

        def __init__(self, player, plugin):
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            self.player = player
            self.plugin = plugin
            self.player_name = player.props.player_name
            self._download_task = None

            self._setup_ui()
            self.update_ui()  # Initial render

        def _setup_ui(self):
            """Constructs the row layout."""
            self.add_css_class("player-row")
            self.set_margin_bottom(8)

            # --- Album Art ---
            self.art_image = Gtk.Image()
            self.art_image.set_pixel_size(72)
            self.art_image.add_css_class("player-art")
            self.append(self.art_image)

            # --- Info & Controls Container ---
            right_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            right_vbox.set_valign(Gtk.Align.CENTER)
            right_vbox.set_hexpand(True)

            # Title
            self.title_label = Gtk.Label(label="Unknown Title")
            self.title_label.add_css_class("player-title")
            self.title_label.set_halign(Gtk.Align.START)
            self.title_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
            self.title_label.set_max_width_chars(30)

            # Artist
            self.artist_label = Gtk.Label(label="Unknown Artist")
            self.artist_label.add_css_class("player-artist")
            self.artist_label.set_halign(Gtk.Align.START)
            self.artist_label.set_ellipsize(3)
            self.artist_label.set_max_width_chars(30)

            # Controls
            controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            controls_box.set_halign(Gtk.Align.START)

            self.btn_play_pause = self._create_btn(
                "media-playback-start-symbolic", self._on_play_pause, "Play/Pause"
            )

            controls_box.append(
                self._create_btn(
                    "media-skip-backward-symbolic", self._on_prev, "Previous"
                )
            )
            controls_box.append(self.btn_play_pause)
            controls_box.append(
                self._create_btn("media-skip-forward-symbolic", self._on_next, "Next")
            )

            right_vbox.append(self.title_label)
            right_vbox.append(self.artist_label)
            right_vbox.append(controls_box)

            self.append(right_vbox)

            # Gesture for the whole row (optional convenience)
            click_ctrl = Gtk.GestureClick()
            click_ctrl.connect("pressed", lambda *_: self._on_play_pause(None))
            self.add_controller(click_ctrl)

        def _create_btn(self, icon, callback, tooltip):
            btn = Gtk.Button.new_from_icon_name(icon)
            btn.add_css_class("flat")
            btn.set_tooltip_text(tooltip)
            btn.connect("clicked", callback)
            return btn

        def update_ui(self):
            """Refreshes labels and art based on current player metadata."""
            try:
                metadata = self.player.props.metadata
                if not metadata:
                    return

                data = metadata.unpack()
                if not data:
                    return

                # Text
                title = data.get("xesam:title", "Unknown Title")
                artist = data.get("xesam:artist", "Unknown Artist")
                if isinstance(artist, list):
                    artist = ", ".join(artist)

                self.title_label.set_label(str(title))
                self.artist_label.set_label(str(artist))

                # Play/Pause Icon State
                status = self.player.props.playback_status
                if status == Playerctl.PlaybackStatus.PLAYING:
                    self.btn_play_pause.set_icon_name("media-playback-pause-symbolic")
                else:
                    self.btn_play_pause.set_icon_name("media-playback-start-symbolic")

                # Art
                art_url = data.get("mpris:artUrl")
                if art_url:
                    self._load_art(str(art_url))
                else:
                    self.art_image.set_from_icon_name("audio-x-generic-symbolic")

            except Exception as e:
                self.plugin.logger.error(f"Row Update Error ({self.player_name}): {e}")

        def _load_art(self, url):
            if self._download_task:
                self._download_task.cancel()

            if url.startswith("file://"):
                from urllib.parse import unquote

                path = unquote(url[7:])
                self._set_pixbuf(path)
            elif url.startswith("http"):
                self._download_task = self.plugin.run_in_async_task(
                    self._download_image(url)
                )
            else:
                self.art_image.set_from_icon_name("audio-x-generic-symbolic")

        async def _download_image(self, url):
            import tempfile
            import aiohttp

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.read()
                            with tempfile.NamedTemporaryFile(
                                delete=False, suffix=".jpg"
                            ) as tmp:
                                tmp.write(data)
                                tmp_path = tmp.name
                            GLib.idle_add(self._set_pixbuf, tmp_path)
            except Exception:
                GLib.idle_add(
                    self.art_image.set_from_icon_name, "audio-x-generic-symbolic"
                )

        def _set_pixbuf(self, path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 72, 72, True)
                self.art_image.set_from_pixbuf(pixbuf)
            except Exception:
                self.art_image.set_from_icon_name("audio-x-generic-symbolic")
            return False

        # --- Controls ---
        def _on_play_pause(self, _):
            self.player.play_pause()

        def _on_prev(self, _):
            self.player.previous()

        def _on_next(self, _):
            self.player.next()

        def destroy_row(self):
            """Cleanup hook."""
            if self._download_task:
                self._download_task.cancel()
            self.plugin.logger.info(f"Destroying row for {self.player_name}")

    class PlayerCalendarPlugin(BasePlugin):
        """
        Manages the integration and list of active players.
        """

        def __init__(self, panel_instance):
            super().__init__(panel_instance)
            self.player_manager = None
            self.main_container = None
            self.target_grid = None

            # Registry: {player_name: PlayerRow_widget}
            self.active_rows = {}

        def on_start(self):
            if Playerctl is None:
                self.logger.error("Playerctl lib not found. Plugin disabled.")
                return

            self._setup_ui()
            self._setup_playerctl()
            self.schedule_in_gtk_thread(self._integrate_into_calendar)
            self.logger.info("PlayerCalendarPlugin V2 started.")

        def on_stop(self):
            if self.main_container and self.main_container.get_parent():
                self.main_container.get_parent().remove(self.main_container)

            # Clean up all rows
            for row in self.active_rows.values():
                row.destroy_row()
            self.active_rows.clear()

        def _setup_ui(self):
            # Main vertical stack
            self.main_container = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            self.main_container.add_css_class("players-container")
            self.main_container.set_margin_top(12)
            self.main_container.set_margin_bottom(6)
            self.main_container.set_margin_start(12)
            self.main_container.set_margin_end(12)
            self.main_container.set_visible(False)  # Hide if empty

        def _integrate_into_calendar(self):
            try:
                calendar_plugin = self.plugins.get("calendar")
                if not calendar_plugin:
                    return

                popover = getattr(calendar_plugin, "popover_calendar", None)
                if not popover:
                    return

                child = popover.get_child()
                if isinstance(child, Gtk.Grid):
                    self.target_grid = child
                    # Attach at bottom (row 2), spanning 3 columns
                    self.target_grid.attach(self.main_container, 0, 2, 3, 1)
                    self.logger.info("Player container attached to Calendar Grid.")
            except Exception as e:
                self.logger.error(f"Integration failed: {e}")

        def _setup_playerctl(self):
            self.player_manager = Playerctl.PlayerManager()
            self.player_manager.connect("name-appeared", self._on_name_appeared)
            self.player_manager.connect("player-vanished", self._on_player_vanished)

            for name in self.player_manager.props.player_names:
                self._on_name_appeared(self.player_manager, name)

        def _on_name_appeared(self, _, name):
            """New player detected: Create a row."""
            try:
                # Avoid duplicates
                if name.name in self.active_rows:
                    return

                player = Playerctl.Player.new_from_name(name)
                player.connect("metadata", self._on_metadata)
                player.connect("playback-status", self._on_status)
                player.connect("exit", self._on_exit)

                row = PlayerRow(player, self)
                self.active_rows[name.name] = row
                self.main_container.append(row)

                # Update visibility
                self.main_container.set_visible(True)

            except Exception as e:
                self.logger.error(f"Failed to init player {name}: {e}")

        def _on_player_vanished(self, _, name):
            """Player removed: Destroy row."""
            # name is a PlayerName object or string depending on context
            # In 'player-vanished', 'name' is usually the PlayerName object.
            key = name.name if hasattr(name, "name") else name

            if key in self.active_rows:
                row = self.active_rows.pop(key)
                self.main_container.remove(row)
                row.destroy_row()

            if not self.active_rows:
                self.main_container.set_visible(False)

        def _on_exit(self, player):
            # player.props.player_name is a string
            self._on_player_vanished(None, player.props.player_name)

        def _on_metadata(self, player, metadata):
            name = player.props.player_name
            if name in self.active_rows:
                self.active_rows[name].update_ui()

        def _on_status(self, player, status):
            name = player.props.player_name
            if name in self.active_rows:
                self.active_rows[name].update_ui()

    return PlayerCalendarPlugin
