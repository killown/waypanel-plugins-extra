def get_plugin_metadata(_):
    about = (
        "Provides a user interface for quickly finding and opening"
        "files from a configured directory, using an extension-based editor mapping."
    )
    return {
        "id": "org.waypanel.plugin.open_with_editor",
        "name": "Open with editor",
        "version": "1.0.0",
        "enabled": True,
        "index": 3,
        "priority": 300,
        "container": "top-panel-box-widgets-left",
        "deps": ["css_generator"],
        "description": about,
    }


def get_plugin_class():
    from src.plugins.core._base import BasePlugin
    from .scanner import get_scanner_logic
    from .launcher import get_launcher_logic
    from .ui import get_ui_factory

    Scanner = get_scanner_logic()
    Launcher = get_launcher_logic()
    UIFactory = get_ui_factory()

    class OpenWithEditor(BasePlugin):
        """
        A plugin to quickly search and open files from a configured directory,
        using a specified editor based on file extension.
        """

        def __init__(self, panel_instance):
            super().__init__(panel_instance)
            self.add_hint(
                ["Searchable UI for files with multi-editor launch support."], None
            )

            self.listbox_widgets = {}
            self.searchbar_widgets = {}
            self.cached_files = {}
            self.active_listbox = None
            self.active_searchbar = None
            self.popover_openwitheditor = None

            self.scanner = Scanner(self)
            self.launcher = Launcher(self)
            self.ui_factory = UIFactory(self)
            self.plugins["css_generator"].install_css("main.css")

        def on_start(self):
            """
            Initialize configuration and UI components.
            """
            self.launcher.init_config()
            self.ui_factory.create_menu_button()
            self.main_widget = (self.ui_factory.menubutton, "append")

        def on_enable(self):
            """
            Lifecycle handled by on_start.
            """
            pass

        def open_popover(self, *_):
            if not self.popover_openwitheditor:
                self.ui_factory.create_popover()

            if self.popover_openwitheditor.is_visible():
                self.popover_openwitheditor.popdown()
            else:
                if self.active_listbox:
                    self.active_listbox.unselect_all()
                self.popover_openwitheditor.popup()

    return OpenWithEditor
