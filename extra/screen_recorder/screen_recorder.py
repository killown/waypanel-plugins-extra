def get_plugin_metadata(panel):
    about = "A plugin that provides a simple screen and audio recording utility"
    id = "org.waypanel.plugin.screen_recorder"
    default_container = "top-panel-systray"
    container, id = panel.config_handler.get_plugin_container(default_container, id)
    return {
        "id": id,
        "name": "Screen Recorder",
        "version": "1.0.0",
        "enabled": True,
        "index": 10,
        "hidden": True,
        "container": container,
        "deps": ["top_panel"],
        "description": about,
    }


def get_plugin_class():
    from gi.repository import Gtk  # pyright: ignore
    from src.plugins.core._base import BasePlugin
    import shutil
    from .config import setup_plugin_settings
    from . import logic

    class RecordingPopover(Gtk.Box):
        """
        A dedicated container (Gtk.Box) for selecting recording options.
        Its content will be placed inside the Gtk.Popover created by BasePlugin.
        """

        def __init__(self, main_plugin):
            super().__init__(
                orientation=main_plugin.gtk.Orientation.VERTICAL, spacing=6
            )
            self.main_plugin = main_plugin
            self.set_margin_top(10)
            self.set_margin_bottom(10)
            self.set_margin_start(10)
            self.set_margin_end(10)
            self.build_ui()

        def build_ui(self):
            """Builds the main popover content."""
            outputs = self.main_plugin.ipc.list_outputs()
            if not outputs:
                label = self.main_plugin.gtk.Label(label="No outputs detected.")
                self.append(label)
                return
            output_names = [output["name"] for output in outputs]
            record_all_btn = self.main_plugin.gtk.Button(label="Record All Outputs")
            record_all_btn.connect(
                "clicked",
                lambda x: self.main_plugin.global_loop.create_task(
                    logic.on_record_all_clicked(self.main_plugin)
                ),
            )
            record_all_btn.add_css_class("record-all-button")
            self.main_plugin.gtk_helper.add_cursor_effect(record_all_btn)
            self.append(record_all_btn)
            separator = self.main_plugin.gtk.Separator(
                orientation=self.main_plugin.gtk.Orientation.HORIZONTAL
            )
            self.append(separator)
            for name in output_names:
                btn = self.main_plugin.gtk.Button(label=f"Record Output: {name}")
                btn.connect(
                    "clicked",
                    lambda x, n=name: self.main_plugin.global_loop.create_task(
                        logic.on_record_output_clicked(self.main_plugin, n)
                    ),
                )
                btn.add_css_class("record-output-button")
                self.main_plugin.gtk_helper.add_cursor_effect(btn)
                self.append(btn)
            separator2 = self.main_plugin.gtk.Separator(
                orientation=self.main_plugin.gtk.Orientation.HORIZONTAL
            )
            self.append(separator2)
            slurp_btn = self.main_plugin.gtk.Button(label="Record Region (slurp)")
            slurp_btn.connect(
                "clicked",
                lambda x: self.main_plugin.global_loop.create_task(
                    logic.on_record_slurp_clicked(self.main_plugin)
                ),
            )
            slurp_btn.add_css_class("record-slurp-button")
            self.main_plugin.gtk_helper.add_cursor_effect(slurp_btn)
            self.append(slurp_btn)
            audio_switch_box = self.main_plugin.gtk.Box(
                orientation=self.main_plugin.gtk.Orientation.HORIZONTAL, spacing=10
            )
            audio_switch_label = self.main_plugin.gtk.Label(label="Record Audio:")
            audio_switch_label.set_halign(self.main_plugin.gtk.Align.START)
            audio_switch_box.append(audio_switch_label)
            self.audio_switch = self.main_plugin.gtk.Switch()
            self.audio_switch.set_active(self.main_plugin.record_audio)
            self.audio_switch.connect(
                "state-set", self.main_plugin.on_audio_switch_toggled
            )
            audio_switch_box.append(self.audio_switch)
            self.append(audio_switch_box)
            separator3 = self.main_plugin.gtk.Separator(
                orientation=self.main_plugin.gtk.Orientation.HORIZONTAL
            )
            self.append(separator3)
            stop_join_btn = self.main_plugin.gtk.Button(label="Stop All & Join Videos")
            stop_join_btn.connect(
                "clicked",
                lambda x: self.main_plugin.global_loop.create_task(
                    logic.on_stop_and_join_clicked(self.main_plugin)
                ),
            )
            stop_join_btn.add_css_class("stop-join-button")
            self.main_plugin.gtk_helper.add_cursor_effect(stop_join_btn)
            self.append(stop_join_btn)

    class RecordingPlugin(BasePlugin):
        def __init__(self, panel_instance):
            super().__init__(panel_instance)
            setup_plugin_settings(self)

            self.popover = None
            self.button = None
            self.record_processes = []
            self.output_files = []
            self.video_dir = self.temp_dir_format.format(pid=self.os.getpid())
            self.final_dir = self._get_user_videos_dir()
            self.is_recording = False
            self.record_audio = self.get_plugin_setting(
                ["recording", "record_audio_default"], False
            )
            self._setup_directories()
            self.button = self.create_widget()
            self.main_widget = (self.button, "append")
            self.glib.idle_add(self.is_wf_recorder_running)

        def is_wf_recorder_running(self):
            try:
                pid = (
                    self.subprocess.check_output(["pgrep", "-x", "wf-recorder"])
                    .decode()
                    .strip()
                )
                self.notify_send(
                    "WF-recorder Process Found",
                    f"WF-recorder process found with the pid {pid}",
                    "view-process-system",
                )
            except self.subprocess.CalledProcessError:
                pass
            return False

        def _setup_directories(self):
            if self.os.path.exists(self.video_dir):
                try:
                    shutil.rmtree(self.video_dir)
                except Exception as e:
                    self.logger.exception(
                        f"Failed to remove temporary directory {self.video_dir}: {e}"
                    )
            try:
                self.os.makedirs(self.video_dir, exist_ok=True)
                self.os.makedirs(self.final_dir, exist_ok=True)
            except Exception as e:
                self.logger.exception(f"Failed to create necessary directories: {e}")

        def _get_user_videos_dir(self):
            try:
                user_dirs_file = self.os.path.expanduser("~/.config/user-dirs.dirs")
                if self.os.path.exists(user_dirs_file):
                    with open(user_dirs_file, "r") as f:
                        for line in f:
                            if line.startswith("XDG_VIDEOS_DIR"):
                                path = line.split("=")[1].strip().strip('"')
                                return self.os.path.expandvars(path)
            except Exception as e:
                self.logger.exception(f"Failed to read ~/.config/user-dirs.dirs: {e}")
            return self.os.path.join(
                self.os.path.expanduser("~"), self.videos_dir_fallback
            )

        def create_widget(self):
            button = self.gtk.Button()
            button.set_icon_name(
                self.gtk_helper.icon_exist(
                    self.main_icon_name,
                    self.main_icon_fallbacks,
                )
            )
            button.set_tooltip_text("Start/Stop Screen Recording")
            self.gtk_helper.add_cursor_effect(button)
            button.connect("clicked", self.open_popover)
            return button

        def open_popover(self, widget):
            if self.popover and self.popover.is_visible():
                self.popover.popdown()
            else:
                self.popover = self.create_popover(
                    parent_widget=self.button, closed_handler=self.popover_is_closed
                )
                popover_content = RecordingPopover(self)
                self.popover.set_child(popover_content)
                self.popover.popup()

        def popdown(self):
            if self.popover:
                self.popover.popdown()

        def popover_is_closed(self, popover):
            self.popover = None
            self.logger.info("Recording popover closed.")

        def on_audio_switch_toggled(self, switch, state):
            self.record_audio = state
            self.logger.info(f"Audio recording {'enabled' if state else 'disabled'}.")

    return RecordingPlugin
