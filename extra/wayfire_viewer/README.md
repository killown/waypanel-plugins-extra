# Wayfire Config Viewer Plugin

A real-time configuration manager for the Wayfire compositor. This plugin provides a graphical interface to view and modify all active Wayfire options, including core settings and individual plugin parameters.

## Overview

The Wayfire Config Viewer allows you to adjust your desktop environment on the fly. It leverages Wayfire's Inter-Process Communication (IPC) to apply changes instantly and persists those settings to a dedicated configuration file to ensure they survive reboots.

## Configuration Priority & Persistence

**Important:** This plugin utilizes a specific configuration hierarchy to ensure stability and compatibility within the Waypanel ecosystem.

- **Storage Path:** All changes applied through this interface are saved to:  
  `~/.config/waypanel/wayfire/wayfire.toml`
- **Priority:** Once you have modified a setting using this plugin, the `wayfire.toml` file becomes the authoritative source for that configuration.
- **Conflict Handling:** Values defined in your traditional `~/.config/wayfire.ini` will be ignored for any keys managed by this plugin. Even if you manually edit your `.ini` file, the settings applied here will remain active and will not be overwritten by the `.ini` file.

## Features

- **Real-time Synchronization:** Changes are sent immediately to the running compositor via IPC.
- **Dynamic Plugin Toggling:** Enable or disable Wayfire plugins (such as _expo_, _scale_, or _wobbly_) using simple toggles.
- **Type-Safe Editing:** Automatically handles boolean switches, numeric inputs, and list-based configurations.
- **TOML Persistence:** Saves configuration in a clean, modern TOML format as a list where required by the compositor.

## Usage

1.  Click the Wayfire Config Viewer icon in your panel (represented by a system-settings icon).
2.  The configuration window will open with a categorized list of all available plugins and their options.
3.  Adjust settings as needed. The background system will handle both the immediate IPC update and the permanent disk write.

## Troubleshooting

If settings do not appear to take effect:

- Ensure the `ipc` plugin is enabled in your core Wayfire configuration.
- Check that you have write permissions for `~/.config/waypanel/wayfire/`.
- Remember that `wayfire.toml` (managed by this plugin) will always override conflicting values in `wayfire.ini`.
