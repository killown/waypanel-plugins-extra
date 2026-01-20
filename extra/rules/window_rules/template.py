"""Constants and metadata for the Window Rules plugin."""

METADATA = {
    "id": "org.waypanel.plugin.window_rules",
    "name": "Window Rules",
    "version": "2.3.1",
    "enabled": True,
    "container": "background",
    "index": 0,
    "deps": ["event_manager"],
    "description": "Smart window engine with focus capture and exhaustive tooltip coverage.",
}

MATCH_KEYS = ["app-id", "title", "output-name", "type", "role", "parent"]

EVENT_LIST = [
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

ACTION_LIST = [
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

ROLES = ["toplevel", "desktop-environment", "popup", "subsurface"]
TYPES = ["toplevel", "background", "panel", "overlay"]
PARENT_STATES = ["Main Window", "Dialog or Popup"]

SLOTS = [
    "Top Left",
    "Top",
    "Top Right",
    "Left",
    "Center",
    "Right",
    "Bottom Left",
    "Bottom",
    "Bottom Right",
]

SLOT_MAP = {
    "Top Left": "slot_tl",
    "Top": "slot_t",
    "Top Right": "slot_tr",
    "Left": "slot_l",
    "Center": "slot_c",
    "Right": "slot_r",
    "Bottom Left": "slot_bl",
    "Bottom": "slot_b",
    "Bottom Right": "slot_br",
}

# Add a reverse map for loading existing rules
REVERSE_SLOT_MAP = {v: k for k, v in SLOT_MAP.items()}

EVENT_HINTS = {
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

ACTION_HINTS = {
    "fullscreen": "Toggles fullscreen state.",
    "center": "Centers the view on its current output.",
    "maximize": "Maximizes the view.",
    "move_to_output": "Moves view to a specific monitor.",
    "send_to_workspace": "Moves view to a specific (X, Y) workspace.",
    "alpha": "Sets window transparency (0.0 - 1.0).",
    "configure_view": "Sets exact (X, Y, W, H) geometry.",
    "set_minimized": "Minimizes or restores the view.",
    "center_cursor": "Warps mouse to center of view.",
    "assign_slot": "Snaps view to a predefined grid slot.",
    "press_key": "Simulates a keyboard press.",
    "move_cursor": "Warps cursor to absolute screen coordinates.",
    "click_button": "Simulates a mouse button click.",
    "set_focus": "Gives input focus to the view.",
}
