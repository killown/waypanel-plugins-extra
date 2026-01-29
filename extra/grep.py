def get_plugin_metadata(_):
    """
    Define the plugin metadata for the File Content Searcher.
    """
    return {
        "id": "org.waypanel.plugin.file_content_searcher",
        "name": "File Content Searcher",
        "version": "2.1.0",
        "enabled": True,
        "index": 5,
        "container": "right-panel-center",
        "description": "Recursive source code search with folder-named Markdown output and persistent path selection.",
    }


def get_plugin_class():
    """
    Main plugin class with folder-aware naming, source-restricted search, and persistent state.
    """
    import os
    import mmap
    import tempfile
    import subprocess
    from src.plugins.core._base import BasePlugin

    class FileContentSearcher(BasePlugin):
        def __init__(self, panel_instance):
            super().__init__(panel_instance)
            self.search_paths = self.get_plugin_setting_add_hint(
                ["behavior", "search_paths"],
                [
                    os.path.expanduser("~/Git/wayfire"),
                    os.path.expanduser("~/Documents"),
                ],
                "A list of absolute paths available for searching.",
            )
            self.last_path = self.get_plugin_setting(
                ["behavior", "last_selected_path"], ""
            )

            self.popover_width = 400
            self.popover_height = 360
            self.found_files = []

            self.menu_button = self.gtk.Button()
            self.menu_button.set_icon_name("system-search-symbolic")
            self.gtk_helper.add_cursor_effect(self.menu_button)
            self.popover = None

            self.programming_extensions = {
                ".py": "python",
                ".c": "c",
                ".cpp": "cpp",
                ".h": "cpp",
                ".hpp": "cpp",
                ".js": "javascript",
                ".ts": "typescript",
                ".lua": "lua",
                ".rs": "rust",
                ".go": "go",
                ".rb": "ruby",
                ".php": "php",
                ".java": "java",
                ".cs": "csharp",
                ".sh": "bash",
                ".vert": "glsl",
                ".frag": "glsl",
                ".geom": "glsl",
                ".comp": "glsl",
                ".glsl": "glsl",
                ".ini": "ini",
                ".conf": "ini",
                ".md": "markdown",
            }
            self.ignored_dirs = {
                "build",
                ".git",
                "__pycache__",
                "node_modules",
                ".venv",
                "target",
            }

        def on_start(self):
            """
            Initialize UI and signals.
            """
            self.main_widget = (self.menu_button, "append")
            self._setup_popover()
            self.menu_button.connect("clicked", self._toggle_popover)

        def _setup_popover(self):
            """
            Create the search interface with directory selection and persistent state.
            """
            self.popover = self.create_popover(
                parent_widget=self.menu_button,
                css_class="file-searcher-popover",
                has_arrow=True,
            )

            main_box = self.gtk.Box.new(self.gtk.Orientation.VERTICAL, 10)
            main_box.set_margin_end(10)
            main_box.set_size_request(self.popover_width, self.popover_height)

            dir_label = self.gtk.Label.new("Search in:")
            dir_label.set_halign(self.gtk.Align.START)
            main_box.append(dir_label)

            self.dir_combo = self.gtk.ComboBoxText()
            active_index = 0
            for idx, path in enumerate(self.search_paths):
                self.dir_combo.append_text(path)
                if path == self.last_path:
                    active_index = idx

            if self.search_paths:
                self.dir_combo.set_active(active_index)

            self.dir_combo.connect("changed", self._on_dir_changed)
            main_box.append(self.dir_combo)

            self.search_entry = self.gtk.SearchEntry()
            self.search_entry.set_placeholder_text("Search source code...")
            self.search_entry.connect("activate", self._on_search_triggered)
            main_box.append(self.search_entry)

            self.trigger_button = self.gtk.Button.new_with_label("Search Now")
            self.trigger_button.add_css_class("suggested-action")
            self.trigger_button.connect("clicked", self._on_search_triggered)
            main_box.append(self.trigger_button)

            self.status_label = self.gtk.Label.new("Status: Ready")
            self.status_label.add_css_class("dim-label")
            main_box.append(self.status_label)

            self.combine_button = self.gtk.Button.new_with_label(
                "Combine & Copy Markdown"
            )
            self.combine_button.set_sensitive(False)
            self.combine_button.connect("clicked", self._on_combine_clicked)
            main_box.append(self.combine_button)

            self.popover.set_child(main_box)

        def _on_dir_changed(self, combo):
            """
            Update the persistent setting when the user selects a new directory.
            """
            selected = combo.get_active_text()
            if selected:
                self.set_plugin_setting(["behavior", "last_selected_path"], selected)

        def _toggle_popover(self, *_):
            if self.popover.is_visible():
                self.popover.popdown()
            else:
                self.popover.popup()
                self.search_entry.grab_focus()

        def _fast_grep(self, file_path, query_bytes):
            """
            Optimized search for source files only using mmap.
            """
            try:
                _, ext = os.path.splitext(file_path)
                if ext.lower() not in self.programming_extensions:
                    return False

                file_size = os.path.getsize(file_path)
                if file_size == 0:
                    return False

                with open(file_path, "rb") as f:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        return mm.find(query_bytes) != -1
            except Exception:
                return False

        def _on_search_triggered(self, *_):
            """
            Recursive grep in selected folder.
            """
            query = self.search_entry.get_text().strip()
            selected_path = self.dir_combo.get_active_text()

            if not query or not selected_path:
                return

            self.status_label.set_text("Status: Searching...")
            query_bytes = query.encode("utf-8")
            self.found_files = []
            target_dir = os.path.expanduser(selected_path)

            if not os.path.isdir(target_dir):
                self.status_label.set_text("Error: Directory not found")
                return

            try:
                for root, dirs, files in os.walk(target_dir):
                    dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
                    for file in files:
                        full_path = os.path.join(root, file)
                        if self._fast_grep(full_path, query_bytes):
                            self.found_files.append(full_path)

                count = len(self.found_files)
                self.status_label.set_text(f"Status: Found {count} source files.")
                self.combine_button.set_sensitive(count > 0)
            except Exception as e:
                self.logger.error(f"Search error: {e}")

        def _on_combine_clicked(self, _):
            """
            Combines text from matches into a Markdown file named after the folder.
            """
            selected_path = self.dir_combo.get_active_text()
            if not self.found_files or not selected_path:
                return

            try:
                folder_name = os.path.basename(os.path.normpath(selected_path))
                if not folder_name:
                    folder_name = "root"

                filename = f"{folder_name}.md"
                temp_path = os.path.join(tempfile.gettempdir(), filename)

                with open(temp_path, "w", encoding="utf-8") as outfile:
                    outfile.write(
                        f"# Search Results for: {self.search_entry.get_text()}\n"
                    )
                    outfile.write(f"**Source Folder:** `{selected_path}`\n\n")

                    for fpath in self.found_files:
                        _, ext = os.path.splitext(fpath)
                        lang = self.programming_extensions.get(ext.lower(), "")

                        outfile.write(f"## File: `{fpath}`\n\n")
                        outfile.write(f"```{lang}\n")
                        with open(fpath, "r", errors="ignore") as infile:
                            outfile.write(infile.read())
                        outfile.write("\n```\n\n---\n\n")

                self._wl_copy_uri(temp_path)
                self.status_label.set_text(f"Success: Copied {filename}")
                self.popover.popdown()
            except Exception as e:
                self.logger.error(f"Combine error: {e}")

        def _wl_copy_uri(self, file_path):
            """
            Copy the combined file reference using wl-copy.
            """
            try:
                uri = f"file://{file_path}\n"
                subprocess.run(
                    ["wl-copy", "--type", "text/uri-list"],
                    input=uri.encode("utf-8"),
                    check=True,
                )
            except Exception as e:
                self.logger.error(f"wl-copy failed: {e}")

        def on_stop(self):
            if self.popover:
                self.popover.unparent()

    return FileContentSearcher
