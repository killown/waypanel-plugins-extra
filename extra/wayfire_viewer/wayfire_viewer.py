def get_plugin_metadata(panel):
    """Metadata for the plugin system."""
    id = "org.waypanel.plugin.wayfire_config_viewer"
    container, id = panel.config_handler.get_plugin_container("right-panel-center", id)
    return {
        "id": id,
        "name": "Wayfire Config Viewer",
        "version": "2.1.0",
        "enabled": True,
        "container": container,
        "index": 10,
    }


def get_plugin_class():
    """Main execution class."""
    import json
    import os
    import toml
    import ast
    from src.plugins.core._base import BasePlugin
    from .icons import get_svg
    from .template import get_html

    WAYFIRE_TOML_PATH = os.path.expanduser("~/.config/waypanel/wayfire/wayfire.toml")

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

            self.window = Gtk.Window(title="Wayfire Configuration")
            self.window.set_default_size(800, 600)

            view = WebKit.WebView()
            self.window.set_child(view)

            view.get_settings().set_enable_developer_extras(True)
            user_content_manager = view.get_user_content_manager()
            user_content_manager.register_script_message_handler("wayfire")
            user_content_manager.connect(
                "script-message-received::wayfire", self._on_msg
            )

            try:
                options = self.ipc.list_config_options()
                enabled_reply = self.ipc.get_option_value("core/plugins")
                enabled = enabled_reply.get("value", "") if enabled_reply else ""

                raw_config = {}
                if os.path.exists(WAYFIRE_TOML_PATH):
                    with open(WAYFIRE_TOML_PATH, "r") as f:
                        raw_config = toml.load(f)

                view.load_html(
                    get_html(options.get("options", {}), enabled, get_svg, raw_config),
                    None,
                )
            except Exception as e:
                view.load_html(f"Error: {e}", None)

            self.window.present()

        def _on_msg(self, _, msg):
            try:
                data = json.loads(msg.to_json(0))
                msg_type = data.get("msg_type")

                if msg_type == "manual_update":
                    section, key, val = data["section"], data["key"], data["value"]
                    if isinstance(val, str):
                        stripped = val.strip()
                        if (stripped.startswith("[") and stripped.endswith("]")) or (
                            stripped.startswith("{") and stripped.endswith("}")
                        ):
                            try:
                                val = ast.literal_eval(stripped)
                            except:
                                pass
                    self._manual_save(section, key, val)
                    return

                if msg_type == "section_reset":
                    section = data.get("plugin")
                    updates = data.get("updates", {})
                    for path, val in updates.items():
                        parsed = self._parse_val(val)
                        self.ipc.set_option_values({path: parsed})
                    self.panel.config_handler.save_config()
                    return

                if msg_type == "toggle_plugin":
                    plist_reply = self.ipc.get_option_value("core/plugins")
                    if not plist_reply:
                        return
                    plist_raw = plist_reply.get("value", "")
                    plist = (
                        plist_raw.split()
                        if isinstance(plist_raw, str)
                        else list(plist_raw)
                    )
                    name, state = data["plugin"], data["state"]

                    if state and name not in plist:
                        plist.append(name)
                    elif not state and name in plist:
                        plist.remove(name)

                    new_val = " ".join(plist)
                    self.ipc.set_option_values({"core/plugins": new_val})
                    self.panel.config_handler.save_config()
                    return

                # Default IPC update path
                path, val, vtype = data["path"], data["value"], data["type"]
                parsed_val = self._parse_val(val, vtype)
                self.ipc.set_option_values({path: parsed_val})
                self.panel.config_handler.save_config()

            except Exception as e:
                self.logger.error(f"Sync error: {e}")

        def _parse_val(self, val, vtype=None):
            if vtype == "bool" or str(val).lower() in ["true", "false"]:
                return str(val).lower() == "true"
            if vtype == "number" or (
                isinstance(val, str)
                and val.replace(".", "", 1).replace("-", "", 1).isdigit()
            ):
                return float(val) if "." in str(val) else int(val)
            if vtype == "list" or (
                isinstance(val, str) and val.strip().startswith("[")
            ):
                try:
                    return ast.literal_eval(val)
                except:
                    return val
            return val

        def _manual_save(self, section, key, value):
            try:
                os.makedirs(os.path.dirname(WAYFIRE_TOML_PATH), exist_ok=True)
                config = {}
                if os.path.exists(WAYFIRE_TOML_PATH):
                    with open(WAYFIRE_TOML_PATH, "r") as f:
                        config = toml.load(f)
                if section not in config:
                    config[section] = {}
                config[section][key] = value
                with open(WAYFIRE_TOML_PATH, "w") as f:
                    toml.dump(config, f)
            except Exception as e:
                self.logger.error(f"Manual save failed: {e}")

        def on_stop(self):
            if self.window:
                self.window.close()

    return WayfireConfigViewerPlugin
