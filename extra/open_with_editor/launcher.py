def get_launcher_logic():
    import os
    import tempfile

    class FileLauncher:
        def __init__(self, plugin):
            self.p = plugin
            self.tui_editors = ["nvim", "vi", "vim", "emacs", "nano", "micro", "ed"]

        def init_config(self):
            raw_dirs = self.p.get_plugin_setting(
                ["directories"], {"nvim": "~/.config/nvim"}
            )
            self.p.config_maps = {k: os.path.expanduser(v) for k, v in raw_dirs.items()}
            self.p.active_dir_name = next(iter(self.p.config_maps))
            self.p.config_dir = self.p.config_maps[self.p.active_dir_name]

            self.p.editor_extensions = self.p.get_plugin_setting(
                ["extensions"],
                {
                    "py": ["nvim", "code"],
                    "lua": ["nvim", "code"],
                    "js": ["code", "nvim"],
                },
            )

            self.p.terminal_emulators = self.p.get_plugin_setting(
                ["terminal_emulators"],
                ["kitty", "alacritty", "gnome-terminal", "xterm"],
            )

        def copy_directory_context(self, clicked_file_path, as_file=False):
            """Aggregates files into /tmp/ and copies via wl-copy."""
            root_dir = os.path.dirname(clicked_file_path)
            context_output = []
            files = self.p.scanner.get_files(root_dir)

            for f_path in files:
                try:
                    with open(f_path, "rb") as f:
                        if b"\x00" in f.read(1024):
                            continue
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    header = f"# ==== FILE: {f_path} ====\n"
                    footer = f"\n# ==== END OF FILE: {f_path} ====\n\n"
                    context_output.append(f"{header}{content}{footer}")
                except:
                    continue

            if not context_output:
                return
            final_text = "".join(context_output)

            # Create temporary file
            try:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".txt", prefix="waypanel_ctx_"
                ) as tmp:
                    tmp.write(final_text.encode("utf-8"))
                    tmp_path = tmp.name
            except Exception as e:
                self.p.logger.error(f"Tmp file error: {e}")
                return

            # Clipboard via wl-copy (Wayland native)
            if as_file:
                # Copy as a URI list for file managers
                self.p.run_cmd(f"wl-copy --type text/uri-list 'file://{tmp_path}'")
            else:
                # Copy as raw text
                self.p.run_cmd(f"wl-copy '{final_text}'")

            # Clipboard Plugin Sync
            cb_id = "org.waypanel.plugin.clipboard"
            clipboard_plugin = self.p.plugins.get(cb_id)
            if clipboard_plugin and hasattr(clipboard_plugin, "manager"):
                self.p.run_in_async_task(
                    clipboard_plugin.manager.server.add_item(final_text)
                )

        def open_file(self, file_path, index=0, is_dir=False):
            if not file_path:
                return
            editor = "nvim" if is_dir else self._get_editor(file_path, index)
            is_tui = editor in self.tui_editors
            success = False
            if is_tui:
                title = f"Waypanel Editor: {editor} {os.path.basename(file_path)}"
                cmd_str = f"{editor} {file_path}"
                for term in self.p.terminal_emulators:
                    if term in ["gnome-terminal", "terminator", "tilix"]:
                        cmd = f'{term} --title="{title}" -- /bin/sh -c "{cmd_str}"'
                    elif term in ["xfce4-terminal", "lxterminal"]:
                        cmd = f'{term} --title="{title}" --command "{cmd_str}"'
                    else:
                        cmd = f'{term} -T "{title}" -e {cmd_str}'
                    try:
                        self.p.run_cmd(cmd)
                        success = True
                        break
                    except:
                        continue
            else:
                try:
                    self.p.run_cmd(f"{editor} {file_path}")
                    success = True
                except:
                    pass

            if success and self.p.popover_openwitheditor:
                self.p.popover_openwitheditor.popdown()

        def _get_editor(self, path, index):
            ext = path.split(".")[-1].lower() if "." in path else ""
            val = self.p.editor_extensions.get(ext, ["nvim", "code"])
            editors = (
                [e.strip() for e in val]
                if isinstance(val, list)
                else [e.strip() for e in val.split(",")]
            )
            return editors[index] if index < len(editors) else editors[0]

    return FileLauncher
