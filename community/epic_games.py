DEFAULT_UPDATE_INTERVAL = 3600
DEFAULT_ICON_NAME = "epic-games-symbolic"
DEFAULT_LOCALE = "en-US"
DEFAULT_COUNTRY = "US"
EPIC_FREE_API = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"


def get_plugin_metadata(panel):
    id = "org.waypanel.plugin.epic_free_games"
    default_container = "background"
    container, id = panel.config_handler.get_plugin_container(default_container, id)
    return {
        "id": id,
        "name": "Epic Free Games",
        "version": "1.0.0",
        "enabled": False,
        "hidden": True,
        "container": container,
        "index": 5,
        "deps": ["requests", "calendar"],
        "description": "Monitors Epic Games Store for free weekly games and displays them in the Calendar popover.",
    }


def get_plugin_class():
    """
    Factory function that returns the main plugin class.
    ALL imports are strictly deferred here.
    """
    from typing import Any, Optional, Dict, List, Union, cast
    from src.plugins.core._base import BasePlugin
    from gi.repository import Gtk, GLib  # pyright: ignore
    from datetime import datetime, timezone
    import requests

    SaleDetails = Dict[str, Union[str, float, int]]
    FreeGameDetails = Dict[str, Union[str, Optional[datetime], List[Dict], Any]]

    def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
        """Parses ISO 8601 UTC timestamps from the Epic API."""
        if not dt:
            return None
        try:
            return datetime.fromisoformat(dt.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        except Exception:
            return None

    def _get_free_games_data(
        locale: str, country: str, logger: Any
    ) -> List[FreeGameDetails]:
        """
        [NON-BLOCKING] Fetches the list of currently free games from the Epic API.
        This logic is now robust to handle complex nested promotions.
        """
        params = {"locale": locale, "country": country, "allowCountries": country}
        try:
            r = requests.get(EPIC_FREE_API, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch Epic Games data: {e}")
            return []

        results: List[FreeGameDetails] = []
        elements = (
            data.get("data", {})
            .get("Catalog", {})
            .get("searchStore", {})
            .get("elements", [])
        )
        now = datetime.now(timezone.utc)

        for el in elements:
            promotions = el.get("promotions") or {}
            # Focus on current active offers
            current_promotions = promotions.get("promotionalOffers") or []

            if not current_promotions:
                continue

            active_free_offers = []

            for p in current_promotions:
                # Offers may be nested under 'promotionalOffers' or 'offers' key
                offers = p.get("promotionalOffers") or p.get("offers") or []
                for offer in offers:
                    discount_percent = offer.get("discountSetting", {}).get(
                        "discountPercentage"
                    )

                    # Only proceed if the discount is 100% (i.e., the game is free)
                    if discount_percent == 100:
                        start = _parse_iso(offer.get("startDate"))
                        end = _parse_iso(offer.get("endDate"))

                        # Sanity check: ensure the offer is still active
                        if end and end > now:
                            active_free_offers.append(
                                {
                                    "startDate": start,
                                    "endDate": end,
                                }
                            )

            # Skip if no currently active free offers were found
            if not active_free_offers:
                continue

            # --- Gather Game Metadata ---
            title = el.get("title") or "Unknown Title"
            # Get the page slug for the direct store link
            page_slug = (el.get("offerMappings") or [{}])[0].get("pageSlug")
            store_url = None
            if page_slug:
                store_url = (
                    f"https://store.epicgames.com/{locale.lower()}/p/{page_slug}"
                )

            # Use the first active offer as the primary reference date
            main_offer = active_free_offers[0]

            results.append(
                {
                    "title": title,
                    "store_url": store_url,
                    "start_date": main_offer["startDate"],
                    "end_date": main_offer["endDate"],
                }
            )

        return results

    class EpicFreeGamesPlugin(BasePlugin):
        """
        Monitors Epic Games for free games and dynamically displays them
        in the Calendar popover.
        """

        _update_interval: int
        _locale: str
        _country: str
        _games_vbox: Optional[Gtk.Box]
        _update_timeout_id: Optional[int]
        _active_games_data: List[FreeGameDetails]

        def __init__(self, panel_instance: Any):
            """Initializes the plugin state and loads configuration settings."""
            super().__init__(panel_instance)
            interval_raw = self.get_plugin_setting_add_hint(
                ["update-interval"],
                DEFAULT_UPDATE_INTERVAL,
                "How often to check Epic Games for new free titles, in seconds.",
            )
            self._update_interval = int(interval_raw)
            self._locale = self.get_plugin_setting_add_hint(
                ["locale"],
                DEFAULT_LOCALE,
                "The locale (e.g., en-US) for language translation.",
            )
            self._country = self.get_plugin_setting_add_hint(
                ["country"],
                DEFAULT_COUNTRY,
                "The country code (e.g., US) to determine game availability.",
            )
            self._games_vbox = None
            self._update_timeout_id = None
            self._active_games_data = []
            self.logger.info("EpicFreeGamesPlugin initialized.")

        def on_start(self) -> None:
            """
            Asynchronous entry point. Sets up UI, schedules integration, and starts
            the recurring update task.
            """
            self.logger.info("Lifecycle: EpicFreeGamesPlugin starting.")
            self._games_vbox = self._build_games_vbox()
            self.schedule_in_gtk_thread(self._integrate_with_calendar)
            self._start_updates()

        def on_stop(self) -> None:
            """Asynchronous cleanup hook. Stops the GLib timer."""
            self.logger.info("Lifecycle: EpicFreeGamesPlugin stopping.")
            if self._update_timeout_id:
                GLib.source_remove(self._update_timeout_id)
                self._update_timeout_id = None
            self.logger.info("EpicFreeGamesPlugin update timer stopped.")

        def _start_updates(self) -> None:
            """Schedules the recurring, non-blocking fetch operation."""
            self.run_in_thread(self._fetch_and_update_games)
            self._update_timeout_id = GLib.timeout_add_seconds(
                self._update_interval,
                self._schedule_next_fetch,
            )

        def _schedule_next_fetch(self) -> bool:
            """Executes the fetch operation in a background thread."""
            self.run_in_thread(self._fetch_and_update_games)
            return True

        def _fetch_and_update_games(self) -> None:
            """
            [NON-BLOCKING] Runs in a background thread. Fetches free games
            and schedules the UI update.
            """
            self.logger.info("Fetching latest Epic free games in background thread.")
            free_games = _get_free_games_data(self._locale, self._country, self.logger)
            self.schedule_in_gtk_thread(self._update_ui_state, free_games)

        def _build_games_vbox(self) -> Gtk.Box:
            """
            [UI THREAD ONLY] Constructs the dynamic Gtk.Box container for free games.
            """
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            vbox.set_margin_top(5)
            vbox.set_margin_bottom(10)
            vbox.set_margin_start(15)
            vbox.set_margin_end(15)
            vbox.add_css_class("epic-games-list")
            header_label = Gtk.Label(label="Epic FREE Games", xalign=0.0)
            header_label.add_css_class("epic-header")
            header_label.set_margin_bottom(5)
            vbox.append(header_label)
            separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            separator.set_margin_bottom(5)
            vbox.append(separator)
            return vbox

        def _update_ui_state(self, games_data: List[FreeGameDetails]) -> None:
            """
            [UI THREAD ONLY] Updates the UI based on the fetched free game data.
            """
            if self._games_vbox is None:
                self.logger.warning("Games VBox not built yet. Skipping UI update.")
                return
            self._active_games_data = games_data
            child = self._games_vbox.get_first_child()
            for _ in range(2):
                if child:
                    child = child.get_next_sibling()
                else:
                    break
            while child:
                next_child = child.get_next_sibling()
                self._games_vbox.remove(child)
                child = next_child
            if games_data:
                self.logger.info(
                    f"Found {len(games_data)} active free games. Updating UI."
                )
                for game in games_data:
                    end_date = cast(datetime, game["end_date"])
                    time_left = end_date - datetime.now(timezone.utc)
                    days_left = time_left.days
                    if days_left == 0:
                        time_display = "Ends TODAY"
                    elif days_left == 1:
                        time_display = "1 day left"
                    else:
                        time_display = f"{days_left} days left"
                    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                    hbox.add_css_class("epic-game-hbox")
                    time_label = Gtk.Label(label=time_display, xalign=0.0)
                    time_label.add_css_class("epic-time-label")
                    title_label = Gtk.Label(label=cast(str, game["title"]), xalign=0.0)
                    title_label.add_css_class("epic-title-label")
                    if game["store_url"]:
                        title_label.set_tooltip_text(
                            f"Click to open: {game['store_url']}"
                        )
                    hbox.append(time_label)
                    hbox.append(title_label)
                    self._games_vbox.append(hbox)
                self._games_vbox.show()
                child = self._games_vbox.get_first_child()
                while child:
                    child.show()
                    child = child.get_next_sibling()
            else:
                self.logger.info("No active free games found. Hiding UI component.")
                self._games_vbox.hide()

        def _integrate_with_calendar(self) -> None:
            """
            [UI THREAD ONLY] Integrates the free games VBox into the calendar
            plugin's popover grid at the position (2, 2).
            """
            if self._games_vbox is None:
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
                    # Attach below the Steam sales widget (which is at 2, 1)
                    grid.attach(self._games_vbox, 3, 2, 1, 1)
                    self.logger.info(
                        "Successfully attached Epic Free Games VBox to Calendar grid at (2, 2)."
                    )
                else:
                    self.logger.warning(
                        f"Calendar popover child is not a Gtk.Grid (found {type(grid)}). Integration failed."
                    )
            except KeyError:
                self.logger.warning(
                    "Calendar plugin not loaded or failed dependency check. Cannot integrate games."
                )
            except Exception as e:
                self.logger.error(f"Failed to integrate with calendar plugin: {e}")

    return EpicFreeGamesPlugin
