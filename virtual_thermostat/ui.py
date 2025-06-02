#!/usr/bin/env python3
"""
Trame-based Web Controller for Virtual Thermostat
Provides a web interface to monitor and control the thermostat state.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from trame.app import get_server, asynchronous
from trame.ui.vuetify import SinglePageLayout
from trame.widgets import html, vuetify

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("thermostat-controller")

DEFAULT_CONFIG_FILE = "config/vthermostat_config.json"
DEFAULT_STATE_FILE = "config/vthermostat_state.json"


def save_config(config, config_file=DEFAULT_CONFIG_FILE):
    """Save configuration to file."""
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Error saving config: {e}")
        return False


def read_config(config_file=DEFAULT_CONFIG_FILE):
    """Read configuration from file."""
    config_path = Path(config_file)
    if not config_path.exists():
        logger.error(f"Config file {config_file} not found")
        return None

    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error reading config: {e}")
        return None


def load_state(state_file=DEFAULT_STATE_FILE):
    """Load state from file."""
    state_path = Path(state_file)
    if not state_path.exists():
        return {"last_ac_state": False, "last_run": None}

    try:
        with open(state_path, "r") as f:
            state = json.load(f)
            return state
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading state: {e}")
        return {"last_ac_state": False, "last_run": None}


def save_state(state, state_file=DEFAULT_STATE_FILE):
    """Save state to file."""
    try:
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Error saving state: {e}")
        return False


class ThermostatController:
    def __init__(self):
        self.server = get_server(client_type="vue2")
        self.state = self.server.state

        # Add our arguments to trame's CLI
        self.server.cli.add_argument(
            "--config",
            default=DEFAULT_CONFIG_FILE,
            help=f"Path to config file (default: {DEFAULT_CONFIG_FILE})",
        )
        self.server.cli.add_argument(
            "--state",
            default=DEFAULT_STATE_FILE,
            help=f"Path to state file (default: {DEFAULT_STATE_FILE})",
        )

        # Parse arguments
        args, _ = self.server.cli.parse_known_args()
        self.config_file = args.config
        self.state_file = args.state

        # Load initial data
        self.config = read_config(self.config_file)
        self.current_state = load_state(self.state_file)

        if not self.config:
            logger.error("Could not load configuration")
            sys.exit(1)

        # Initialize server state
        self.update_server_state()

        # Set up callbacks
        self.state.change("enabled")(self.on_enabled_change)
        self.state.change("desired_temperature_display")(
            self.on_desired_temperature_change
        )
        self.state.change("display_fahrenheit")(self.on_display_unit_change)
        self.state.change("cooldown_minutes")(self.on_cooldown_change)
        self.state.change("auto_refresh_enabled")(self.on_auto_refresh_change)

        # Start background autorefresh thread
        self.running = True
        self.auto_refresh_enabled = True
        self._update_task = asynchronous.create_task(self.background_refresh())

    def celsius_to_fahrenheit(self, celsius):
        """Convert Celsius to Fahrenheit."""
        if isinstance(celsius, (int, float)):
            return round(celsius * 9 / 5 + 32, 1)
        return celsius

    def fahrenheit_to_celsius(self, fahrenheit):
        """Convert Fahrenheit to Celsius."""
        if isinstance(fahrenheit, (int, float)):
            return round((fahrenheit - 32) * 5 / 9, 1)
        return fahrenheit

    def get_display_temp(self, celsius_temp):
        """Get temperature in display unit."""
        display_fahrenheit = getattr(self.state, "display_fahrenheit", False)
        if display_fahrenheit:
            return self.celsius_to_fahrenheit(celsius_temp)
        return celsius_temp

    def get_display_unit(self):
        """Get display unit symbol."""
        display_fahrenheit = getattr(self.state, "display_fahrenheit", False)
        return "F" if display_fahrenheit else "C"

    def update_server_state(self):
        """Update trame server state with current thermostat data."""
        display_fahrenheit = self.current_state.get("display_fahrenheit", False)
        desired_temperature_c = self.config.get("desired_temperature", 24)
        last_temp = self.current_state.get("last_temperature", "Unknown")

        # Format temperature display
        if isinstance(last_temp, (int, float)):
            last_temp_display = f"{self.get_display_temp(last_temp)}"
        else:
            last_temp_display = str(last_temp)

        self.state.update(
            {
                "enabled": self.config.get("enabled", True),
                "last_ac_state": self.current_state.get("last_ac_state", False),
                "last_run": self.current_state.get("last_run", "Never"),
                "last_temperature": last_temp_display,
                "desired_temperature_display": self.get_display_temp(
                    desired_temperature_c
                ),
                "display_fahrenheit": display_fahrenheit,
                "host": self.config.get("host", "Unknown"),
                "cooldown_minutes": self.config.get("cooldown_minutes", 15),
                "display_unit": self.get_display_unit(),
                "ac_state_text": (
                    "ON" if self.current_state.get("last_ac_state", False) else "OFF"
                ),
                "last_refresh": getattr(self.state, "last_refresh", "Never"),
                "auto_refresh_enabled": getattr(self, "auto_refresh_enabled", True),
            }
        )

    def on_enabled_change(self, enabled, **kwargs):
        """Handle enabled/disabled toggle."""
        self.config["enabled"] = enabled
        if self.save_config():
            logger.info(f"Thermostat {'enabled' if enabled else 'disabled'}")
        else:
            logger.error("Failed to save config")

    def on_desired_temperature_change(self, desired_temperature_display, **kwargs):
        """Handle desired temperature change (convert from display unit to Celsius)."""
        display_fahrenheit = getattr(self.state, "display_fahrenheit", False)
        if display_fahrenheit:
            desired_temperature_c = self.fahrenheit_to_celsius(
                desired_temperature_display
            )
        else:
            desired_temperature_c = desired_temperature_display

        self.config["desired_temperature"] = desired_temperature_c
        if self.save_config():
            logger.info(
                f"Desired temperature set to {desired_temperature_c}°C "
                f"({desired_temperature_display}°{self.get_display_unit()})"
            )
        else:
            logger.error("Failed to save config")

    def on_display_unit_change(self, display_fahrenheit, **kwargs):
        """Handle display unit toggle change."""
        self.current_state["display_fahrenheit"] = display_fahrenheit

        # Update display temperatures and unit
        desired_temperature_c = self.config.get("desired_temperature", 24)
        self.state.desired_temperature_display = self.get_display_temp(
            desired_temperature_c
        )
        self.state.display_unit = self.get_display_unit()

        # Update current temperature display if it's a numeric value
        last_temp = self.current_state.get("last_temperature")
        if isinstance(last_temp, (int, float)):
            self.state.last_temperature = f"{self.get_display_temp(last_temp)}"

        if save_state(self.current_state, self.state_file):
            unit = "Fahrenheit" if display_fahrenheit else "Celsius"
            logger.info(f"Display unit changed to {unit}")
        else:
            logger.error("Failed to save state")

    def on_cooldown_change(self, cooldown_minutes, **kwargs):
        """Handle cooldown time change."""
        self.config["cooldown_minutes"] = cooldown_minutes
        if self.save_config():
            logger.info(f"Cooldown time set to {cooldown_minutes} minutes")
        else:
            logger.error("Failed to save config")

    def on_auto_refresh_change(self, auto_refresh_enabled, **kwargs):
        """Handle auto refresh toggle change."""
        self.auto_refresh_enabled = auto_refresh_enabled
        logger.info(f"Auto refresh {'enabled' if auto_refresh_enabled else 'disabled'}")

    def save_config(self):
        """Save current config to file."""
        return save_config(self.config, self.config_file)

    async def _update_points(self):
        with self.state:
            self.state.is_loading = True
            self.points_sources = {}
            self.clear_points_transformations()
        # Don't lock server before enabling the spinner on client
        await self.server.network_completion

        self.save_embedding_params()

        with self.state:
            self.compute_source_points()
            self.update_transformed_points(self.transformed_images.transformed_features)
            self.state.is_loading = False

    def update_points(self, **kwargs):
        if hasattr(self, "_update_task"):
            self._update_task.cancel()
        self._update_task = asynchronous.create_task(self._update_points())

    def refresh_data(self):
        """Refresh data from state file."""
        self.current_state = load_state(self.state_file)
        self.config = read_config(self.config_file)
        self.update_server_state()
        self.state.last_refresh = datetime.now().strftime("%H:%M:%S")
        logger.debug("Manual data refresh completed")

    async def background_refresh(self):
        """Background thread for auto-refresh."""
        # Initial delay
        await asyncio.sleep(1)
        while self.running:
            try:
                if self.auto_refresh_enabled:
                    with self.state:
                        self.refresh_data()

                    # Don't lock server before enabling the spinner on client
                    await self.server.network_completion
                    logger.debug("Background auto-refresh executed")
            except Exception as e:
                logger.error(f"Error in background refresh: {e}")
            await asyncio.sleep(5)  # Refresh every 5 seconds

    def create_ui(self):
        """Create the web UI."""
        with SinglePageLayout(self.server, theme={"dark": True}) as layout:
            layout.title.set_text("Virtual Thermostat Controller")

            with layout.content:
                with vuetify.VContainer():
                    # Header
                    with vuetify.VRow():
                        with vuetify.VCol():
                            html.H1(
                                "Virtual Thermostat Controller", classes="text-center"
                            )

                    # Control Card
                    with vuetify.VRow():
                        with vuetify.VCol():
                            with vuetify.VCard():
                                vuetify.VCardTitle("Controls")
                                with vuetify.VCardText():
                                    with vuetify.VRow():
                                        with vuetify.VCol(cols=12, sm=6, md=4):
                                            vuetify.VSwitch(
                                                v_model=("enabled",),
                                                label="Enable Thermostat",
                                                color="primary",
                                            )
                                    with vuetify.VRow():
                                        with vuetify.VCol(cols=12):
                                            html.Div(
                                                "Desired Temperature: {{ desired_temperature_display }}°{{ display_unit }}"
                                            )
                                            vuetify.VSlider(
                                                v_model=(
                                                    "desired_temperature_display",
                                                ),
                                                min=18,
                                                max=30,
                                                step=1.0,
                                                thumb_label=True,
                                                color="primary",
                                            )
                    # Status Card
                    with vuetify.VRow():
                        with vuetify.VCol():
                            with vuetify.VCard():
                                vuetify.VCardTitle("Current Status")
                                with vuetify.VCardText():
                                    with vuetify.VRow():
                                        with vuetify.VCol(cols=6):
                                            html.P("Host: {{ host }}")
                                            html.P(
                                                "Last Temperature: {{ last_temperature }}°{{ display_unit }}"
                                            )
                                            html.P(
                                                "Desired Temperature: {{ desired_temperature_display }}°{{ display_unit }}"
                                            )
                                            html.P(
                                                "Cooldown: {{ cooldown_minutes }} minutes"
                                            )
                                        with vuetify.VCol(cols=6):
                                            html.P("AC State: {{ ac_state_text }}")
                                            html.P("Last Run: {{ last_run }}")
                                            html.P(
                                                "Last Refresh: {{ last_refresh }}",
                                                style="font-size: 12px; color: #666;",
                                            )

                    # Control Card
                    with vuetify.VRow():
                        with vuetify.VCol():
                            with vuetify.VCard():
                                vuetify.VCardTitle("Settings")
                                with vuetify.VCardText():
                                    with vuetify.VRow():
                                        with vuetify.VCol(cols=12, sm=6, md=4):
                                            vuetify.VSwitch(
                                                v_model=("display_fahrenheit",),
                                                label="Display in Fahrenheit",
                                                color="secondary",
                                            )
                                        with vuetify.VCol(cols=12, sm=12, md=4):
                                            vuetify.VSwitch(
                                                v_model=("auto_refresh_enabled",),
                                                label="Auto Refresh",
                                                color="success",
                                            )
                                    with vuetify.VRow():
                                        with vuetify.VCol(cols=12):
                                            html.Div(
                                                "Cooldown Time: {{ cooldown_minutes }} minutes"
                                            )
                                            vuetify.VSlider(
                                                v_model=("cooldown_minutes",),
                                                min=1,
                                                max=15,
                                                step=1,
                                                thumb_label=True,
                                                color="secondary",
                                            )

    def start(self):
        """Start the web server."""
        self.create_ui()
        logger.info("Starting thermostat controller")
        self.server.start()


def main():
    """Main function."""
    controller = ThermostatController()
    controller.start()


if __name__ == "__main__":
    main()
