"""Window Rules matching and execution engine."""

from typing import Any, Dict


class RuleEngine:
    def __init__(self, plugin):
        self.p = plugin
        # Action Registry mapping action strings to internal methods
        self._actions = {
            "fullscreen": self._act_fullscreen,
            "center": self._act_center,
            "maximize": self._act_maximize,
            "move_to_output": self._act_move_to_output,
            "send_to_workspace": self._act_send_to_workspace,
            "alpha": self._act_alpha,
            "configure_view": self._act_configure_view,
            "set_minimized": self._act_set_minimized,
            "center_cursor": self._act_center_cursor,
            "assign_slot": self._act_assign_slot,
            "press_key": self._act_press_key,
            "move_cursor": self._act_move_cursor,
            "click_button": self._act_click_button,
            "set_focus": self._act_set_focus,
        }

    def match(self, rule: Dict, view: Dict) -> bool:
        """Determines if a view matches a specific rule."""
        m_key = rule.get("match_key")
        m_val = str(rule.get("match_value", ""))
        view_val = view.get(m_key)

        if m_key == "parent":
            is_child = int(view_val) > -1
            if m_val == "Dialog or Popup":
                return is_child
            if m_val == "Main Window":
                return not is_child
            return False

        if m_key in ["title", "app-id"]:
            return m_val.lower() in str(view_val).lower()

        return m_val.lower() == str(view_val).lower()

    def apply(self, rule: Dict, view: Dict):
        """Executes the action defined in the rule via the registry."""
        v_id = view.get("id")
        if not v_id:
            return

        action = rule.get("action")
        val = rule.get("value")

        # Constraint: Non-toplevel views cannot have certain geometry actions
        if view.get("role") != "toplevel" and action in [
            "maximize",
            "fullscreen",
            "set_minimized",
            "configure_view",
        ]:
            return

        handler = self._actions.get(action)
        if handler:
            try:
                self.p.logger.info(
                    f"[Rule Triggered] View: {view.get('app-id')} Action: {action}"
                )
                handler(v_id, val)
            except Exception as e:
                self.p.logger.error(f"Failed to execute action {action}: {e}")

    # Dedicated Action Methods

    def _act_fullscreen(self, v_id, val):
        self.p.ipc.set_view_fullscreen(v_id, str(val).lower() == "true")

    def _act_center(self, v_id, _):
        self.p.wf_helper.center_view_on_output(v_id)

    def _act_maximize(self, v_id, _):
        self.p.ipc.set_view_maximized(v_id)

    def _act_move_to_output(self, v_id, val):
        for out in self.p.ipc.list_outputs() or []:
            if out.get("name") == val:
                self.p.ipc.send_view_to_wset(v_id, out.get("wset-index"))
                break

    def _act_send_to_workspace(self, v_id, val):
        x, y = map(int, str(val).split(","))
        self.p.ipc.send_view_to_workspace(v_id, x, y)

    def _act_alpha(self, v_id, val):
        self.p.ipc.set_view_alpha(v_id, float(val))

    def _act_configure_view(self, v_id, val):
        x, y, w, h = map(int, str(val).split(","))
        self.p.ipc.configure_view(v_id, x, y, w, h)

    def _act_set_minimized(self, v_id, val):
        self.p.ipc.set_view_minimized(v_id, str(val).lower() == "true")

    def _act_center_cursor(self, v_id, _):
        self.p.ipc.center_cursor_on_view(v_id)

    def _act_assign_slot(self, v_id, val):
        self.p.ipc.assign_slot(v_id, str(val))

    def _act_press_key(self, _, val):
        self.p.ipc.press_key(str(val))

    def _act_move_cursor(self, _, val):
        x, y = map(int, str(val).split(","))
        self.p.ipc.move_cursor(x, y)

    def _act_click_button(self, _, val):
        btn, mode = str(val).split(",")
        self.p.ipc.click_button(btn, mode)

    def _act_set_focus(self, v_id, _):
        self.p.ipc.set_view_focus(v_id)
