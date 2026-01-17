# Waypanel Community Plugins

This repository serves as a collective catalog for community-contributed plugins. To maintain high system performance, this repository is structured as a **Passive Library** rather than an active deployment folder.

---

## The Performance Guard: `.ignore_plugins`

By default, this repository contains a `.ignore_plugins` file at its root.

### Why it exists

- **Instant Skip:** When the Waypanel loader encounters this file, it instantly discards the entire directory branch.
- **Zero Overhead:** No system calls are made to subdirectories, and no Python modules are imported into memory.
- **Safety:** It prevents experimental or unconfigured community plugins from impacting your stable environment.

---

## How to Enable Plugins

The ignore logic allows you to sync the entire repository locally without affecting startup speed. To "install" a plugin, use a physical toggle:

### Method 1: The Move (Recommended)

Copy or move the specific plugin folder from this repository into your primary plugins directory:

`cp -r ~/Git/waypanel-community/plugin-name ~/.local/share/waypanel/plugins/`

### Method 2: Selective Discovery

If you want to keep the plugin inside this folder but enable it, delete the `.ignore_plugins` file. _Note: Deleting the root ignore file will attempt to load every plugin in the repository._

---

## Contributing

When submitting a Pull Request:

1.  Ensure your plugin follows the Waypanel Coding Protocol.
2.  Do not include a `.ignore_plugins` file inside your specific plugin folder.
3.  Update the global manifest if applicable.
