def get_plugin_metadata(panel):
    """
    Define the plugin metadata and its position within the panel.

    Args:
        panel: The Waypanel instance.

    Returns:
        dict: Plugin configuration metadata.
    """
    id = "org.waypanel.plugin.ollama_native"
    default_container = "top-panel-systray"
    container, id = panel.config_handler.get_plugin_container(default_container, id)

    return {
        "id": id,
        "name": "Ollama Native",
        "version": "1.6.0",
        "enabled": False,
        "container": container,
        "index": 10,
        "deps": [],
        "description": "Native Ollama client with state management and context clearing.",
    }


def get_plugin_class():
    """
    Return the plugin class with deferred imports to maintain process isolation.
    """
    import json
    import subprocess
    import shutil
    import base64
    from typing import Optional, List, Any

    from gi.repository import GLib, Gtk, Gio
    import aiohttp

    from src.plugins.core._base import BasePlugin

    class OllamaNativePlugin(BasePlugin):
        """
        A senior-grade native asynchronous client for Ollama.

        This implementation manages the lifecycle of the Ollama process and
        provides a high-performance streaming interface with context reset capabilities.
        """

        def __init__(self, panel_instance: Any):
            """
            Initialize the plugin state and UI handles.
            """
            super().__init__(panel_instance)
            self.ollama_process: Optional[subprocess.Popen] = None
            self.is_serving: bool = False

            # Context State
            self.pending_image_b64: Optional[str] = None
            self.pending_text_context: Optional[str] = None
            self.attached_filename: Optional[str] = None

            # UI Handles
            self.text_buffer: Optional[Gtk.TextBuffer] = None
            self.scroll_window: Optional[Gtk.ScrolledWindow] = None
            self.serve_btn: Optional[Gtk.Button] = None
            self.status_label: Optional[Gtk.Label] = None
            self.entry: Optional[Gtk.Entry] = None

        def on_start(self) -> None:
            """
            Synchronize system state and construct the interface.
            """
            self._setup_ui()
            self._sync_process_state()

        def _setup_ui(self) -> None:
            """
            Construct the GTK interface using a Popover structure.
            """
            self.menu_button = Gtk.MenuButton()
            self.menu_button.set_icon_name("utilities-terminal-symbolic")
            self.menu_button.set_tooltip_text("Ollama Assistant")
            self.menu_button.add_css_class("flat")

            popover = Gtk.Popover()
            root_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            root_vbox.set_margin_end(10)
            root_vbox.set_size_request(450, 600)

            # Header: Server Control and Clear Button
            header_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            self.serve_btn = Gtk.Button(label="Start Ollama", hexpand=True)
            self.serve_btn.add_css_class("suggested-action")
            self.serve_btn.connect("clicked", self._on_toggle_server)
            header_hbox.append(self.serve_btn)

            clear_btn = Gtk.Button(icon_name="edit-clear-all-symbolic")
            clear_btn.set_tooltip_text("Clear Chat and Context")
            clear_btn.connect("clicked", self._on_clear_clicked)
            header_hbox.append(clear_btn)

            root_vbox.append(header_hbox)

            # Main Chat Area
            self.scroll_window = Gtk.ScrolledWindow()
            self.scroll_window.set_vexpand(True)
            view = Gtk.TextView(
                editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR
            )
            self.text_buffer = view.get_buffer()
            self.scroll_window.set_child(view)
            root_vbox.append(self.scroll_window)

            # Status and Context Notification
            self.status_label = Gtk.Label(label="")
            self.status_label.add_css_class("dim-label")
            root_vbox.append(self.status_label)

            # Footer: Input and Attachments
            input_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self.entry = Gtk.Entry(hexpand=True)
            self.entry.set_placeholder_text("Ask Ollama...")
            self.entry.connect("activate", self._on_prompt_sent)

            self.attach_btn = Gtk.Button(icon_name="mail-attachment-symbolic")
            self.attach_btn.connect("clicked", self._on_attach_file)

            input_hbox.append(self.attach_btn)
            input_hbox.append(self.entry)
            root_vbox.append(input_hbox)

            popover.set_child(root_vbox)
            self.menu_button.set_popover(popover)
            self.main_widget = (self.menu_button, "append")

        def _on_clear_clicked(self, _btn: Gtk.Button) -> None:
            """
            Reset the UI and purge any pending context buffers.
            """
            self.text_buffer.set_text("", 0)
            self.entry.set_text("")
            self.pending_image_b64 = None
            self.pending_text_context = None
            self.attached_filename = None
            self.status_label.set_label("")
            self.logger.info("Session context and UI buffer cleared.")

        def _sync_process_state(self) -> None:
            """
            Detect existing Ollama instances to synchronize the UI.
            """
            if shutil.which("pgrep"):
                res = subprocess.run(["pgrep", "ollama"], capture_output=True)
                if res.returncode == 0:
                    self.is_serving = True
                    self._update_button_ui(True)

        def _update_button_ui(self, active: bool) -> None:
            """
            Modify server button aesthetics based on running state.
            """
            if active:
                self.serve_btn.set_label("Started")
                self.serve_btn.remove_css_class("suggested-action")
                self.serve_btn.add_css_class("success")
            else:
                self.serve_btn.set_label("Start Ollama")
                self.serve_btn.remove_css_class("success")
                self.serve_btn.add_css_class("suggested-action")

        def _on_toggle_server(self, _btn: Gtk.Button) -> None:
            """
            Toggle the Ollama daemon subprocess.
            """
            if not self.is_serving:
                self.ollama_process = subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.is_serving = True
                self._update_button_ui(True)
            else:
                if self.ollama_process:
                    self.ollama_process.terminate()
                else:
                    subprocess.run(["pkill", "ollama"])
                self.is_serving = False
                self._update_button_ui(False)

        def _on_attach_file(self, _btn: Gtk.Button) -> None:
            """
            Trigger file selection for multimodal or text context injection.
            """
            dialog = Gtk.FileDialog.new()
            dialog.open(None, None, self._on_file_selected)

        def _on_file_selected(
            self, dialog: Gtk.FileDialog, result: Gio.AsyncResult
        ) -> None:
            """
            Process the selected file into the appropriate memory buffer.
            """
            try:
                file = dialog.open_finish(result)
                if not file:
                    return

                path = file.get_path()
                info = file.query_info(
                    "standard::content-type", Gio.FileQueryInfoFlags.NONE, None
                )
                mime = info.get_content_type()
                self.attached_filename = file.get_basename()

                if "image" in mime:
                    with open(path, "rb") as f:
                        self.pending_image_b64 = base64.b64encode(f.read()).decode(
                            "utf-8"
                        )
                        self.pending_text_context = None
                else:
                    with open(path, "r", encoding="utf-8") as f:
                        self.pending_text_context = f.read()
                        self.pending_image_b64 = None

                GLib.idle_add(
                    self.status_label.set_label, f"Context: {self.attached_filename}"
                )
            except Exception as e:
                self.logger.error(f"File ingestion failure: {e}")

        def _on_prompt_sent(self, entry: Gtk.Entry) -> None:
            """
            Dispatch the assembled payload to the Ollama endpoint.
            """
            query = entry.get_text().strip()
            if not query:
                return

            entry.set_text("")
            self._update_chat(f"\nUser: {query}\nOllama: ")

            final_prompt = query
            if self.pending_text_context:
                final_prompt = (
                    f"Context:\n{self.pending_text_context}\n\nQuestion: {query}"
                )

            images = [self.pending_image_b64] if self.pending_image_b64 else []
            self.run_in_async_task(self._stream_inference(final_prompt, images))

            # Post-send cleanup
            self.pending_text_context = None
            self.pending_image_b64 = None
            self.status_label.set_label("")

        async def _stream_inference(self, prompt: str, images: List[str]) -> None:
            """
            Perform native aiohttp streaming to retrieve LLM tokens.
            """
            url = "http://127.0.0.1:11434/api/generate"
            payload = {
                "model": "devstral-small-2:latest"
                if not images
                else "devstral-small-2:latest",
                "prompt": prompt,
                "stream": True,
                "images": images,
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as response:
                        if response.status != 200:
                            err = await response.text()
                            GLib.idle_add(self._update_chat, f"\n[Error: {err}]\n")
                            return

                        async for line in response.content:
                            if not line:
                                continue
                            try:
                                data = json.loads(line.decode("utf-8"))
                                if chunk := data.get("response"):
                                    GLib.idle_add(self._update_chat, chunk)
                                if data.get("done"):
                                    break
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                GLib.idle_add(self._update_chat, f"\n[Native Connection Error: {e}]\n")

        def _update_chat(self, text: str) -> bool:
            """
            Update the Gtk.TextView in a thread-safe manner.
            """
            end_iter = self.text_buffer.get_end_iter()
            self.text_buffer.insert(end_iter, text)
            adj = self.scroll_window.get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())
            return False

        def on_stop(self) -> None:
            """
            Cleanup resources and subprocesses.
            """
            if self.ollama_process:
                self.ollama_process.terminate()

    return OllamaNativePlugin
