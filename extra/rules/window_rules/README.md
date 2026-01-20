# Waypanel Window Rules

A sophisticated automation engine for Wayland compositors. Define "If-This-Then-That" logic for your windows, enabling automatic positioning, transparency, and workspace management.

## Getting Started

To manage your rules, click on the **Window Title** widget on your panel and select **Open Window Rules**.

### Creating a Rule

- Click the **Plus (+)** button in the header bar.
- New rules are automatically **prepended** to the top of the list for easy access.
- Fill in the **Name** and **Description** to keep your setup organized.
- Define the **Match Key** and **Value** to identify the target window.
- Select a **Trigger Event** to determine when the rule fires.
- Choose an **Action** and provide its corresponding value.
- Click **Save** in the header to apply your changes.

| Match Key     | Description                        | Example              |
| :------------ | :--------------------------------- | :------------------- |
| `app-id`      | The application's internal ID.     | `org.gnome.Nautilus` |
| `title`       | The window's title text.           | `*YouTube*`          |
| `output-name` | The specific monitor name.         | `eDP-1`              |
| `parent`      | Matches based on window hierarchy. | `Dialog` or `Popup`  |

## Events & Actions

### Trigger Events

- **view-mapped**: Fires exactly when a window opens.
- **view-focused**: Fires when a window gains input focus.
- **view-fullscreen**: Fires when a window toggles fullscreen mode.
- **view-geometry-changed**: Fires when a window is moved or resized.

### Smart Actions

**send_to_workspace** Pick a workspace number from the dropdown. The engine calculates the coordinates for you.

**assign_slot** Snaps windows to a grid (e.g., Top Left, Center, Right).

**click_button** Simulates a physical mouse click automatically upon an event.

**alpha** Adjusts window transparency from 0.0 (invisible) to 1.0 (opaque).

## Advanced Tips

### Using Timeouts

Some applications take a few milliseconds to settle their UI after opening. If a rule (like centering) isn't sticking on launch, set a **Timeout of 100ms or 200ms** to let the window initialize first.

**Gaming Persistence Example**  
Match: `app-id` -> `steam_app_12345`  
Event: `view-mapped`  
Action 1: `move_to_output` -> `HDMI-A-1`  
Action 2: `fullscreen` -> `Switch ON`

### Organization

Rules are saved in the order they appear. Use the **Search Bar** to filter through names, descriptions, or application IDs. New rules always go to the top so your most recent work is always visible.

## Saving & Notifications

Always click the **Save** button after making changes. A **Toast Notification** will appear at the bottom of the window to confirm that your rules have been written to the Waypanel configuration.

Waypanel Project - Senior Python Implementation
