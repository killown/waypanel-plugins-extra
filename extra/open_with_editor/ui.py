# ==== FILE: ui.py ====


def get_ui_factory():
    import os
    from gi.repository import Gdk, Gio

    class UIFactory:
        def __init__(self, plugin):
            self.p = plugin

        def create_menu_button(self):
            self.menubutton = self.p.gtk.Button()
            self.menubutton.connect("clicked", self.p.open_popover)
            icon = self.p.gtk_helper.set_widget_icon_name(
                "text-editor-symbolic",
                ["text-editor-symbolic", "org.gnome.gedit-symbolic"],
            )
            self.menubutton.set_icon_name(icon)
            self.menubutton.add_css_class("openwitheditor-menu-button")
            self.p.gtk_helper.add_cursor_effect(self.menubutton)

        def create_popover(self):
            self.p.popover_openwitheditor = self.p.create_popover(
                parent_widget=self.menubutton,
                css_class="openwitheditor-popover",
                closed_handler=self.on_closed,
                visible_handler=self.on_open,
            )

            box = self.p.gtk.Box.new(self.p.gtk.Orientation.VERTICAL, 0)
            box.add_css_class("openwitheditor-main-box")

            self.p.stack = self.p.gtk.Stack.new()
            self.p.stack.add_css_class("openwitheditor-stack")
            self.p.stack.connect("notify::visible-child-name", self.on_open)

            switcher = self.p.gtk.StackSwitcher.new()
            switcher.set_stack(self.p.stack)
            switcher.add_css_class("openwitheditor-stack-switcher")

            box.append(switcher)
            box.append(self.p.stack)

            # Context Menu initialized as Popover
            self.ctx_menu = self.p.gtk.Popover()
            self.ctx_menu.add_css_class("openwitheditor-context-menu")
            self.ctx_menu.set_autohide(True)

            for name, path in self.p.config_maps.items():
                page = self.p.gtk.Box.new(self.p.gtk.Orientation.VERTICAL, 0)
                page.add_css_class("openwitheditor-page-box")

                search_entry = self.p.gtk.SearchEntry.new()
                search_entry.add_css_class("openwitheditor-search-entry")
                search_entry.connect("search-changed", self.on_search_changed)
                search_entry.connect("activate", self.on_search_activated)

                key_controller = self.p.gtk.EventControllerKey.new()
                key_controller.connect("key-pressed", self.on_key_pressed)
                search_entry.add_controller(key_controller)

                scrolled = self.p.gtk.ScrolledWindow.new()
                scrolled.add_css_class("openwitheditor-scrolled-window")
                scrolled.set_policy(
                    self.p.gtk.PolicyType.NEVER, self.p.gtk.PolicyType.AUTOMATIC
                )
                scrolled.set_propagate_natural_height(True)
                scrolled.set_min_content_height(350)
                scrolled.set_max_content_height(600)

                listbox = self.p.gtk.ListBox.new()
                listbox.add_css_class("openwitheditor-listbox")
                listbox.connect("row-activated", self.on_activated)

                scrolled.set_child(listbox)
                page.append(search_entry)
                page.append(scrolled)

                self.p.stack.add_titled(page, name, name)
                self.p.listbox_widgets[name] = listbox
                self.p.searchbar_widgets[name] = search_entry

            self.p.popover_openwitheditor.set_child(box)

        def on_open(self, *_):
            self.p.layer_shell.set_keyboard_mode(
                self.p.obj.top_panel, self.p.layer_shell.KeyboardMode.ON_DEMAND
            )

            def _deferred_load():
                name = self.p.stack.get_visible_child_name()
                if not name or name not in self.p.config_maps:
                    name = next(iter(self.p.config_maps))
                    self.p.stack.set_visible_child_name(name)

                self.p.active_dir_name = name
                active_path = self.p.config_maps[name]
                self.p.active_listbox = self.p.listbox_widgets[name]
                self.p.active_searchbar = self.p.searchbar_widgets[name]
                self.p.active_searchbar.grab_focus()

                files = self.p.scanner.get_files(active_path)
                while child_row := self.p.active_listbox.get_first_child():
                    self.p.active_listbox.remove(child_row)

                for f in files:
                    row_content = self._create_row(f, active_path)
                    row = self.p.gtk.ListBoxRow.new()
                    row.set_child(row_content)

                    gesture = self.p.gtk.GestureClick.new()
                    gesture.set_button(0)
                    gesture.connect(
                        "pressed",
                        lambda g, n, x, y, r=row: self.on_click(g, n, x, y, r),
                    )
                    row.add_controller(gesture)
                    self.p.active_listbox.append(row)

                self.p.active_listbox.set_filter_func(self.filter_func)
                self._select_first_visible()
                return False

            self.p.glib.timeout_add(50, _deferred_load)

        def _create_row(self, path, base_dir):
            row_hbox = self.p.gtk.Box.new(self.p.gtk.Orientation.HORIZONTAL, 0)
            row_hbox.add_css_class("openwitheditor-row-hbox")
            row_hbox.MYTEXT = path

            content_type = Gio.content_type_guess(path, None)[0]
            icon = Gio.content_type_get_icon(content_type)
            image = self.p.gtk.Image.new_from_gicon(icon)
            image.add_css_class("openwitheditor-icon-from-popover")

            label = self.p.gtk.Label.new(os.path.relpath(path, base_dir))
            label.add_css_class("openwitheditor-label-from-popover")
            label.set_halign(self.p.gtk.Align.START)

            row_hbox.append(image)
            row_hbox.append(label)
            return row_hbox

        def on_click(self, gesture, n_press, x, y, row):
            btn = gesture.get_current_button()
            file_path = row.get_child().MYTEXT
            if btn == 3:
                self._show_context_menu(row, x, y, file_path)
            elif btn == 1:
                self.p.launcher.open_file(file_path, 0)

        def _show_context_menu(self, anchor, x, y, file_path):
            # Taskbar Pattern: Use .popup() instead of .present()
            if self.ctx_menu.get_parent():
                self.ctx_menu.unparent()

            box = self.p.gtk.Box.new(self.p.gtk.Orientation.VERTICAL, 0)
            box.add_css_class("openwitheditor-context-box")

            actions = [
                (
                    "Secondary Editor",
                    lambda: self.p.launcher.open_file(file_path, index=1),
                ),
                (
                    "Open Folder",
                    lambda: self.p.launcher.open_file(
                        os.path.dirname(file_path), is_dir=True
                    ),
                ),
                (
                    "Copy Context (Text)",
                    lambda: self.p.launcher.copy_directory_context(file_path, False),
                ),
                (
                    "Copy Context (File)",
                    lambda: self.p.launcher.copy_directory_context(file_path, True),
                ),
            ]

            for label, func in actions:
                item = self.p.gtk.Button(label=label)
                item.set_has_frame(False)
                item.set_halign(self.p.gtk.Align.START)
                item.connect(
                    "clicked", lambda _, f=func: [f(), self.ctx_menu.popdown()]
                )
                box.append(item)

            self.ctx_menu.set_parent(anchor)
            self.ctx_menu.set_child(box)

            rect = Gdk.Rectangle()
            rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
            self.ctx_menu.set_pointing_to(rect)

            # Taskbar implementation uses .popup()
            self.ctx_menu.popup()

        def on_search_changed(self, entry):
            self.p.active_listbox.invalidate_filter()
            self.p.glib.idle_add(self._select_first_visible)

        def _select_first_visible(self):
            child = self.p.active_listbox.get_first_child()
            while child:
                if child.is_visible():
                    self.p.active_listbox.select_row(child)
                    break
                child = child.get_next_sibling()

        def filter_func(self, row):
            query = self.p.active_searchbar.get_text().lower()
            return not query or query in row.get_child().MYTEXT.lower()

        def on_search_activated(self, entry):
            selected = self.p.active_listbox.get_selected_row()
            if selected and selected.is_visible():
                self.on_activated(self.p.active_listbox, selected)

        def on_activated(self, lb, row):
            if row:
                self.p.launcher.open_file(row.get_child().MYTEXT, 0)

        def on_closed(self, *_):
            self.p.layer_shell.set_keyboard_mode(
                self.p.obj.top_panel, self.p.layer_shell.KeyboardMode.NONE
            )

        def on_key_pressed(self, controller, keyval, keycode, state):
            from gi.repository import Gdk

            if keyval == Gdk.KEY_Up:
                row = self.p.active_listbox.get_selected_row()
                self._select_visible_row((row.get_index() if row else 0) - 1, True)
                return True
            elif keyval == Gdk.KEY_Down:
                row = self.p.active_listbox.get_selected_row()
                self._select_visible_row((row.get_index() if row else -1) + 1, False)
                return True
            return False

        def _select_visible_row(self, start_index, reverse):
            while True:
                row = self.p.active_listbox.get_row_at_index(start_index)
                if not row:
                    break
                if row.is_visible():
                    self.p.active_listbox.select_row(row)
                    self.p.active_searchbar.grab_focus()
                    break
                start_index = start_index - 1 if reverse else start_index + 1

    return UIFactory
