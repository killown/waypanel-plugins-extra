"""GTK Manager for Window Rules UI."""

from .template import (
    MATCH_KEYS,
    EVENT_LIST,
    ACTION_LIST,
    ROLES,
    TYPES,
    PARENT_STATES,
    SLOTS,
    EVENT_HINTS,
    ACTION_HINTS,
)


class RuleManager:
    def __init__(self, plugin):
        self.p = plugin
        self.window = None
        self.list_box = None
        self.search_entry = None

    def _create_dropdown_with_hints(self, items, hint_map):
        """Internal helper to build dropdowns with item tooltips."""
        model = self.p.gtk.StringList.new(items)
        factory = self.p.gtk.SignalListItemFactory()
        factory.connect("setup", lambda f, i: i.set_child(self.p.gtk.Label(xalign=0)))
        factory.connect(
            "bind",
            lambda f, i: (
                i.get_child().set_text(i.get_item().get_string()),
                i.get_child().set_tooltip_text(
                    hint_map.get(i.get_item().get_string(), "")
                ),
            ),
        )
        return self.p.gtk.DropDown(model=model, factory=factory)

    def open(self):
        if self.window:
            self.window.present()
            return

        self.window = self.p.gtk.Window(title="Window Rules")
        self.window.set_default_size(1400, 750)

        header = self.p.gtk.HeaderBar()
        self.window.set_titlebar(header)

        # Search Bar
        self.search_entry = self.p.gtk.SearchEntry(placeholder_text="Filter rules...")
        self.search_entry.set_width_chars(30)
        self.search_entry.connect("search-changed", self._on_search_changed)
        header.set_title_widget(self.search_entry)

        add_btn = self.p.gtk.Button(icon_name="list-add-symbolic")
        add_btn.set_tooltip_text("Create a new manual rule")
        add_btn.connect("clicked", lambda _: self.add_row())
        header.pack_start(add_btn)

        capture_btn = self.p.gtk.Button(icon_name="camera-photo-symbolic")
        capture_btn.set_tooltip_text("Capture properties from currently focused window")
        capture_btn.connect("clicked", lambda _: self.capture_focused())
        header.pack_start(capture_btn)

        save_btn = self.p.gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _: self.save())
        header.pack_end(save_btn)

        scrolled = self.p.gtk.ScrolledWindow()
        self.list_box = self.p.gtk.ListBox()
        self.list_box.set_selection_mode(self.p.gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")

        for m in ["start", "end", "top", "bottom"]:
            getattr(self.list_box, f"set_margin_{m}")(20)

        scrolled.set_child(self.list_box)
        self.window.set_child(scrolled)

        self.refresh_ui()
        self.window.connect("close-request", self._on_close)
        self.window.present()

    def _on_search_changed(self, entry):
        search_text = entry.get_text().lower()
        row = self.list_box.get_first_child()
        while row:
            # Get the match value from the second widget in the box
            inner_box = row.get_child().get_first_child()
            match_val_widget = inner_box.get_first_child().get_next_sibling()
            val = self._get_val(match_val_widget).lower()

            row.set_visible(search_text in val if search_text else True)
            row = row.get_next_sibling()

    def capture_focused(self):
        view = self.p.wf_helper.get_most_recent_focused_view()
        if not view:
            return
        self.add_row(
            {
                "match_key": "app-id",
                "match_value": view.get("app-id", ""),
                "event": "view-mapped",
                "timeout": 0,
                "action": "center",
                "value": "",
            }
        )

    def add_row(self, data=None):
        row_container = self.p.gtk.Box(
            orientation=self.p.gtk.Orientation.VERTICAL, spacing=4
        )
        row_container.set_margin_top(8)
        row_container.set_margin_bottom(8)
        row = self.p.gtk.Box(spacing=10)

        match_key_drop = self.p.gtk.DropDown.new_from_strings(MATCH_KEYS)
        match_val_wrapper = self.p.gtk.Box(hexpand=True)
        event_drop = self._create_dropdown_with_hints(EVENT_LIST, EVENT_HINTS)

        timeout_adj = self.p.gtk.Adjustment.new(0, 0, 10000, 50, 500, 0)
        timeout_spin = self.p.gtk.SpinButton(adjustment=timeout_adj, numeric=True)
        timeout_spin.set_tooltip_text(
            "Milliseconds to wait after event before firing action"
        )

        action_drop = self._create_dropdown_with_hints(ACTION_LIST, ACTION_HINTS)
        value_wrapper = self.p.gtk.Box(spacing=6)
        value_wrapper.set_size_request(250, -1)

        def update_match_value_widget(key, initial_val=None):
            if child := match_val_wrapper.get_first_child():
                while child:
                    next_c = child.get_next_sibling()
                    match_val_wrapper.remove(child)
                    child = next_c

            if key == "app-id":
                views = self.p.ipc.list_views() or []
                app_ids = sorted(
                    list(set(v.get("app-id") for v in views if v.get("app-id")))
                )[:100]
                widget = self.p.gtk.ComboBoxText.new_with_entry()
                for aid in app_ids:
                    widget.append_text(aid)
                if initial_val:
                    widget.get_child().set_text(str(initial_val))
                match_val_wrapper.append(widget)
            elif key == "output-name":
                outputs = [o.get("name") for o in self.p.ipc.list_outputs() or []]
                widget = self.p.gtk.DropDown.new_from_strings(outputs)
                if initial_val and initial_val in outputs:
                    widget.set_selected(outputs.index(initial_val))
                match_val_wrapper.append(widget)
            elif key == "parent":
                widget = self.p.gtk.DropDown.new_from_strings(PARENT_STATES)
                if initial_val == "Dialog or Popup":
                    widget.set_selected(1)
                match_val_wrapper.append(widget)
            else:
                widget = self.p.gtk.Entry(placeholder_text="Value...", hexpand=True)
                if initial_val:
                    widget.set_text(str(initial_val))
                match_val_wrapper.append(widget)

        def update_action_value_widget(action_name, initial_val=None):
            if child := value_wrapper.get_first_child():
                while child:
                    next_c = child.get_next_sibling()
                    value_wrapper.remove(child)
                    child = next_c

            if action_name in ["maximize", "center", "center_cursor", "set_focus"]:
                value_wrapper.set_visible(False)
                return

            value_wrapper.set_visible(True)
            if action_name in ["fullscreen", "set_minimized"]:
                widget = self.p.gtk.Switch()
                widget.set_valign(self.p.gtk.Align.CENTER)
                if initial_val is not None:
                    widget.set_active(str(initial_val).lower() == "true")
                value_wrapper.append(widget)
            elif action_name == "move_to_output":
                outputs = [o.get("name") for o in self.p.ipc.list_outputs() or []]
                widget = self.p.gtk.DropDown.new_from_strings(outputs)
                if initial_val and initial_val in outputs:
                    widget.set_selected(outputs.index(initial_val))
                value_wrapper.append(widget)
            elif action_name == "alpha":
                adj = self.p.gtk.Adjustment.new(1.0, 0.0, 1.0, 0.1, 0.1, 0.0)
                widget = self.p.gtk.SpinButton(adjustment=adj, digits=1)
                if initial_val is not None:
                    widget.set_value(float(initial_val))
                value_wrapper.append(widget)
            else:
                widget = self.p.gtk.Entry(placeholder_text="Value", hexpand=True)
                if initial_val:
                    widget.set_text(str(initial_val))
                value_wrapper.append(widget)

        match_key_drop.connect(
            "notify::selected-item",
            lambda d, _: update_match_value_widget(d.get_selected_item().get_string()),
        )
        action_drop.connect(
            "notify::selected-item",
            lambda d, _: update_action_value_widget(d.get_selected_item().get_string()),
        )

        if data:
            match_key_drop.set_selected(
                MATCH_KEYS.index(data.get("match_key", "app-id"))
            )
            update_match_value_widget(data.get("match_key"), data.get("match_value"))
            event_drop.set_selected(EVENT_LIST.index(data.get("event")))
            timeout_spin.set_value(float(data.get("timeout", 0)))
            action_drop.set_selected(ACTION_LIST.index(data.get("action")))
            update_action_value_widget(data.get("action"), data.get("value"))
        else:
            update_match_value_widget("app-id")
            update_action_value_widget("fullscreen")

        del_btn = self.p.gtk.Button(icon_name="user-trash-symbolic")
        del_btn.add_css_class("destructive-action")
        del_btn.connect(
            "clicked", lambda _: self.list_box.remove(row_container.get_parent())
        )

        row.append(match_key_drop)
        row.append(match_val_wrapper)
        row.append(event_drop)
        row.append(timeout_spin)
        row.append(action_drop)
        row.append(value_wrapper)
        row.append(del_btn)
        row_container.append(row)
        row_container.append(self.p.gtk.Separator())
        self.list_box.append(row_container)

    def save(self):
        rules = []
        child = self.list_box.get_first_child()
        while child:
            row = child.get_child().get_first_child()
            ws = []
            curr = row.get_first_child()
            while curr:
                ws.append(curr)
                curr = curr.get_next_sibling()

            rules.append(
                {
                    "match_key": ws[0].get_selected_item().get_string(),
                    "match_value": self._get_val(ws[1]),
                    "event": ws[2].get_selected_item().get_string(),
                    "timeout": int(ws[3].get_value()),
                    "action": ws[4].get_selected_item().get_string(),
                    "value": self._get_val(ws[5]),
                }
            )
            child = child.get_next_sibling()
        self.p.set_plugin_setting("rules", rules)

    def _get_val(self, widget):
        if isinstance(widget, self.p.gtk.ComboBoxText):
            return widget.get_active_text() or widget.get_child().get_text()
        if isinstance(widget, self.p.gtk.DropDown):
            return widget.get_selected_item().get_string()
        if isinstance(widget, self.p.gtk.Entry):
            return widget.get_text()
        if isinstance(widget, self.p.gtk.Switch):
            return widget.get_active()
        if isinstance(widget, self.p.gtk.SpinButton):
            return widget.get_value()
        if isinstance(widget, self.p.gtk.Box):
            vals = []
            c = widget.get_first_child()
            while c:
                vals.append(str(self._get_val(c)))
                c = c.get_next_sibling()
            return ",".join(vals) if len(vals) > 1 else (vals[0] if vals else "")
        return ""

    def refresh_ui(self):
        for r in self.p.get_plugin_setting("rules", []):
            self.add_row(r)

    def _on_close(self, _):
        self.window = None
        return False
