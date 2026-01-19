def get_ui_factory():
    import os

    class UIFactory:
        def __init__(self, plugin):
            self.p = plugin

        def create_menu_button(self):
            self.p.layer_shell.set_keyboard_mode(
                self.p.obj.top_panel, self.p.layer_shell.KeyboardMode.ON_DEMAND
            )
            self.menubutton = self.p.gtk.Button()
            self.menubutton.connect("clicked", self.p.open_popover)
            icon = self.p.gtk_helper.set_widget_icon_name(
                "documentation-symbolic", ["documentation-symbolic"]
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
            self.p.stack.set_transition_type(
                self.p.gtk.StackTransitionType.SLIDE_LEFT_RIGHT
            )

            switcher = self.p.gtk.StackSwitcher.new()
            switcher.set_stack(self.p.stack)

            for name in self.p.config_maps:
                page = self._build_page(name)
                self.p.stack.add_titled(page, name, name)

            self.p.stack.connect("notify::visible-child", self.on_tab_switched)
            box.append(switcher)
            box.append(self.p.stack)
            self.p.popover_openwitheditor.set_child(box)

            self._sync_active()
            self._populate()
            self.p.popover_openwitheditor.popup()

        def _build_page(self, name):
            box = self.p.gtk.Box.new(self.p.gtk.Orientation.VERTICAL, 0)
            entry = self.p.gtk.SearchEntry.new()
            entry.connect("search_changed", self.on_search_changed)

            listbox = self.p.gtk.ListBox.new()
            listbox.connect("row-activated", self.on_activated)

            scroll = self.p.gtk.ScrolledWindow()
            scroll.set_min_content_width(800)
            scroll.set_min_content_height(600)
            scroll.set_child(listbox)

            box.append(entry)
            box.append(scroll)
            self.p.searchbar_widgets[name] = entry
            self.p.listbox_widgets[name] = listbox
            return box

        def on_tab_switched(self, stack, _):
            self._sync_active()
            if self.p.active_listbox.get_row_at_index(0) is None:
                self._populate()
            self.p.active_searchbar.grab_focus()

        def _sync_active(self):
            name = self.p.stack.get_visible_child_name()
            self.p.active_dir_name = name
            self.p.config_dir = self.p.config_maps[name]
            self.p.active_listbox = self.p.listbox_widgets[name]
            self.p.active_searchbar = self.p.searchbar_widgets[name]

        def _populate(self):
            files = self.p.scanner.get_files(self.p.config_dir)
            for f in files:
                row = self._create_row(f)
                gesture = self.p.gtk.GestureClick.new()
                gesture.connect("pressed", self.on_click, row)
                row.add_controller(gesture)
                self.p.active_listbox.append(row)
            self.p.active_listbox.set_filter_func(self.filter_func)

        def _create_row(self, path):
            box = self.p.gtk.Box.new(self.p.gtk.Orientation.HORIZONTAL, 0)
            box.MYTEXT = path
            label = self.p.gtk.Label.new(os.path.relpath(path, self.p.config_dir))
            label.set_halign(self.p.gtk.Align.START)
            box.append(label)
            return box

        def on_click(self, gesture, _, x, y, row):
            btn = gesture.get_current_button()
            if btn == 3:
                self.p.launcher.open_file(os.path.dirname(row.MYTEXT), is_dir=True)
            else:
                self.p.launcher.open_file(row.MYTEXT, index=btn - 1)

        def on_activated(self, lb, row):
            self.p.launcher.open_file(row.get_child().MYTEXT, 0)

        def on_search_changed(self, entry):
            self.p.active_listbox.invalidate_filter()

        def filter_func(self, row):
            query = self.p.active_searchbar.get_text().lower()
            return query in row.get_child().MYTEXT.lower()

        def on_open(self, *_):
            self.p.active_searchbar.grab_focus()

        def on_closed(self, *_):
            self.p.set_keyboard_on_demand(False)

    return UIFactory
