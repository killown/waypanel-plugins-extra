def get_plugin_metadata(panel):
    """Metadata for the plugin system."""
    id = "org.waypanel.plugin.wayfire_config_viewer"
    container, id = panel.config_handler.get_plugin_container("right-panel-center", id)
    return {
        "id": id,
        "name": "Wayfire Config Viewer",
        "version": "2.0.0",
        "enabled": True,
        "container": container,
        "index": 10,
    }


def get_plugin_class():
    """Main execution class."""
    import json
    from src.plugins.core._base import BasePlugin
    from .icons import get_svg
    from .template import get_html

    class WayfireConfigViewerPlugin(BasePlugin):
        def __init__(self, panel_instance):
            super().__init__(panel_instance)
            self.window = None

        def on_start(self):
            self.button = self.gtk.Button(icon_name="preferences-system-symbolic")
            self.button.connect("clicked", self.on_click)
            self.add_cursor_effect(self.button)
            self.main_widget = (self.button, "append")

        def on_click(self, _):
            if self.window and self.window.get_visible():
                self.window.present()
                return
            self._open_viewer()

        def _open_viewer(self):
            import gi

            gi.require_version("WebKit", "6.0")
            from gi.repository import Gtk, WebKit
            from wayfire import WayfireSocket

            self.window = Gtk.Window(
                title="Wayfire Inspector", default_width=1000, default_height=800
            )
            manager = WebKit.UserContentManager()
            manager.register_script_message_handler("wayfire", None)
            manager.connect("script-message-received::wayfire", self._on_msg)

            view = WebKit.WebView(user_content_manager=manager)
            scroll = Gtk.ScrolledWindow(child=view)
            self.window.set_child(scroll)

            try:
                sock = WayfireSocket()
                raw_data = sock.list_config_options()
                enabled = sock.get_option_value("core/plugins")["value"]
                view.load_html(
                    get_html(raw_data.get("options", {}), enabled, get_svg), None
                )
            except Exception as e:
                view.load_html(f"Error: {e}", None)

            self.window.present()

        def _on_msg(self, _, msg):
            from wayfire import WayfireSocket

            try:
                data = json.loads(msg.to_json(0))
                sock = WayfireSocket()
                if data.get("msg_type") == "toggle_plugin":
                    plist = sock.get_option_value("core/plugins")["value"]
                    plist = plist.split() if isinstance(plist, str) else list(plist)
                    name, state = data["plugin"], data["state"]
                    if state and name not in plist:
                        plist.append(name)
                    elif not state and name in plist:
                        plist.remove(name)
                    sock.set_option_values({"core/plugins": " ".join(plist)})
                else:
                    path, val, vtype = data["path"], data["value"], data["type"]
                    if vtype == "bool":
                        val = bool(val)
                    elif vtype == "number":
                        val = float(val) if "." in str(val) else int(val)
                    sock.set_option_values({path: val})
            except Exception as e:
                self.logger.error(f"Sync error: {e}")

        def on_stop(self):
            if self.window:
                self.window.close()

    return WayfireConfigViewerPlugin
