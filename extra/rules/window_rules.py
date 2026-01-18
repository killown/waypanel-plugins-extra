def get_plugin_metadata(_):
    return {
        "id": "org.waypanel.plugin.window_rules",
        "name": "Window Rules",
        "version": "1.9.0",
        "enabled": True,
        "container": "background",
        "index": 0,
        "deps": ["event_manager"],
        "description": "Advanced window automation with HIG-compliant Header Bar interface.",
    }


def get_plugin_class():
    from src.plugins.core._base import BasePlugin
    from typing import Any

    class WindowRulesPlugin(BasePlugin):
        def __init__(self, panel_instance):
            super().__init__(panel_instance)
            self.window = None
            self.event_list = [
                "view-mapped",
                "view-focused",
                "view-unmapped",
                "view-pre-map",
                "view-title-changed",
                "view-app-id-changed",
                "view-set-output",
                "view-workspace-changed",
                "view-wset-changed",
                "view-geometry-changed",
                "view-tiled",
                "view-minimized",
                "view-fullscreen",
                "view-sticky",
            ]
            self.action_list = [
                "fullscreen",
                "center",
                "maximize",
                "move_to_output",
                "send_to_workspace",
                "alpha",
                "configure_view",
                "set_minimized",
                "center_cursor",
                "assign_slot",
                "press_key",
                "move_cursor",
                "click_button",
                "set_focus",
            ]

            self.slots = [
                "slot_tl",
                "slot_t",
                "slot_tr",
                "slot_l",
                "slot_c",
                "slot_r",
                "slot_bl",
                "slot_b",
                "slot_br",
            ]
            self.mouse_buttons = ["BTN_LEFT", "BTN_RIGHT", "BTN_MIDDLE"]
            self.mouse_modes = ["press", "release", "click"]

            self.event_hints = {
                "view-focused": "Emitted when input focus changes.",
                "view-unmapped": "Emitted when a view is hidden or closed.",
                "view-pre-map": "Emitted immediately before a view is mapped.",
                "view-mapped": "Emitted when a view becomes visible on screen.",
                "view-title-changed": "Emitted when a view title changes.",
                "view-app-id-changed": "Emitted when a view application ID changes.",
                "view-set-output": "Emitted when a view is moved to another output.",
                "view-workspace-changed": "Emitted when a view changes workspace.",
                "view-wset-changed": "Emitted when a view changes workspace set.",
                "view-geometry-changed": "Emitted when a view position or size changes.",
                "view-tiled": "Emitted when a view is tiled or snapped.",
                "view-minimized": "Emitted when a view is minimized or restored.",
                "view-fullscreen": "Emitted when a view enters or exits fullscreen.",
                "view-sticky": "Emitted when a view becomes sticky or unsticky.",
            }

        def on_start(self):
            self.get_plugin_setting_add_hint("rules", [], "List of window rules.")
            self.glib.idle_add(self._subscribe_to_events_with_retry)

        def _subscribe_to_events_with_retry(self) -> bool:
            mgr = self.plugins.get("org.waypanel.plugin.event_manager")
            if not mgr:
                return self.glib.SOURCE_CONTINUE
            for event in self.event_list:
                mgr.subscribe_to_event(event, self._handle_event)
            return self.glib.SOURCE_REMOVE

        def open_rules_manager(self):
            if self.window:
                self.window.present()
                return

            self.window = self.gtk.Window(title="Window Rules")
            self.window.set_default_size(1100, 650)

            # --- Header Bar (HIG Guidelines) ---
            header = self.gtk.HeaderBar()
            self.window.set_titlebar(header)

            add_btn = self.gtk.Button(icon_name="list-add-symbolic")
            add_btn.set_tooltip_text("Add New Rule")
            add_btn.connect("clicked", lambda _: self._add_rule_row())
            header.pack_start(add_btn)

            save_btn = self.gtk.Button(label="Save")
            save_btn.add_css_class("suggested-action")
            save_btn.connect("clicked", lambda _: self._save_rules())
            header.pack_end(save_btn)

            # --- Main Content Area ---
            main_vbox = self.gtk.Box(
                orientation=self.gtk.Orientation.VERTICAL, spacing=0
            )

            self.rules_list_box = self.gtk.ListBox()
            self.rules_list_box.set_selection_mode(self.gtk.SelectionMode.NONE)
            self.rules_list_box.add_css_class("boxed-list")
            self.rules_list_box.set_margin_start(20)
            self.rules_list_box.set_margin_end(20)
            self.rules_list_box.set_margin_top(20)
            self.rules_list_box.set_margin_bottom(20)

            scrolled = self.gtk.ScrolledWindow()
            scrolled.set_vexpand(True)
            scrolled.set_child(self.rules_list_box)
            main_vbox.append(scrolled)

            self.window.set_child(main_vbox)
            self._refresh_ui()
            self.window.connect("close-request", self._on_window_close)
            self.window.present()

        def _add_rule_row(self, data=None):
            row_container = self.gtk.Box(
                orientation=self.gtk.Orientation.VERTICAL, spacing=4
            )
            row_container.set_margin_top(8)
            row_container.set_margin_bottom(8)

            row = self.gtk.Box(spacing=12)

            app_entry = self.gtk.Entry(placeholder_text="app-id", hexpand=True)
            if data and isinstance(data, dict):
                app_entry.set_text(data.get("app_id", ""))

            event_drop = self.gtk.DropDown.new_from_strings(self.event_list)
            action_drop = self.gtk.DropDown.new_from_strings(self.action_list)

            value_wrapper = self.gtk.Box(spacing=6)
            value_wrapper.set_size_request(300, -1)

            hint_label = self.gtk.Label(xalign=0)
            hint_label.add_css_class("dim-label")
            hint_label.set_margin_start(12)

            def update_value_widget(action_name, initial_val=None):
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
                    widget = self.gtk.Switch()
                    widget.set_valign(self.gtk.Align.CENTER)
                    if initial_val is not None:
                        widget.set_active(str(initial_val).lower() == "true")
                    value_wrapper.append(widget)

                elif action_name == "press_key":
                    widget = self.gtk.Entry(placeholder_text="KEY_ENTER")
                    if initial_val:
                        widget.set_text(str(initial_val))
                    value_wrapper.append(widget)

                elif action_name == "click_button":
                    vals = (
                        str(initial_val).split(",")
                        if initial_val
                        else ["BTN_LEFT", "click"]
                    )
                    btn_drop = self.gtk.DropDown.new_from_strings(self.mouse_buttons)
                    mode_drop = self.gtk.DropDown.new_from_strings(self.mouse_modes)
                    if vals[0] in self.mouse_buttons:
                        btn_drop.set_selected(self.mouse_buttons.index(vals[0]))
                    if len(vals) > 1 and vals[1] in self.mouse_modes:
                        mode_drop.set_selected(self.mouse_modes.index(vals[1]))
                    value_wrapper.append(btn_drop)
                    value_wrapper.append(mode_drop)

                elif action_name in ["move_cursor", "send_to_workspace"]:
                    vals = str(initial_val).split(",") if initial_val else ["0", "0"]
                    for i, p in enumerate(["X", "Y"]):
                        entry = self.gtk.Entry(placeholder_text=p)
                        entry.set_width_chars(5)
                        if len(vals) > i:
                            entry.set_text(vals[i])
                        value_wrapper.append(entry)

                elif action_name == "assign_slot":
                    widget = self.gtk.DropDown.new_from_strings(self.slots)
                    if initial_val and initial_val in self.slots:
                        widget.set_selected(self.slots.index(initial_val))
                    value_wrapper.append(widget)

                elif action_name == "alpha":
                    adj = self.gtk.Adjustment.new(1.0, 0.0, 1.0, 0.1, 0.1, 0.0)
                    widget = self.gtk.SpinButton(adjustment=adj, digits=1)
                    if initial_val is not None:
                        widget.set_value(float(initial_val))
                    value_wrapper.append(widget)

                elif action_name == "configure_view":
                    vals = (
                        str(initial_val).split(",")
                        if initial_val
                        else ["0", "0", "800", "600"]
                    )
                    for i, p in enumerate(["X", "Y", "W", "H"]):
                        entry = self.gtk.Entry(placeholder_text=p)
                        entry.set_width_chars(5)
                        if len(vals) > i:
                            entry.set_text(vals[i])
                        value_wrapper.append(entry)
                else:
                    widget = self.gtk.Entry(placeholder_text="Value", hexpand=True)
                    if initial_val:
                        widget.set_text(str(initial_val))
                    value_wrapper.append(widget)

            event_drop.connect(
                "notify::selected-item",
                lambda d, _: hint_label.set_text(
                    self.event_hints.get(d.get_selected_item().get_string(), "")
                ),
            )
            action_drop.connect(
                "notify::selected-item",
                lambda d, _: update_value_widget(d.get_selected_item().get_string()),
            )

            if data and isinstance(data, dict):
                if data.get("event") in self.event_list:
                    event_drop.set_selected(self.event_list.index(data.get("event")))
                if data.get("action") in self.action_list:
                    action_drop.set_selected(self.action_list.index(data.get("action")))
                update_value_widget(data.get("action"), data.get("value"))
            else:
                update_value_widget("fullscreen")

            del_btn = self.gtk.Button(icon_name="user-trash-symbolic")
            del_btn.add_css_class("destructive-action")
            del_btn.connect(
                "clicked",
                lambda _: self.rules_list_box.remove(row_container.get_parent()),
            )

            row.append(app_entry)
            row.append(event_drop)
            row.append(action_drop)
            row.append(value_wrapper)
            row.append(del_btn)
            row_container.append(row)
            row_container.append(hint_label)
            row_container.append(self.gtk.Separator())
            self.rules_list_box.append(row_container)

        def _refresh_ui(self):
            rules = self.get_plugin_setting("rules", [])
            for r in rules:
                self._add_rule_row(r)

        def _get_val_from_wrapper(self, wrapper):
            if not wrapper.get_visible():
                return ""
            child = wrapper.get_first_child()
            if isinstance(child, self.gtk.Switch):
                return child.get_active()
            if isinstance(child, self.gtk.DropDown):
                vals = []
                curr = child
                while curr:
                    vals.append(curr.get_selected_item().get_string())
                    curr = curr.get_next_sibling()
                return ",".join(vals)
            if isinstance(child, self.gtk.SpinButton):
                return child.get_value()
            if isinstance(child, self.gtk.Entry):
                vals = []
                curr = child
                while curr:
                    vals.append(curr.get_text() or "0")
                    curr = curr.get_next_sibling()
                return ",".join(vals) if len(vals) > 1 else vals[0]
            return ""

        def _save_rules(self):
            new_rules = []
            child = self.rules_list_box.get_first_child()
            while child:
                vbox = child.get_child()
                row = vbox.get_first_child()
                widgets = self._get_row_widgets(row)
                aid = widgets[0].get_text().strip()
                if aid:
                    new_rules.append(
                        {
                            "app_id": aid,
                            "event": widgets[1].get_selected_item().get_string(),
                            "action": widgets[2].get_selected_item().get_string(),
                            "value": self._get_val_from_wrapper(widgets[3]),
                        }
                    )
                child = child.get_next_sibling()
            self.set_plugin_setting("rules", new_rules)
            self.logger.info("Window Rules saved.")

        def _get_row_widgets(self, box):
            res = []
            curr = box.get_first_child()
            while curr:
                res.append(curr)
                curr = curr.get_next_sibling()
            return res

        def _on_window_close(self, _):
            self.window = None
            return False

        def _handle_event(self, event_data: Any):
            if not isinstance(event_data, dict):
                return
            view = event_data.get("view")
            if not view or not isinstance(view, dict) or view.get("role") != "toplevel":
                return
            app_id = view.get("app-id")
            event_type = event_data.get("event")
            if not app_id:
                return
            rules = self.get_plugin_setting("rules", [])
            for rule in rules:
                if (
                    isinstance(rule, dict)
                    and rule.get("app_id") == app_id
                    and rule.get("event") == event_type
                ):
                    self._apply_rule(rule, view.get("id"))

        def _apply_rule(self, rule, view_id):
            action = rule.get("action")
            val = rule.get("value")
            if action == "fullscreen":
                self.ipc.set_view_fullscreen(view_id, str(val).lower() == "true")
            elif action == "center":
                self.wf_helper.center_view_on_output(view_id)
            elif action == "maximize":
                self.ipc.set_view_maximized(view_id)
            elif action == "move_to_output":
                for out in self.ipc.list_outputs() or []:
                    if out.get("name") == val:
                        self.ipc.send_view_to_wset(view_id, out.get("wset-index"))
                        break
            elif action == "send_to_workspace":
                try:
                    x, y = map(int, str(val).split(","))
                    self.ipc.send_view_to_workspace(view_id, x, y)
                except:
                    pass
            elif action == "alpha":
                try:
                    self.ipc.set_view_alpha(view_id, float(val))
                except:
                    pass
            elif action == "configure_view":
                try:
                    x, y, w, h = map(int, str(val).split(","))
                    self.ipc.configure_view(view_id, x, y, w, h)
                except:
                    pass
            elif action == "set_minimized":
                self.ipc.set_view_minimized(view_id, str(val).lower() == "true")
            elif action == "center_cursor":
                self.ipc.center_cursor_on_view(view_id)
            elif action == "assign_slot":
                self.ipc.assign_slot(view_id, str(val))
            elif action == "press_key":
                self.ipc.press_key(str(val))
            elif action == "move_cursor":
                try:
                    x, y = map(int, str(val).split(","))
                    self.ipc.move_cursor(x, y)
                except:
                    pass
            elif action == "click_button":
                try:
                    btn, mode = str(val).split(",")
                    self.ipc.click_button(btn, mode)
                except:
                    pass
            elif action == "set_focus":
                self.ipc.set_view_focus(view_id)

    return WindowRulesPlugin
