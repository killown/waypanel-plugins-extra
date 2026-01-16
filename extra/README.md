Waypanel Plugins Extra
======================

A dedicated repository for extended functionality, community contributions, and non-core plugins for Waypanel.

Why This Repository?
--------------------

Waypanel aims to remain lightweight and stable. To achieve this, the core repository only includes essential plugins required for a functional desktop environment. **Waypanel Plugins Extra** was created to:

*   **Keep Core Clean:** Prevent the main project from becoming bloated with niche or highly specific plugins.
*   **Community Contributions:** Provide a space where users can easily submit and share their own custom plugins.
*   **Experimental Features:** Host plugins that are in development or use external dependencies not found in the core stack.

Plugin Architecture
-------------------

All plugins here follow the standard `BasePlugin` architecture. Remember the strict rule:

*   **No Top-Level Imports:** All library and module imports must be handled inside `get_plugin_class()` to ensure the panel remains fast and responsive via lazy loading.

How to Contribute
-----------------

Got a plugin you want to share? We welcome all submissions!

1.  Fork this repository.
2.  Ensure your plugin follows the metadata and class factory structure.
3.  Submit a Pull Request.

Refer to the [Official Wiki](https://github.com/killown/waypanel/wiki/Building-plugins) for detailed building instructions.
