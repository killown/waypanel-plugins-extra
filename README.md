Waypanel Plugins Extra
======================

A dedicated repository for extended functionality, community contributions, and non-core plugins for Waypanel.

Why This Repository?
--------------------

Waypanel aims to remain lightweight and stable. The core repository only includes essential plugins. This repo exists to:

*   **Keep Core Clean:** Avoid bloating the main project with niche plugins.
*   **Community Space:** A place for users to submit and share their own creations.
*   **Experimental Features:** Host plugins with external dependencies or development-stage code.

Repository Structure
--------------------

### waypanel-plugins-extra/
    ├── extra/          # Official extra plugins maintained by the project
    └── community/      # User-submitted plugins and community contributions

Plugin Architecture
-------------------

All plugins must follow the `BasePlugin` architecture. Note the strict rule:

*   **No Top-Level Imports:** All library and module imports must be deferred inside `get_plugin_class()` to allow for lazy loading.

How to Contribute
-----------------

Got a plugin to share? Follow these steps to submit your work:

1.  Fork this repository.
2.  Create a folder for your plugin inside the **`community/`** directory.
3.  Ensure your code follows the metadata and class factory structure.
4.  Submit a **Pull Request (PR)** targeting the `community/` folder.

Refer to the [Official Wiki](https://github.com/killown/waypanel/wiki/Building-plugins) for building instructions.
