DEFAULT_UPDATE_INTERVAL = 3600
DEFAULT_APP_IDS = "1903340, 489830, 892970, 271590"
DEFAULT_ICON_NAME = "steam-symbolic"
DEFAULT_CURRENCY = "US"


def get_plugin_metadata(panel):
    id = "org.waypanel.plugin.steam_sales"
    default_container = "background"
    container, id = panel.config_handler.get_plugin_container(default_container, id)
    return {
        "id": id,
        "name": "Steam Sales",
        "version": "1.0.0",
        "enabled": False,
        "hidden": True,
        "container": container,
        "index": 4,
        "deps": ["requests", "calendar"],
        "description": "Monitors Steam game discounts and displays active sales in the Calendar popover.",
    }


def get_plugin_class():
    """
    Factory function that returns the main plugin class.
    ALL imports are strictly deferred here.
    """
    from typing import Any, Optional, Dict, List, Union, cast
    from src.plugins.core._base import BasePlugin
    from gi.repository import Gtk, GLib  # pyright: ignore

    SaleDetails = Dict[str, Union[str, float, int]]

    class SteamSalesPlugin(BasePlugin):
        """
        Monitors a list of Steam App IDs for active sales using a background
        worker thread and dynamically updates the Calendar popover's UI.
        """

        _update_interval: int
        _app_ids_str: str
        _default_currency: str
        _tracked_app_ids: List[int]
        _sales_vbox: Optional[Gtk.Box]
        _sales_labels: Dict[int, Gtk.Box]
        _update_timeout_id: Optional[int]
        _active_sales_data: List[SaleDetails]

        def __init__(self, panel_instance: Any):
            """Initializes the plugin state and loads configuration settings."""
            super().__init__(panel_instance)
            interval_raw = self.get_plugin_setting_add_hint(
                ["update-interval"],
                DEFAULT_UPDATE_INTERVAL,
                "How often to check Steam for new sales, in seconds.",
            )
            self._update_interval = int(interval_raw)
            self._app_ids_str = self.get_plugin_setting_add_hint(
                ["tracked-app-ids"],
                DEFAULT_APP_IDS,
                "A comma-separated list of Steam App IDs to monitor for sales.",
            )
            # --- NEW CURRENCY SETTING ---
            self._default_currency = self.get_plugin_setting_add_hint(
                ["default-currency"],
                DEFAULT_CURRENCY,
                "The currency/country code (e.g., US, GB, JP) to fetch prices in.",
            )

            self._tracked_app_ids = []
            for id_str in self._app_ids_str.split(","):
                try:
                    self._tracked_app_ids.append(int(id_str.strip()))
                except ValueError:
                    self.logger.warning(f"Invalid Steam App ID ignored: {id_str}")
            self._sales_vbox = None
            self._sales_labels = {}
            self._update_timeout_id = None
            self._active_sales_data = []
            self.logger.info(
                f"SteamSalesPlugin initialized. Tracking {len(self._tracked_app_ids)} apps."
            )

        def on_start(self) -> None:
            """
            Asynchronous entry point. Sets up the UI, schedules initial integration
            with the calendar, and starts the recurring update task.
            """
            self.logger.info("Lifecycle: SteamSalesPlugin starting.")
            self._sales_vbox = self._build_sales_vbox()
            self.schedule_in_gtk_thread(self._integrate_with_calendar)
            self._start_updates()

        def on_stop(self) -> None:
            """Asynchronous cleanup hook. Stops the GLib timer."""
            self.logger.info("Lifecycle: SteamSalesPlugin stopping.")
            if self._update_timeout_id:
                GLib.source_remove(self._update_timeout_id)
                self._update_timeout_id = None
            self.logger.info("SteamSalesPlugin update timer stopped.")

        def _start_updates(self) -> None:
            """Schedules the recurring, non-blocking price fetch operation."""
            self.run_in_thread(self._fetch_and_update_sales)
            self._update_timeout_id = GLib.timeout_add_seconds(
                self._update_interval,
                self._schedule_next_fetch,
            )

        def _schedule_next_fetch(self) -> bool:
            """
            Executes the fetch operation in a background thread and ensures
            the timer is rescheduled by returning True.
            """
            self.run_in_thread(self._fetch_and_update_sales)
            return True

        def _fetch_sale_data(self, appid: int) -> Optional[SaleDetails]:
            """
            Performs the synchronous network request to the Steam API, using the
            configured country code for currency.
            """
            # --- FIX: Dynamically use configured currency code (cc) ---
            url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={self._default_currency}&l=english"

            try:
                response = self.requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                if not data or not data[str(appid)]["success"]:
                    self.logger.warning(f"App ID {appid} not found or API failed.")
                    return None
                info = data[str(appid)]["data"]
                if "price_overview" in info:
                    price = info["price_overview"]
                    if price.get("discount_percent", 0) > 0:
                        return {
                            "name": info["name"],
                            "original": price["initial"] / 100,
                            "final": price["final"] / 100,
                            "discount": price["discount_percent"],
                            "currency": price["currency"],
                        }
                self.logger.debug(f"App ID {appid} is not currently on sale.")
                return None
            except Exception as e:
                self.logger.error(f"Failed to fetch sale for {appid}: {e}")
                return None

        def _fetch_and_update_sales(self) -> None:
            """
            [NON-BLOCKING] Runs in a background thread. Fetches sales for all
            tracked apps and schedules the UI update.
            """
            self.logger.info("Fetching latest Steam sale prices in background thread.")
            active_sales: List[SaleDetails] = []
            for appid in self._tracked_app_ids:
                sale = self._fetch_sale_data(appid)
                if sale is not None:
                    active_sales.append(sale)
            self.schedule_in_gtk_thread(self._update_ui_state, active_sales)

        def _build_sales_vbox(self) -> Gtk.Box:
            """
            [UI THREAD ONLY] Constructs the dynamic Gtk.Box container for sales.
            Returns:
                Gtk.Box: The container box for all sales data.
            """
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            vbox.set_margin_top(5)
            vbox.set_margin_bottom(10)
            vbox.set_margin_start(15)
            vbox.set_margin_end(15)
            vbox.add_css_class("steam-sales-list")
            header_label = Gtk.Label(label="Steam Deals", xalign=0.0)
            header_label.add_css_class("steam-header")
            header_label.set_margin_bottom(5)
            vbox.append(header_label)
            separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            separator.set_margin_bottom(5)
            vbox.append(separator)
            return vbox

        def _update_ui_state(self, sales_data: List[SaleDetails]) -> None:
            """
            [UI THREAD ONLY] Updates the UI based on the fetched sale data.
            Shows the container if sales exist, hides it otherwise.
            """
            if self._sales_vbox is None:
                self.logger.warning("Sales VBox not built yet. Skipping UI update.")
                return
            self._active_sales_data = sales_data
            child = self._sales_vbox.get_first_child()
            for _ in range(2):
                if child:
                    child = child.get_next_sibling()
                else:
                    break
            while child:
                next_child = child.get_next_sibling()
                self._sales_vbox.remove(child)
                child = next_child
            self._sales_labels.clear()
            if sales_data:
                self.logger.info(
                    f"Found {len(sales_data)} active Steam sales. Updating UI."
                )
                for sale in sales_data:
                    final_price = f"{sale['final']:.2f} {sale['currency']}"
                    discount = f"-{sale['discount']}%"
                    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                    hbox.add_css_class("steam-sale-hbox")
                    discount_label = Gtk.Label(label=discount, xalign=0.0)
                    discount_label.add_css_class("steam-discount-label")
                    price_label = Gtk.Label(label=final_price, xalign=0.0)
                    price_label.add_css_class("steam-price-label")
                    name_label = Gtk.Label(label=cast(str, sale["name"]), xalign=0.0)
                    name_label.add_css_class("steam-name-label")
                    hbox.append(discount_label)
                    hbox.append(price_label)
                    hbox.append(name_label)
                    self._sales_vbox.append(hbox)
                self._sales_vbox.show()
                child = self._sales_vbox.get_first_child()
                while child:
                    child.show()
                    child = child.get_next_sibling()
            else:
                self.logger.info("No active Steam sales found. Hiding UI component.")
                self._sales_vbox.hide()

        def _integrate_with_calendar(self) -> None:
            """
            [UI THREAD ONLY] Integrates the sales VBox into the calendar
            plugin's popover grid at the position (2, 1).
            """
            if self._sales_vbox is None:
                return
            try:
                calendar_plugin = self.plugins["calendar"]
                calendar_popover = getattr(calendar_plugin, "popover_calendar", None)
                if calendar_popover is None:
                    self.logger.warning(
                        "Calendar plugin is loaded but missing 'popover_calendar' attribute. Integration failed."
                    )
                    return
                grid = calendar_popover.get_child()
                if isinstance(grid, Gtk.Grid):
                    # NOTE: Grid attachment moved to column 0, row 1 as per your request in the previous turn.
                    grid.attach(self._sales_vbox, 0, 1, 1, 1)
                    self.logger.info(
                        "Successfully attached Steam Sales VBox to Calendar grid."
                    )
                else:
                    self.logger.warning(
                        f"Calendar popover child is not a Gtk.Grid (found {type(grid)}). Integration failed."
                    )
            except KeyError:
                self.logger.warning(
                    "Calendar plugin not loaded or failed dependency check. Cannot integrate sales."
                )
            except Exception as e:
                self.logger.error(f"Failed to integrate with calendar plugin: {e}")

    return SteamSalesPlugin
