def get_plugin_metadata(panel):
    """Metadata for the plugin system."""
    id = "org.waypanel.plugin.wayfire_config_viewer"
    return {
        "id": id,
        "name": "Wayfire Config Viewer",
        "version": "2.4.0",
        "enabled": True,
        "container": "background",
        "index": 10,
        "deps": ["app_launcher"],
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
            self.view = None

        def on_start(self):
            self.button = self.gtk.Button(icon_name="preferences-system-symbolic")
            self.button.connect("clicked", self.on_click)
            self.add_cursor_effect(self.button)
            self.plugins["app_launcher"].system_button_config["Wayfire Settings"] = {
                "icons": self.get_plugin_setting(
                    ["buttons", "icons", "settings"],
                    [
                        "settings-configure-symbolic",
                        "systemsettings-symbolic",
                        "settings",
                    ],
                ),
                "callback": self.on_click,
            }

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

            self.view = WebKit.WebView()
            self.window.set_child(self.view)

            self.view.get_settings().set_enable_developer_extras(True)
            user_content_manager = self.view.get_user_content_manager()
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

                self.view.load_html(
                    get_html(options.get("options", {}), enabled, get_svg, raw_config),
                    None,
                )
            except Exception as e:
                self.view.load_html(f"Error: {e}", None)

            self.window.present()

        def _on_msg(self, _, msg):
            """
            Handles incoming JSON messages from the WebKit view and synchronizes
            changes between the Live IPC, internal config, and the physical TOML file.
            """
            try:
                # WebKit messages are typically strings; parse into dict
                data = json.loads(msg.to_json(0))
                msg_type = data.get("msg_type")

                # 1. Handle Plugin Toggling
                if msg_type == "toggle_plugin":
                    plist_reply = self.ipc.get_option_value("core/plugins")
                    if not plist_reply:
                        return

                    plist_raw = plist_reply.get("value", "")
                    plist = plist_raw.split()
                    name, state = data["plugin"], data["state"]

                    if state and name not in plist:
                        plist.append(name)
                    elif not state and name in plist:
                        try:
                            plist.remove(name)
                        except ValueError:
                            pass

                    new_val = " ".join(plist)

                    # Sync Live, Disk, and Internal Cache
                    self.ipc.set_option_values({"core/plugins": new_val})
                    self._manual_save("core", "plugins", new_val)
                    self.config_handler.update_config(["core", "plugins"], new_val)
                    return

                # 2. Handle Manual Option Updates (usually for custom keys)
                if msg_type == "manual_update":
                    section, key, val = data["section"], data["key"], data["value"]
                    parsed_val = self._parse_val(val)

                    self._manual_save(section, key, parsed_val)
                    self.ipc.set_option_values({f"{section}/{key}": parsed_val})
                    self.config_handler.update_config([section, key], parsed_val)
                    return

                # 3. Handle Manual Key Deletion
                if msg_type == "manual_delete":
                    section, key = data["section"], data["key"]
                    self._manual_delete(section, key)
                    self.config_handler.remove_root_setting([section, key])
                    return

                # 4. Handle Standard Widget Updates (Sliders, Text Inputs, Enums)
                # These usually come with a 'path' (e.g., 'command/width')
                if "path" in data:
                    path, val, vtype = data["path"], data["value"], data["type"]
                    parsed_val = self._parse_val(val, vtype)

                    # Update the live compositor instance
                    self.ipc.set_option_values({path: parsed_val})

                    # Update Waypanel's internal settings cache
                    self.config_handler.update_config(path.split("/"), parsed_val)

                    # FIXED: Save to the physical TOML file for persistence
                    # Split 'section/key' to extract location for _manual_save
                    path_parts = path.split("/")
                    if len(path_parts) == 2:
                        section, key = path_parts
                        self._manual_save(section, key, parsed_val)

                    self.logger.debug(
                        f"Wayfire Sync: Persistent update for {path} -> {parsed_val}"
                    )

            except Exception as e:
                self.logger.error(f"Wayfire Sync Error: {e}")

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

        def _manual_delete(self, section, key):
            try:
                if not os.path.exists(WAYFIRE_TOML_PATH):
                    return
                with open(WAYFIRE_TOML_PATH, "r") as f:
                    config = toml.load(f)
                if section in config and key in config[section]:
                    del config[section][key]
                    with open(WAYFIRE_TOML_PATH, "w") as f:
                        toml.dump(config, f)
            except Exception as e:
                self.logger.error(f"Manual delete failed: {e}")

        def on_stop(self):
            if self.window:
                self.window.close()

    return WayfireConfigViewerPlugin
