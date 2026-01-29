def get_plugin_metadata(panel):
    return {
        "id": "org.waypanel.plugin.player_calendar",
        "name": "Player Calendar Integration",
        "version": "2.2.0",
        "description": "Integrates media player metadata into the Calendar plugin's popover.",
        "author": "Architect Prime",
        "container": "background",
        "deps": ["calendar"],
        "enabled": True,
    }


def get_plugin_class():
    import gi
    import os

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, GdkPixbuf, Gio
    from src.plugins.core._base import BasePlugin
    from src.shared.dbus_helpers import DbusHelpers
    from dbus_fast.aio import MessageBus
    from dbus_fast import BusType

    class PlayerRow(Gtk.Box):
        def __init__(self, service_name, plugin):
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            self.service_name = service_name
            self.plugin = plugin
            self.last_art_url = None
            self._setup_ui()

        def _setup_ui(self):
            self.add_css_class("player-row")
            self.set_margin_bottom(12)

            # Album Art with fixed size constraints
            self.art_image = Gtk.Image()
            self.art_image.set_pixel_size(72)
            self.art_image.set_size_request(72, 72)
            self.art_image.add_css_class("player-art")
            self.append(self.art_image)

            right_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            right_vbox.set_valign(Gtk.Align.CENTER)
            right_vbox.set_hexpand(True)

            # Title with character limit and ellipsize
            self.title_label = Gtk.Label(label="Unknown Title")
            self.title_label.set_halign(Gtk.Align.START)
            self.title_label.set_max_width_chars(25)
            self.title_label.add_css_class("player-title")

            self.artist_label = Gtk.Label(label="Unknown Artist")
            self.artist_label.set_halign(Gtk.Align.START)
            self.artist_label.set_max_width_chars(30)
            self.artist_label.add_css_class("caption")

            controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self.btn_prev = self._create_btn("media-skip-backward-symbolic", "previous")
            self.btn_play = self._create_btn(
                "media-playback-start-symbolic", "play_pause"
            )
            self.btn_next = self._create_btn("media-skip-forward-symbolic", "next")

            controls_box.append(self.btn_prev)
            controls_box.append(self.btn_play)
            controls_box.append(self.btn_next)

            right_vbox.append(self.title_label)
            right_vbox.append(self.artist_label)
            right_vbox.append(controls_box)
            self.append(right_vbox)

        def _create_btn(self, icon, action):
            btn = Gtk.Button.new_from_icon_name(icon)
            btn.add_css_class("flat")
            btn.connect(
                "clicked",
                lambda _: self.plugin.run_in_async_task(
                    self.plugin.local_dbus.player_action(self.service_name, action)
                ),
            )
            return btn

        def update_ui(self, data):
            # Enforce hard text length limits
            title = data.get("title", "Unknown")
            if len(title) > 50:
                title = title[:47] + "..."

            self.title_label.set_text(title)
            self.artist_label.set_text(data.get("artist", "Unknown"))

            icon = (
                "media-playback-pause-symbolic"
                if data.get("status") == "Playing"
                else "media-playback-start-symbolic"
            )
            self.btn_play.set_icon_name(icon)

            art_url = data.get("art_url")
            if art_url and art_url != self.last_art_url:
                self.last_art_url = art_url
                self._load_art_async(art_url)
            elif not art_url:
                self.art_image.set_from_icon_name("audio-x-generic-symbolic")

            self.btn_next.set_sensitive(data.get("can_next", True))
            self.btn_prev.set_sensitive(data.get("can_prev", True))

        def _load_art_async(self, url):
            """Loads art asynchronously to prevent UI hangs with remote/sandboxed URIs."""
            if not url:
                return

            def _on_load_finished(source, result):
                try:
                    stream = source.read_finish(result)
                    pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
                        stream, 72, 72, True, None
                    )
                    self.plugin.schedule_in_gtk_thread(
                        lambda: self.art_image.set_from_pixbuf(pixbuf)
                    )
                except Exception:
                    self.plugin.schedule_in_gtk_thread(
                        lambda: self.art_image.set_from_icon_name(
                            "audio-x-generic-symbolic"
                        )
                    )

            try:
                # Handle file:// and https:// via Gio
                file = Gio.File.new_for_uri(url)
                file.read_async(GLib.PRIORITY_DEFAULT, None, _on_load_finished)
            except Exception:
                self.art_image.set_from_icon_name("audio-x-generic-symbolic")

    class PlayerCalendarPlugin(BasePlugin):
        def on_enable(self):
            self.active_rows = {}
            self.local_dbus = None
            self.main_container = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=0
            )
            self.main_container.add_css_class("players-container")
            self.main_container.set_visible(False)

            GLib.timeout_add(1000, self._integrate_with_retry)
            self.run_in_async_task(self._init_local_dbus_and_monitor())

        async def _init_local_dbus_and_monitor(self):
            try:
                bus = await MessageBus(bus_type=BusType.SESSION).connect()
                self.local_dbus = DbusHelpers(bus)
                await self._monitor_loop()
            except Exception as e:
                self.logger.error(f"D-Bus init failed: {e}")

        async def _monitor_loop(self):
            while True:
                try:
                    players = await self.local_dbus.get_active_mpris_players()
                    valid_ids = set()

                    for p_id in players:
                        meta = await self.local_dbus.get_media_metadata(p_id)
                        # Filter out empty metadata ghosts (Edge instances)
                        if meta and (meta.get("title") or meta.get("status")):
                            valid_ids.add(p_id)
                            self.schedule_in_gtk_thread(self._sync_row, p_id, meta)

                    for p_id in list(self.active_rows.keys()):
                        if p_id not in valid_ids:
                            self.schedule_in_gtk_thread(self._remove_row, p_id)
                except Exception as e:
                    self.logger.error(f"Monitor error: {e}")
                await self.asyncio.sleep(2)

        def _sync_row(self, p_id, meta):
            if p_id not in self.active_rows:
                row = PlayerRow(p_id, self)
                self.active_rows[p_id] = row
                self.main_container.append(row)
                self.main_container.set_visible(True)
            self.active_rows[p_id].update_ui(meta)

        def _remove_row(self, p_id):
            row = self.active_rows.pop(p_id, None)
            if row:
                self.main_container.remove(row)
            if not self.active_rows:
                self.main_container.set_visible(False)

        def _integrate_with_retry(self):
            cal = self.plugins.get("calendar")
            if not cal or not hasattr(cal, "popover_calendar"):
                return True
            grid = cal.popover_calendar.get_child()
            if isinstance(grid, Gtk.Grid) and self.main_container.get_parent() is None:
                # Attach to bottom of calendar grid
                grid.attach(self.main_container, 0, 3, 3, 1)
                return False
            return True

        def on_disable(self):
            if self.main_container and self.main_container.get_parent():
                self.main_container.get_parent().remove(self.main_container)
            self.active_rows.clear()

    return PlayerCalendarPlugin
