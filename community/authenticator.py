def get_plugin_metadata(panel):
    """
    Defines the static metadata for the Authenticator plugin.
    Args:
        panel: The main Waypanel instance containing config and handler objects.
    Returns:
        Dict: Plugin metadata.
    """
    id = "org.waypanel.plugin.authenticator"
    default_container = "top-panel-systray"
    container, id = panel.config_handler.get_plugin_container(default_container, id)
    return {
        "id": id,
        "name": "2FA Authenticator",
        "version": "1.0.0",
        "enabled": True,
        "hidden": True,
        "container": container,
        "index": 1,
        "deps": [],
        "description": "Imports otpauth URIs and generates TOTP codes via pyotp.",
    }


def get_plugin_class():
    """
    Factory function that returns the main plugin class.
    ALL necessary imports are deferred here as per Waypanel architectural constraints.
    """
    import time
    import subprocess
    import urllib.parse
    from pathlib import Path
    from typing import Any, List, Optional
    from gi.repository import Gtk, GLib  # pyright: ignore
    from src.plugins.core._base import BasePlugin
    import pyotp

    class OTPAccount:
        """
        A strongly-typed container for a single TOTP account's configuration.
        Holds the pyotp generator object directly.
        """

        def __init__(self, label: str, generator: pyotp.TOTP):
            self.label = label
            self.generator = generator
            self.otp_label_widget: Optional[Gtk.Label] = None
            self.time_label_widget: Optional[Gtk.Label] = None
            self._last_otp_counter: Optional[int] = None

        def get_current_otp(self) -> str:
            """Calculates the current TOTP code using the pyotp generator."""
            return self.generator.now()

        def get_time_remaining(self) -> int:
            """
            Calculates seconds remaining in the current time window.
            """
            period = self.generator.interval
            return int(period - (time.time() % period)) % period

    class AuthenticatorPlugin(BasePlugin):
        """
        Plugin to manage and display Time-based One-Time Passwords (TOTP)
        using Gtk.ListBox.
        """

        def __init__(self, panel_instance: Any):
            """Initializes state, the synchronous placeholder widget, and connects the click handler."""
            super().__init__(panel_instance)
            self._timer_id: Optional[int] = None
            self.accounts: List[OTPAccount] = []
            self.popover: Optional[Gtk.Popover] = None
            self._popover_content_box: Optional[Gtk.Box] = None
            self.main_button = Gtk.Button()
            self.main_icon = Gtk.Image.new_from_icon_name(
                self.gtk_helper.icon_exist("system-search-symbolic")
            )
            self.main_button.set_child(self.main_icon)
            self.main_button.set_tooltip_text("2FA: Initializing...")
            self.main_button.connect("clicked", self._on_main_button_click)
            self.main_widget = (self.main_button, "append")
            self.settings_file = self.get_plugin_setting_add_hint(
                ["settings_file"],
                ".authenticator_secrets.txt",
                "file location where contains the secrets",
            )

        def on_start(self) -> None:
            """
            Asynchronous entry point. Now executing synchronously.
            """
            self.logger.info("AuthenticatorPlugin starting...")
            success = self._load_secrets_from_file()
            self._setup_ui_and_timer(success)

        async def on_stop(self) -> None:
            """Cleanup hook. Cancels the periodic timer."""
            self._cancel_timer()
            self.logger.info("AuthenticatorPlugin stopped and timer cancelled.")

        def _get_secrets_path(self) -> Path:
            """
            Retrieves the absolute path to the secrets file defined in plugin settings.
            """
            return Path(self.settings_file).expanduser().resolve()

        def _load_secrets_from_file(self) -> bool:
            """
            Synchronously reads the secrets file and parses it line-by-line
            using pyotp.parse_uri() for generation and urllib.parse for robust label extraction.
            """
            secrets_path = self._get_secrets_path()
            if not secrets_path.exists():
                self.logger.warning(f"Secrets file not found at: {secrets_path}")
                return False
            try:
                with open(secrets_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.logger.info(f"Checking Path: {secrets_path}")
                self.logger.info(f"Raw Content Size: {len(content)} bytes")
                new_accounts: List[OTPAccount] = []
                for line in content.splitlines():
                    line = line.strip()
                    if not line.startswith("otpauth://totp/"):
                        continue
                    try:
                        generator = pyotp.parse_uri(line)
                        if not isinstance(generator, pyotp.TOTP):
                            self.logger.warning(
                                "Skipped URI: Only TOTP is supported, found non-TOTP URI."
                            )
                            continue
                        url = urllib.parse.urlparse(line)
                        query = urllib.parse.parse_qs(url.query)
                        label_path = urllib.parse.unquote(url.path.lstrip("/"))
                        issuer_query = urllib.parse.unquote(
                            query.get("issuer", [None])[0]
                            if query.get("issuer")
                            else None
                        )
                        base_label = label_path.strip().rstrip(":")
                        final_label = ""
                        if base_label and ":" in base_label:
                            final_label = base_label.strip()
                        elif base_label:
                            final_label = base_label
                        if (
                            issuer_query
                            and final_label
                            and issuer_query not in final_label
                        ):
                            final_label = f"{issuer_query}: {final_label}"
                        elif issuer_query and not final_label:
                            final_label = issuer_query
                        if final_label:
                            account = OTPAccount(label=final_label, generator=generator)
                            new_accounts.append(account)
                        else:
                            self.logger.warning(
                                f"Skipped URI: Could not determine final label for {line}"
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to parse OTP URI line: {e} - Line: {line}"
                        )
                        continue
                self.accounts = new_accounts
                self.logger.info(
                    f"Loaded {len(self.accounts)} TOTP accounts from URI file."
                )
                return True
            except Exception as e:
                self.logger.error(f"Error loading and parsing secrets URI file: {e}")
                return False

        def _setup_ui_and_timer(self, success: bool) -> None:
            """Updates the main button properties. Timer setup is moved to _on_main_button_click."""
            if not success or not self.accounts:
                self.main_button.set_tooltip_text(
                    f"2FA: No accounts. Place file at: {self._get_secrets_path()}"
                )
                self.main_icon.set_from_icon_name(
                    self.gtk_helper.icon_exist("dialog-warning-symbolic")
                )
                return
            self.main_icon.set_from_icon_name(
                self.gtk_helper.icon_exist("lock-symbolic", "security-medium-symbolic")
            )
            self.main_button.set_tooltip_text(
                f"Authenticator ({len(self.accounts)} accounts)"
            )

        def _on_main_button_click(self, button: Gtk.Button) -> None:
            """
            Handles the Gtk.Button 'clicked' signal, managing the popover and the timer lifecycle.
            """
            if not self.accounts:
                self.notifier.notify_send(
                    "2FA Authenticator",
                    f"Setup Required: Place secrets file at {self._get_secrets_path()}",
                    "dialog-warning-symbolic",
                )
                return
            if self.popover and self.popover.is_visible():
                self.popover.popdown()
                self._cancel_timer()
                return
            if not self.popover:
                self._create_popover_content(button)
            if self.popover:
                self._refresh_timer_callback()
                if not self._timer_id:
                    self._timer_id = GLib.timeout_add_seconds(
                        1, self._refresh_timer_callback
                    )
                self.popover.popup()

        def _create_popover_content(self, parent_widget: Gtk.Button) -> None:
            """
            Manually creates the popover and its content (Gtk.ListBox with columns).
            """
            self.popover = Gtk.Popover.new()
            self.popover.set_parent(parent_widget)
            self.popover.set_size_request(300, -1)
            scrolled_window = Gtk.ScrolledWindow()
            scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scrolled_window.set_max_content_height(400)
            scrolled_window.set_propagate_natural_height(True)
            list_box = Gtk.ListBox()
            list_box.add_css_class("authenticator-list-box")
            list_box.set_selection_mode(Gtk.SelectionMode.NONE)
            list_box.set_margin_start(10)
            list_box.set_margin_end(10)
            for account in self.accounts:
                row_widget = self._create_account_row(account)
                list_box.append(row_widget)
            scrolled_window.set_child(list_box)
            self.popover.set_child(scrolled_window)

        def _create_account_row(self, account: OTPAccount) -> Gtk.ListBoxRow:
            """
            Creates a single Gtk.ListBoxRow simulating two columns (Label, Code).
            """
            list_box_row = Gtk.ListBoxRow()
            h_grid = Gtk.Grid(column_spacing=10)
            h_grid.set_hexpand(True)
            h_grid.add_css_class("authenticator-account-row")
            label = Gtk.Label(label=account.label)
            label.set_halign(Gtk.Align.START)
            label.set_hexpand(True)
            label.set_margin_start(5)
            gesture_label = Gtk.GestureClick.new()
            gesture_label.connect(
                "released", lambda g, n, x, y, acc=account: self._on_otp_copied(acc)
            )
            label.add_controller(gesture_label)
            label.set_tooltip_text(f"Click to copy OTP code for {account.label}")
            h_grid.attach(label, 0, 0, 1, 1)
            otp_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            otp_box.set_hexpand(False)
            otp_box.set_halign(Gtk.Align.END)
            otp_box.set_margin_end(5)
            time_label = Gtk.Label(label=f"{account.generator.interval}s")
            time_label.add_css_class("authenticator-timer")
            otp_box.append(time_label)
            account.time_label_widget = time_label
            otp_label = Gtk.Label(label=account.get_current_otp())
            otp_label.add_css_class("authenticator-otp-code")
            otp_label.add_css_class("mono")
            otp_box.append(otp_label)
            account.otp_label_widget = otp_label
            h_grid.attach(otp_box, 1, 0, 1, 1)
            list_box_row.set_child(h_grid)
            return list_box_row

        def _on_dashboard_action(self, _, action_label: str) -> None:
            """Action handler (not strictly used, but required by helper)."""
            self.logger.warning(
                f"Unexpected dashboard action triggered: {action_label}"
            )
            if self.popover:
                self.popover.popdown()

        def _on_otp_copied(self, account: OTPAccount) -> None:
            """
            Copies the current OTP code to the Wayland clipboard using wl-copy
            and provides user feedback.
            """
            current_otp = account.get_current_otp()
            try:
                subprocess.run(
                    ["wl-copy"],
                    input=current_otp.encode("utf-8"),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1,
                )
                self.logger.info(f"Copied OTP for {account.label} via wl-copy.")
                self.notifier.notify_send(
                    "2FA Authenticator",
                    f"Copied OTP for {account.label}",
                    "security-low-symbolic",
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to copy OTP for {account.label} using wl-copy: {e}"
                )
                try:
                    self.gtk_helper.set_clipboard_text(current_otp)
                    self.logger.warning(
                        "wl-copy failed, fell back to gtk_helper clipboard."
                    )
                    self.notifier.notify_send(
                        "2FA Authenticator",
                        f"Copied OTP (via fallback) for {account.label}",
                        "security-low-symbolic",
                    )
                except Exception:
                    self.notifier.notify_send(
                        "2FA Authenticator",
                        "Copy Failed: Could not execute wl-copy or fallback.",
                        "dialog-error-symbolic",
                    )
            if self.popover:
                self.popover.popdown()

        def _refresh_timer_callback(self) -> bool:
            """
            Callback function executed every second to update codes and timers.
            NOW uses counter comparison for guaranteed label update.
            """
            current_time = time.time()
            for account in self.accounts:
                if not account.otp_label_widget:
                    continue
                current_time_remaining = account.get_time_remaining()
                generator_interval = account.generator.interval
                new_counter = int(current_time // generator_interval)
                if (
                    account._last_otp_counter is None
                    or new_counter != account._last_otp_counter
                ):
                    new_otp = account.get_current_otp()
                    self.update_widget_safely(
                        account.otp_label_widget.set_label, new_otp
                    )
                    account._last_otp_counter = new_counter
                    account.time_label_widget.remove_css_class("warning")
                self.update_widget_safely(
                    account.time_label_widget.set_label, f"{current_time_remaining}s"
                )
                if current_time_remaining <= 5:
                    account.time_label_widget.add_css_class("warning")
                else:
                    account.time_label_widget.remove_css_class("warning")
            return GLib.SOURCE_CONTINUE

        def _cancel_timer(self) -> None:
            """Safely removes the GLib timer resource."""
            if self._timer_id:
                GLib.source_remove(self._timer_id)
                self._timer_id = None
                self._timer_id = None

    return AuthenticatorPlugin
