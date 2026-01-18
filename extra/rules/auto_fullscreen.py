def get_plugin_metadata(panel):
    """
    Define the plugin's properties and background container placement.

    Args:
        panel: The main Panel instance.
    """
    id = "org.waypanel.plugin.auto_fullscreen"
    container = "background"

    return {
        "id": id,
        "name": "Auto Fullscreen",
        "version": "1.1.3",
        "enabled": True,
        "container": container,
        "index": 0,
        "deps": ["event_manager"],
        "description": "Automatically fullscreens specific applications upon mapping.",
    }


def get_plugin_class():
    """Returns the main plugin class with deferred imports."""
    from src.plugins.core._base import BasePlugin

    class AutoFullscreenPlugin(BasePlugin):
        """
        Monitors 'view-mapped' events and forces fullscreen for configured app-ids.
        """

        def __init__(self, panel_instance):
            super().__init__(panel_instance)
            self.fullscreen_key = "KEY_F11"
            self.delay = 300

        def on_start(self):
            """Subscribes to events and registers configuration settings."""
            self.get_plugin_setting_add_hint(
                "fullscreen_app_ids",
                ["virt-manager", "vlc"],
                "List of app-ids to automatically trigger fullscreen on startup",
            )

            self.fullscreen_key = self.get_plugin_setting_add_hint(
                "fullscreen_key",
                "KEY_F11",
                "The key to press (libinput key name) as a fallback for fullscreen",
            )

            self.delay = self.get_plugin_setting_add_hint(
                "fullscreen_delay_ms",
                300,
                "Milliseconds to wait after mapping before triggering fullscreen",
            )

            self._subscribe_to_events()

        def _subscribe_to_events(self):
            """Connects to the event manager to listen for window mapping."""
            if "event_manager" not in self.obj.plugin_loader.plugins:
                self.logger.error(
                    "Event Manager not found; cannot auto-fullscreen views."
                )
                return

            event_mgr = self.obj.plugin_loader.plugins["event_manager"]
            event_mgr.subscribe_to_event("view-mapped", self._on_view_mapped)

        def set_fullscreen(self, app_id, view_id):
            """
            Executes the fullscreen key press and verifies state via IPC.

            Args:
                app_id: The application identifier.
                view_id: The view identifier.

            Returns:
                False to stop the GLib timeout.
            """
            self.logger.info(f"Auto-fullscreening: {app_id} (ID: {view_id})")

            if self.fullscreen_key:
                # We use F11 instead of self.ipc.set_view_fullscreen(view_id, True)
                # because it is often more reliable and ensures the application
                # triggers its internal true fullscreen state.
                self.ipc.press_key(self.fullscreen_key)

            # Verify if the view actually entered fullscreen
            self._verify_fullscreen(view_id)
            return False

        def _verify_fullscreen(self, view_id: int) -> bool:
            """
            Checks if a view is fullscreen. If not, forces it via IPC.
            """
            view = self.ipc.get_view(view_id)
            if not view:
                return False

            if not view.get("fullscreen"):
                self.logger.warn(
                    f"View {view_id} did not respond to F11. Forcing via IPC."
                )
                self.ipc.set_view_fullscreen(view_id, True)

            return False

        def _on_view_mapped(self, event_data: dict):
            """
            Checks if the mapped view's app-id is in the target list and applies fullscreen.

            Args:
                event_data: The IPC event payload containing view details.
            """
            view = event_data.get("view", {})
            view_id = view.get("id")
            app_id = view.get("app-id", "")

            fullscreen_apps = self.get_plugin_setting("fullscreen_app_ids", [])

            if app_id in fullscreen_apps:
                self.glib.timeout_add(self.delay, self.set_fullscreen, app_id, view_id)

        def on_stop(self):
            """Cleanup operations when the plugin is disabled."""
            pass

    return AutoFullscreenPlugin
