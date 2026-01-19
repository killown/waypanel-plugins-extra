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
            self.p.stack.add_css_class("openwitheditor-stack")

            switcher = self.p.gtk.StackSwitcher.new()
            switcher.set_stack(self.p.stack)
            switcher.add_css_class("openwitheditor-stack-switcher")

            box.append(switcher)
            box.append(self.p.stack)

            for name, path in self.p.config_maps.items():
                page = self.p.gtk.Box.new(self.p.gtk.Orientation.VERTICAL, 0)
                page.add_css_class("openwitheditor-page-box")

                search_entry = self.p.gtk.SearchEntry.new()
                search_entry.add_css_class("openwitheditor-search-entry")
                search_entry.connect("search-changed", self.on_search_changed)

                scrolled = self.p.gtk.ScrolledWindow.new()
                scrolled.add_css_class("openwitheditor-scrolled-window")
                scrolled.set_policy(
                    self.p.gtk.PolicyType.NEVER, self.p.gtk.PolicyType.AUTOMATIC
                )

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
            self.p.active_dir_name = self.p.stack.get_visible_child_name()
            self.p.config_dir = self.p.config_maps[self.p.active_dir_name]
            self.p.active_listbox = self.p.listbox_widgets[self.p.active_dir_name]
            self.p.active_searchbar = self.p.searchbar_widgets[self.p.active_dir_name]

            files = self.p.scanner.get_files(self.p.config_dir)

            while child := self.p.active_listbox.get_first_child():
                self.p.active_listbox.remove(child)

            for f in files:
                row_content = self._create_row(f)
                row = self.p.gtk.ListBoxRow.new()
                row.set_child(row_content)

                gesture = self.p.gtk.GestureClick.new()
                gesture.set_button(0)
                gesture.connect("pressed", self.on_click, row_content)
                row.add_controller(gesture)

                self.p.active_listbox.append(row)

            self.p.active_listbox.set_filter_func(self.filter_func)

        def _create_row(self, path):
            row_hbox = self.p.gtk.Box.new(self.p.gtk.Orientation.HORIZONTAL, 0)
            row_hbox.add_css_class("openwitheditor-row-hbox")
            row_hbox.MYTEXT = path

            icon = self.p.gtk.Image.new_from_icon_name("text-x-generic-symbolic")
            icon.add_css_class("openwitheditor-icon-from-popover")

            label = self.p.gtk.Label.new(os.path.relpath(path, self.p.config_dir))
            label.add_css_class("openwitheditor-label-from-popover")
            label.set_halign(self.p.gtk.Align.START)

            row_hbox.append(icon)
            row_hbox.append(label)
            return row_hbox

        def on_closed(self, *_):
            pass

        def on_click(self, gesture, _, x, y, row_content):
            btn = gesture.get_current_button()
            if btn == 3:
                self.p.launcher.open_file(
                    os.path.dirname(row_content.MYTEXT), is_dir=True
                )
            else:
                self.p.launcher.open_file(row_content.MYTEXT, index=btn - 1)

        def on_activated(self, lb, row):
            self.p.launcher.open_file(row.get_child().MYTEXT, 0)

        def on_search_changed(self, entry):
            self.p.active_listbox.invalidate_filter()

        def filter_func(self, row):
            query = self.p.active_searchbar.get_text().lower()
            if not query:
                return True
            return query in row.get_child().MYTEXT.lower()

    return UIFactory
