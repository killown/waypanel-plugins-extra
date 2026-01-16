def get_plugin_metadata(_):
    return {
        "id": "org.waypanel.plugin.background_menu",
        "name": "Background Menu",
        "version": "1.0.0",
        "enabled": False,
        "container": "background",
        "description": "Provides a right-click context menu on the desktop background layer.",
        "priority": 50,
        "deps": ["gestures_setup"],
    }


def get_plugin_class():
    """
    The factory function to return the plugin class. All library imports MUST be deferred here.
    """
    from src.plugins.core._base import BasePlugin  # pyright: ignore
    from gi.repository import Gtk, Gdk, Gtk4LayerShell, GLib, Gio  # pyright: ignore

    class BackgroundMenuPlugin(BasePlugin):
        """
        Plugin responsible for creating the fullscreen background layer shell window
        and implementing a right-click context menu for desktop actions.
        """

        ACTION_PREFIX = "bg"

        def __init__(self, panel_instance):
            """
            Initializes the background plugin.
            """
            super().__init__(panel_instance)
            self.window = None
            self._file_dialog = None
            self._transient_window = None
            self.create_gesture = self.plugins["gestures_setup"].create_gesture
            self._action_group = None

        def on_start(self):
            """
            Initializes the background layer shell window, sets anchors, and sets
            up the right-click handler. Called automatically during startup.
            """
            self.window = Gtk.Window()
            self.window.add_css_class("desktop-layer-window")
            self.window.set_title("Waypanel Background Layer")
            Gtk4LayerShell.init_for_window(self.window)
            Gtk4LayerShell.set_namespace(self.window, "waypanel-background-layer")
            Gtk4LayerShell.set_layer(self.window, Gtk4LayerShell.Layer.BOTTOM)
            Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.LEFT, True)
            Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.RIGHT, True)
            Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.TOP, True)
            Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.BOTTOM, True)
            Gtk4LayerShell.set_exclusive_zone(self.window, 0)
            self.container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            self.window.set_child(self.container)
            self.create_gesture(self.window, 3, self._on_right_click)
            self._setup_gio_actions()
            self.window.show()

        def on_stop(self):
            """
            Cleans up the window and resources when the plugin is disabled/unloaded.
            """
            self.plugin_loader.disable_plugin(
                get_plugin_metadata(self._panel_instance).get("id")
            )

        def _setup_gio_actions(self):
            """
            Creates and registers the Gio.SimpleActionGroup for the context menu.
            """
            action_group = Gio.SimpleActionGroup()
            action_set_fav = Gio.SimpleAction.new("set-favorite-image", None)
            action_set_fav.connect("activate", self._trigger_file_dialog)
            action_group.add_action(action_set_fav)
            action_sample = Gio.SimpleAction.new("sample-action", None)
            action_sample.connect("activate", self._menu_item_activated, "Action 1")
            action_group.add_action(action_sample)
            action_quit = Gio.SimpleAction.new("quit", None)
            action_quit.connect("activate", self._menu_item_activated, "Quit")
            action_group.add_action(action_quit)
            self.window.insert_action_group(self.ACTION_PREFIX, action_group)
            self._action_group = action_group

        def _on_right_click(self, *_) -> None:
            """
            Handles the right-click event. Retrieves pointer coordinates to position the popover.
            """
            x, y = self.ipc.get_cursor_position()
            self._open_context_menu(x, y)

        def _create_transient_parent_window(self):
            """
            Creates a minimal Gtk.Window of size 1x1 to be used as a temporary parent
            for the modal Gtk.FileDialog.
            """
            self.logger.debug("Creating temporary transient window for Gtk.FileDialog.")
            temp_window = Gtk.Window()
            temp_window.set_default_size(1, 1)
            temp_window.set_opacity(0.0)
            temp_window.set_title("File Dialog Parent")
            temp_window.set_child(Gtk.Label(label=""))
            temp_window.present()
            return temp_window

        def _run_file_dialog_async(self, *args) -> bool:
            """
            Opens a Gtk.FileDialog to select an image file.
            This function is called via GLib.idle_add.
            """
            self.logger.info("Starting Gtk.FileDialog to select image.")
            self._transient_window = self._create_transient_parent_window()
            file_dialog = Gtk.FileDialog.new()
            file_dialog.set_title("Select Image File for Background")
            filter_images = Gtk.FileFilter.new()
            filter_images.set_name("Image files (JPEG, PNG, GIF, WebP)")
            filter_images.add_mime_type("image/jpeg")
            filter_images.add_mime_type("image/png")
            filter_images.add_mime_type("image/gif")
            filter_images.add_mime_type("image/webp")
            filter_all = Gtk.FileFilter.new()
            filter_all.set_name("All Files")
            filter_all.add_pattern("*")
            list_model = Gio.ListStore.new(Gtk.FileFilter)
            list_model.append(filter_images)
            list_model.append(filter_all)
            file_dialog.set_filters(list_model)
            file_dialog.set_default_filter(filter_images)
            self._file_dialog = file_dialog
            file_dialog.open(
                parent=self._transient_window,
                cancellable=None,
                callback=self._file_selected_callback,
            )
            return False

        def _trigger_file_dialog(self, action, parameter) -> None:
            """
            Activated by the menu item. Uses GLib.idle_add to safely run
            the asynchronous dialog function after the menu is dismissed.
            """
            GLib.idle_add(self._run_file_dialog_async)

        def _file_selected_callback(self, dialog, result) -> None:
            """
            Handles the result when the user closes the Gtk.FileDialog.
            """
            self._file_dialog = None
            if self._transient_window:
                self.logger.debug("Destroying temporary transient window.")
                self._transient_window.destroy()
                self._transient_window = None
            try:
                gio_file = dialog.open_finish(result)
                if gio_file is not None:
                    file_path = gio_file.get_path()
                    if file_path:
                        self.logger.info(f"File selected successfully: {file_path}")
                        print(f"File Path: {file_path}")
                    else:
                        self.logger.warning("Selected file does not have a local path.")
                else:
                    self.logger.info("File selection cancelled by the user.")
            except GLib.Error as error:
                self.logger.error(f"Error opening file dialog: {error.message}")

        def _open_context_menu(self, x, y) -> None:
            """
            Creates and displays a Gtk.PopoverMenu using a Gio.MenuModel at the click location (x, y).
            """
            menu = Gio.Menu.new()
            menu.append_item(
                Gio.MenuItem.new(
                    "Set Favorite Image (fav.jpg)",
                    f"{self.ACTION_PREFIX}.set-favorite-image",
                )
            )
            menu.append_item(
                Gio.MenuItem.new(
                    "Sample Action 1 (Check Log)", f"{self.ACTION_PREFIX}.sample-action"
                )
            )
            menu.append_item(
                Gio.MenuItem.new(
                    "Quit Background (Disable Plugin)", f"{self.ACTION_PREFIX}.quit"
                )
            )
            popover = Gtk.PopoverMenu()
            popover.set_parent(self.container)
            popover.add_css_class("background-menu-popover")
            popover.add_css_class("desktop-popover")
            popover.set_menu_model(menu)
            rect = Gdk.Rectangle()
            rect.x = int(x)
            rect.y = int(y)
            rect.width = 1
            rect.height = 1
            popover.set_pointing_to(rect)
            popover.popup()

        def _menu_item_activated(self, action, parameter, user_data=None):
            """Handler for the menu item activation."""
            action_name = user_data if user_data else action.get_name()
            self.logger.info(f"Gio Action '{action_name}' activated.")
            if action_name == "Quit":
                GLib.idle_add(self.on_stop)
                return

    return BackgroundMenuPlugin
