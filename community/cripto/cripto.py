DEFAULT_UPDATE_INTERVAL = 1800
DEFAULT_CRYPTOS = "XRPUSDT, BTCUSDT, HBARUSDT, VETUSDT"
DEFAULT_API_URL = "https://api.binance.com/api/v3/ticker/price"
DEFAULT_ICON_NAME = "wallet-open-symbolic"
DEFAULT_BTC_FORMAT_K = True
DEFAULT_ICON_CDN = "https://cdn.jsdelivr.net/gh/vadimmalykhin/binance-icons/crypto/"


def get_plugin_metadata(panel):
    id = "org.waypanel.plugin.cripto"
    default_container = "background"
    container, id = panel.config_handler.get_plugin_container(default_container, id)
    return {
        "id": id,
        "name": "Cripto Ticker",
        "version": "2.1.0",
        "enabled": True,
        "hidden": False,
        "container": container,
        "index": 3,
        "deps": ["requests", "calendar", "css_generator"],
        "description": "A cryptocurrency price ticker that fetches data from the Binance API and integrates directly into the Calendar popover.",
    }


def get_plugin_class():
    """
    Factory function that returns the main plugin class.
    ALL imports are strictly deferred here.
    """
    from typing import Any, Optional, Dict, List, cast
    from src.plugins.core._base import BasePlugin
    from gi.repository import Gtk, GLib  # pyright: ignore
    from pathlib import Path

    class CriptoPlugin(BasePlugin):
        """
        A cryptocurrency price ticker that fetches data asynchronously from the
        Binance API and integrates directly into the Calendar plugin's popover
        for a consolidated view, including cached icons.
        """

        _update_interval: int
        _cryptos_to_track_str: str
        _api_url: str
        _panel_icon_name: str
        _btc_format_k: bool
        _cryptos_to_track: List[str]
        _icon_paths: Dict[str, str]

        def __init__(self, panel_instance: Any):
            """
            Initializes the plugin's state. Configuration loading is performed
            here by leveraging the return value of get_plugin_setting_add_hint.
            """
            super().__init__(panel_instance)
            interval_raw = self.get_plugin_setting_add_hint(
                ["update-interval"],
                DEFAULT_UPDATE_INTERVAL,
                "How often to fetch new prices from the API, in seconds. This setting is used in control-center.",
            )
            self._update_interval = int(interval_raw)
            self._cryptos_to_track_str = self.get_plugin_setting_add_hint(
                ["tracked-symbols"],
                DEFAULT_CRYPTOS,
                "A comma-separated list of symbols to track (e.g., ADAUSDT, ETHUSDT). This setting is used in control-center.",
            )
            self._api_url = self.get_plugin_setting_add_hint(
                ["api-url"],
                DEFAULT_API_URL,
                "The URL for fetching ticker prices. Only change if necessary. This setting is used in control-center.",
            )
            self._panel_icon_name = self.get_plugin_setting_add_hint(
                ["panel-icon-name"],
                DEFAULT_ICON_NAME,
                "The GTK symbolic icon name for the main button. This setting is used in control-center.",
            )
            btc_format_raw = self.get_plugin_setting_add_hint(
                ["btc-format-k"],
                DEFAULT_BTC_FORMAT_K,
                "If True, BTC prices >= 1000 will be shown in 'K' notation (e.g., 65.5K). This setting is used in control-center.",
            )
            self._btc_format_k = bool(btc_format_raw)
            self._cryptos_to_track = [
                s.strip().upper()
                for s in self._cryptos_to_track_str.split(",")
                if s.strip()
            ]
            self._icon_paths = {symbol: "" for symbol in self._cryptos_to_track}
            self.main_button: Optional[Gtk.Button] = None
            self.crypto_labels: Dict[str, Gtk.Label] = {}
            self.update_timeout_id: Optional[int] = None
            self.current_prices: Dict[str, str] = {
                symbol: "Fetching..." for symbol in self._cryptos_to_track
            }
            self.logger.info(
                "CriptoPlugin initialized and settings loaded via hint API."
            )

        def on_start(self) -> None:
            """
            Asynchronous entry point. Creates the UI indicator, integrates with the
            calendar, and starts the background data tasks (icon cache and price updates).
            """
            self.plugins["css_generator"].install_css("main.css")
            self.logger.info("Lifecycle: CriptoPlugin starting.")
            self._setup_ui()
            self.run_in_thread(self._fetch_and_cache_icons)
            self._start_updates()
            self.schedule_in_gtk_thread(self._integrate_with_calendar)

        def on_stop(self) -> None:
            """
            Asynchronous cleanup hook. Stops the GLib timer to prevent resource leaks.
            """
            self.logger.info("Lifecycle: CriptoPlugin stopping.")
            if self.update_timeout_id:
                GLib.source_remove(self.update_timeout_id)
                self.update_timeout_id = None
            self.logger.info("CriptoPlugin update timer stopped.")

        def _setup_ui(self) -> None:
            """Constructs the main panel button (now only an indicator)."""
            icon_name = self.gtk_helper.icon_exist(
                self._panel_icon_name, "emblem-money"
            )
            self.main_button = Gtk.Button.new_from_icon_name(icon_name)
            self.main_button.set_tooltip_text(
                "Cryptocurrency Prices (integrated into Calendar popover)"
            )
            self.main_button.add_css_class("cripto-indicator-button")
            self.add_cursor_effect(self.main_button)
            self.main_widget = (self.main_button, "append")

        def _fetch_and_cache_icons(self) -> None:
            """
            [NON-BLOCKING] Runs in a background thread. Downloads and caches SVG icons
            to a local directory using the standard pathlib approach.
            """
            from pathlib import Path

            try:
                cache_dir = (
                    Path(
                        self.panel_instance.config_handler.plugin_config_path(
                            self.get_plugin_id()
                        )
                    )
                    / "icons"
                )
            except AttributeError:
                cache_dir = Path.home() / ".config" / "waypanel" / "cripto_icons"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Icon cache directory: {cache_dir}")
            for symbol in self._cryptos_to_track:
                base_symbol = symbol.replace("USDT", "")
                local_path = cache_dir / f"{base_symbol.lower()}.svg"
                if local_path.exists():
                    self._icon_paths[symbol] = str(local_path)
                    continue
                try:
                    url = f"{DEFAULT_ICON_CDN}{base_symbol.lower()}.svg"
                    response = self.requests.get(url, timeout=5)
                    if response.status_code == 200:
                        local_path.write_bytes(response.content)
                        self._icon_paths[symbol] = str(local_path)
                        self.logger.info(
                            f"Successfully cached icon for {symbol} to {local_path}."
                        )
                    else:
                        self.logger.warning(
                            f"No icon found for {symbol} (HTTP {response.status_code})."
                        )
                        self._icon_paths[symbol] = ""
                except Exception as e:
                    self.logger.warning(
                        f"Failed to fetch and cache icon for {symbol}: {e}"
                    )
                    self._icon_paths[symbol] = ""

        def _schedule_next_fetch(self) -> bool:
            """
            Executes the fetch operation in a background thread and ensures
            the timer is rescheduled by returning True.
            """
            self.run_in_thread(self._fetch_and_update_prices)
            return True

        def _start_updates(self):
            """Schedules the recurring, non-blocking price fetch operation."""
            self.run_in_thread(self._fetch_and_update_prices)
            self.update_timeout_id = GLib.timeout_add_seconds(
                self._update_interval,
                self._schedule_next_fetch,
            )

        def _fetch_and_update_prices(self) -> None:
            """
            [NON-BLOCKING] Runs in a background thread. Fetches and schedules
            the UI update.
            """
            self.logger.info("Fetching latest crypto prices in background thread.")
            try:
                prices = self._fetch_prices_from_api(self._cryptos_to_track)
                self.schedule_in_gtk_thread(self._update_labels, prices)
            except Exception as e:
                self.logger.error(f"Failed to fetch or update prices: {e}")

        def _fetch_prices_from_api(self, symbols: List[str]) -> Dict[str, str]:
            """
            Performs the synchronous network request. MUST be run in a thread.
            """
            prices: Dict[str, str] = {}
            for symbol in symbols:
                try:
                    response = self.requests.get(
                        self._api_url, params={"symbol": symbol}, timeout=10
                    )
                    response.raise_for_status()
                    data = response.json()
                    price = float(data["price"])
                    prices[symbol] = self._format_price(price, symbol)
                except getattr(
                    self.requests.exceptions, "RequestException", Exception
                ) as e:
                    self.logger.warning(f"Error fetching {symbol} price: {e}")
                    prices[symbol] = "Error"
            return prices

        def _format_price(self, price: float, symbol: str) -> str:
            """
            Formats a price float into a display string.
            """
            if symbol == "BTCUSDT" and self._btc_format_k:
                return f"{price / 1000:.2f}K" if price >= 1000 else f"{price:.2f}"
            if price < 0.1:
                return f"{price:.3f}"
            return f"{price:.2f}"

        def _update_labels(self, new_prices: Dict[str, str]) -> None:
            """[UI THREAD ONLY] Updates persistent data and Gtk.Label widgets."""
            self.logger.info("Updating UI labels and persistent data on GTK thread.")
            self.current_prices.update(new_prices)
            if not self.crypto_labels:
                self.logger.info("Labels not yet created. Skipping Gtk widget update.")
                return
            for symbol, price_str in new_prices.items():
                label = self.crypto_labels.get(symbol)
                if label:
                    concise_symbol = symbol.replace("USDT", "")
                    label.set_label(f"{concise_symbol}: ${price_str}")

        def _build_crypto_vbox(self) -> Gtk.Box:
            """
            [UI THREAD ONLY] Constructs the Gtk.Box containing the title,
            all the cryptocurrency labels and icons.
            """
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            vbox.set_margin_top(10)
            vbox.set_margin_bottom(10)
            vbox.set_margin_start(15)
            vbox.set_margin_end(15)
            vbox.add_css_class("cripto-list-container")
            header_label = Gtk.Label(label="Crypto Market Watch", xalign=0.0)
            header_label.add_css_class("cripto-header")
            header_label.set_margin_bottom(5)
            vbox.append(header_label)
            separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            separator.set_margin_bottom(10)
            vbox.append(separator)
            for crypto in self._cryptos_to_track:
                initial_price_str = self.current_prices.get(crypto, "Error")
                concise_symbol = crypto.replace("USDT", "")
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                hbox.add_css_class("cripto-hbox")
                image = Gtk.Image()
                icon_path = self._icon_paths.get(crypto, "")
                if icon_path and Path(icon_path).exists():
                    image.set_from_file(icon_path)
                else:
                    image.set_from_icon_name("image-missing-symbolic")
                image.set_pixel_size(16)
                image.add_css_class("cripto-icon")
                label_text = f"{concise_symbol}: ${initial_price_str}"
                label = Gtk.Label(label=label_text, xalign=0.0)
                label.add_css_class("cripto-item-label")
                label.add_css_class(f"cripto-symbol-{crypto.lower()}")
                self.crypto_labels[crypto] = label
                hbox.append(image)
                hbox.append(label)
                vbox.append(hbox)
            return vbox

        def _integrate_with_calendar(self) -> None:
            """
            [UI THREAD ONLY] Integrates the cryptocurrency VBox into the calendar
            plugin's popover grid at the specified position (2, 0).
            """
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
                    crypto_vbox = self._build_crypto_vbox()
                    grid.attach(crypto_vbox, 2, 0, 1, 1)
                    crypto_vbox.show()
                    self.logger.info(
                        "Successfully integrated crypto prices into Calendar popover at grid position (2, 0)."
                    )
                else:
                    self.logger.warning(
                        f"Calendar popover child is not a Gtk.Grid (found {type(grid)}). Integration failed."
                    )
            except KeyError:
                self.logger.warning(
                    "Calendar plugin not loaded or failed dependency check. Cannot integrate prices."
                )
            except Exception as e:
                self.logger.error(f"Failed to integrate with calendar plugin: {e}")

    return CriptoPlugin
