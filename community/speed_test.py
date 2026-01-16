def get_plugin_metadata(_) -> dict:
    return {
        "id": "org.waypanel.plugin.internet_speed_test",
        "name": "Internet Speed Tester",
        "version": "1.0.0",
        "enabled": True,
        "deps": ["event_manager"],
        "description": "Periodically tests internet speed without blocking the UI.",
    }


def get_plugin_class() -> type:
    import threading
    import psutil
    from typing import Any, Optional, Dict
    from src.plugins.core._base import BasePlugin

    _NETWORK_USAGE_THRESHOLD_MBPS: float = 10.0
    _RETRY_DELAY_SECONDS: int = 30
    _TEST_INTERVAL_SECONDS: int = 1800
    _SLOW_SPEED_THRESHOLD_MBPS: float = 100.0

    class InternetSpeedTesterPlugin(BasePlugin):
        """
        A background plugin for non-blocking network performance monitoring.
        """

        def __init__(self, panel_instance: Any) -> None:
            """
            Initializes the plugin state.
            Args:
                panel_instance: The Waypanel instance.
            """
            super().__init__(panel_instance)
            self._timer_source_id: Optional[int] = None

        def on_start(self):
            def run_once():
                if self.module_exist("speedtest"):
                    import speedtest

                    self.speedtest = speedtest
                    self.glib.timeout_add_seconds(
                        _TEST_INTERVAL_SECONDS, self._schedule_speed_test
                    )
                else:
                    self.plugin_loader.disable_plugin("speed_test")
                return False  # stop glib loop

            self.glib.idle_add(run_once)

        def on_stop(self) -> None:
            """
            The asynchronous deactivation method. Cleans up all self.glib timers.
            """
            if self._timer_source_id:
                self.glib.source_remove(self._timer_source_id)
                self._timer_source_id = None
            self.logger.info("Lifecycle: Plugin stopped and resources cleaned.")

        def _schedule_speed_test(self) -> bool:
            """
            Schedules the network usage check process on the main thread's idle loop.
            Returns:
                bool: True to ensure the self.glib timeout reschedules itself.
            """
            self.glib.idle_add(self._check_network_usage)
            return True

        def _check_network_usage(self) -> bool:
            """
            Starts the two-stage network utilization check by measuring the initial state.
            Returns:
                bool: False to prevent rescheduling.
            """
            try:
                net_io = psutil.net_io_counters()
                bytes_sent = net_io.bytes_sent
                bytes_recv = net_io.bytes_recv
                self.glib.timeout_add_seconds(
                    1, self._calculate_network_rate, bytes_sent, bytes_recv
                )
            except Exception as e:
                self.logger.error(f"Error checking initial network usage: {e}")
            return False

        def _calculate_network_rate(
            self, prev_bytes_sent: int, prev_bytes_recv: int
        ) -> bool:
            """
            Calculates the network usage rate and decides whether to run the speed test or retry.
            Args:
                prev_bytes_sent: Bytes sent at the start of the interval.
                prev_bytes_recv: Bytes received at the start of the interval.
            Returns:
                bool: False to prevent rescheduling.
            """
            try:
                net_io = psutil.net_io_counters()
                sent_per_sec = net_io.bytes_sent - prev_bytes_sent
                recv_per_sec = net_io.bytes_recv - prev_bytes_recv
                total_mbps = (sent_per_sec + recv_per_sec) * 8 / 1_000_000
                if total_mbps < _NETWORK_USAGE_THRESHOLD_MBPS:
                    self.logger.info(
                        f"Network usage: {total_mbps:.2f} Mbps. Proceeding with speed test."
                    )
                    self.glib.idle_add(self._run_speed_test)
                else:
                    self.logger.info(
                        f"Network usage: {total_mbps:.2f} Mbps. Retrying in {_RETRY_DELAY_SECONDS}s."
                    )
                    self.glib.timeout_add_seconds(
                        _RETRY_DELAY_SECONDS, self._check_network_usage
                    )
            except Exception as e:
                self.logger.error(f"Error calculating network rate: {e}")
            return False

        def _run_speed_test(self) -> bool:
            """
            Initiates the internet speed test in a background thread to maintain main thread responsiveness.
            Returns:
                bool: False to prevent rescheduling.
            """

            def _run_test_in_thread():
                """The I/O-heavy operation target for the thread."""
                try:
                    self.logger.info("Starting internet speed test...")
                    st = self.speedtest.Speedtest()
                    st.get_best_server()
                    download_speed = st.download() / 1_000_000
                    upload_speed = st.upload() / 1_000_000
                    self.glib.idle_add(
                        self._check_and_notify, download_speed, upload_speed
                    )
                except Exception as e:
                    self.logger.error(f"An error occurred during the speed test: {e}")

            thread = threading.Thread(target=_run_test_in_thread, daemon=True)
            thread.start()
            return False

        def _check_and_notify(self, download_speed: float, upload_speed: float) -> bool:
            """
            Checks results against the threshold and sends a notification.
            Args:
                download_speed: The measured download speed in Mbps.
                upload_speed: The measured upload speed in Mbps.
            Returns:
                bool: False to prevent rescheduling.
            """
            try:
                is_slow = (download_speed < _SLOW_SPEED_THRESHOLD_MBPS) or (
                    upload_speed < _SLOW_SPEED_THRESHOLD_MBPS
                )
                focused_view: Optional[Dict[str, Any]] = self.ipc.get_focused_view()
                is_fullscreen: bool = focused_view and focused_view.get(
                    "fullscreen", False
                )  # pyright: ignore
                if is_slow and not is_fullscreen:
                    message = f"⚠️ Slow Internet! Down: {download_speed:.2f} Mbps | Up: {upload_speed:.2f} Mbps"
                    self.notify_send("Internet Speed Test", message)
                    self.logger.info("Notification sent about slow internet speed.")
                elif is_fullscreen:
                    self.logger.info(
                        "Focused view is fullscreen. Skipping notification."
                    )
                else:
                    self.logger.info(
                        "Internet speed is above threshold. No notification sent."
                    )
            except Exception as e:
                self.logger.error(f"Error checking or sending notification: {e}")
            return False

    return InternetSpeedTesterPlugin
