"""Window Rules Plugin for Waypanel."""


def get_plugin_metadata(_):
    from .template import METADATA

    return METADATA


def get_plugin_class():
    from src.plugins.core._base import BasePlugin
    from .engine import RuleEngine
    from .manager import RuleManager
    from .template import EVENT_LIST

    class WindowRulesPlugin(BasePlugin):
        def __init__(self, panel_instance):
            super().__init__(panel_instance)
            self.engine = RuleEngine(self)
            self.manager = RuleManager(self)

        def on_start(self):
            # Register CSS for the rule manager UI
            self.plugins["css_generator"].install_css("window_rules.css")

            # Initialize settings
            self.get_plugin_setting_add_hint(
                "rules", [], "List of fuzzy-logic window rules."
            )

            # Delayed subscription to event manager
            self.glib.timeout_add(500, self._subscribe)

        def _subscribe(self):
            mgr = self.plugins.get("org.waypanel.plugin.event_manager")
            if not mgr:
                return self.glib.SOURCE_CONTINUE
            for ev in EVENT_LIST:
                mgr.subscribe_to_event(ev, self._handle_event)
            return self.glib.SOURCE_REMOVE

        def open_rules_manager(self):
            self.manager.open()

        def _handle_event(self, data):
            view, ev = data.get("view"), data.get("event")
            if not view:
                return

            if view["type"] != "toplevel":
                return

            # Apply rules defined in the Rule Manager
            for rule in self.get_plugin_setting("rules", []):
                if rule.get("event") == ev and self.engine.match(rule, view):
                    t = rule.get("timeout", 0)
                    if t > 0:
                        self.glib.timeout_add(
                            t,
                            lambda r=rule, v=view: (self.engine.apply(r, v), False)[1],
                        )
                    else:
                        self.engine.apply(rule, view)

    return WindowRulesPlugin
