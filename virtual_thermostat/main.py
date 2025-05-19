#!/usr/bin/env python3
"""
Virtual Thermostat - A daemon for controlling smart plugs based on temperature.
"""

import asyncio
import argparse
import json
import logging
import re
import sys
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

import requests
from kasa import SmartPlug

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("virtual-thermostat")


class TempUnit(str, Enum):
    """Temperature unit."""

    CELSIUS = "C"
    FAHRENHEIT = "F"


# Default settings
DEFAULT_TEMP_UNIT = TempUnit.FAHRENHEIT
DEFAULT_TEMP_THRESHOLD_LOW_F = 75  # Default in Fahrenheit
DEFAULT_TEMP_THRESHOLD_HIGH_F = 80  # Default in Fahrenheit
DEFAULT_TEMP_THRESHOLD_LOW_C = 24  # Default in Celsius
DEFAULT_TEMP_THRESHOLD_HIGH_C = 27  # Default in Celsius
DEFAULT_COOLDOWN_MINUTES = 360  # 6 hours
DEFAULT_STATE_FILE = "vthermostat_state.json"
DEFAULT_CHECK_INTERVAL = 600  # 10 minutes


def convert_temperature(temp, from_unit, to_unit):
    """Convert temperature between Celsius and Fahrenheit."""
    if from_unit == to_unit:
        return temp

    if from_unit == TempUnit.FAHRENHEIT and to_unit == TempUnit.CELSIUS:
        # F to C: (F - 32) * 5/9
        return (temp - 32) * 5 / 9
    else:
        # C to F: (C * 9/5) + 32
        return (temp * 9 / 5) + 32


class VirtualThermostat:
    """Control a smart plug based on temperature."""

    def __init__(
        self,
        host,
        zipcode,
        state_file=DEFAULT_STATE_FILE,
        cooldown_minutes=DEFAULT_COOLDOWN_MINUTES,
        temp_low=None,
        temp_high=None,
        temp_unit=DEFAULT_TEMP_UNIT,
    ):
        self.host = host
        self.zipcode = zipcode
        self.state_file = Path(state_file)
        self.cooldown_minutes = cooldown_minutes
        self.temp_unit = temp_unit

        # Set temperature thresholds based on unit
        if temp_low is None:
            self.temp_threshold_low = (
                DEFAULT_TEMP_THRESHOLD_LOW_F
                if temp_unit == TempUnit.FAHRENHEIT
                else DEFAULT_TEMP_THRESHOLD_LOW_C
            )
        else:
            self.temp_threshold_low = temp_low

        if temp_high is None:
            self.temp_threshold_high = (
                DEFAULT_TEMP_THRESHOLD_HIGH_F
                if temp_unit == TempUnit.FAHRENHEIT
                else DEFAULT_TEMP_THRESHOLD_HIGH_C
            )
        else:
            self.temp_threshold_high = temp_high

        self.plug = SmartPlug(self.host)
        self.state = self._load_state()
        logger.info(
            f"Initialized VirtualThermostat with: host={host}, zipcode={zipcode}"
        )
        logger.info(f"State file: {state_file}, cooldown: {cooldown_minutes} minutes")
        logger.info(
            f"Temperature thresholds: LOW={self.temp_threshold_low}°{temp_unit}, "
            f"HIGH={self.temp_threshold_high}°{temp_unit}"
        )
        logger.info(f"Using temperature unit: {temp_unit}")

    def _load_state(self):
        """Load the state from the state file."""
        if not self.state_file.exists():
            logger.info(
                f"State file {self.state_file} doesn't exist, creating default state"
            )
            return {
                "last_action_time": None,
                "last_action": None,
                "last_temperature": None,
                "last_temperature_unit": None,
            }

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
                logger.info(f"Loaded state: {state}")

                # If we have a temperature stored with a different unit, convert it
                if (
                    state.get("last_temperature") is not None
                    and state.get("last_temperature_unit") is not None
                    and state["last_temperature_unit"] != self.temp_unit
                ):
                    old_temp = state["last_temperature"]
                    old_unit = state["last_temperature_unit"]
                    new_temp = convert_temperature(old_temp, old_unit, self.temp_unit)
                    logger.info(
                        f"Converting stored temperature from {old_temp}°{old_unit} "
                        f"to {new_temp:.1f}°{self.temp_unit}"
                    )
                    state["last_temperature"] = new_temp
                    state["last_temperature_unit"] = self.temp_unit

                return state
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading state file: {e}")
            return {
                "last_action_time": None,
                "last_action": None,
                "last_temperature": None,
                "last_temperature_unit": None,
            }

    def _save_state(self):
        """Save the state to the state file."""
        try:
            # Make sure we save the temperature unit
            if (
                "last_temperature" in self.state
                and self.state["last_temperature"] is not None
            ):
                self.state["last_temperature_unit"] = self.temp_unit

            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
                logger.info(f"Saved state: {self.state}")
        except IOError as e:
            logger.error(f"Error saving state file: {e}")

    def get_temperature(self):
        """Get current temperature from wttr.in."""
        try:
            # Use metric parameter when Celsius is requested
            metric_param = "m" if self.temp_unit == TempUnit.CELSIUS else ""

            # Request the temperature in the desired unit directly from wttr.in
            url = f"https://wttr.in/{self.zipcode}?format=%f&{metric_param}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # Parse the temperature (response format should match our desired unit)
            temp_str = response.text.strip()
            logger.debug(f"Raw temperature response: {temp_str}")

            # Extract the temperature value with regex
            match = re.search(r"([+-]?\d+(?:\.\d+)?)", temp_str)
            if not match:
                logger.error(f"Unable to parse temperature from: {temp_str}")
                return self.state.get("last_temperature")

            temperature = float(match.group(1))
            logger.info(f"Current temperature: {temperature:.1f}°{self.temp_unit}")
            return temperature
        except (requests.RequestException, ValueError) as e:
            logger.error(f"Error fetching temperature: {e}")
            # Return the last known temperature or None
            return self.state.get("last_temperature")

    async def check_plug_state(self):
        """Check the current state of the smart plug."""
        try:
            await self.plug.update()
            is_on = self.plug.is_on
            logger.info(f"Smart plug is currently {'ON' if is_on else 'OFF'}")
            return is_on
        except Exception as e:
            logger.error(f"Error checking smart plug state: {e}")
            return None

    async def set_plug_state(self, turn_on):
        """Set the state of the smart plug."""
        try:
            if turn_on:
                await self.plug.turn_on()
                logger.info("Turned smart plug ON")
                self.state["last_action"] = "turn_on"
            else:
                await self.plug.turn_off()
                logger.info("Turned smart plug OFF")
                self.state["last_action"] = "turn_off"

            self.state["last_action_time"] = datetime.now().isoformat()
            self._save_state()

        except Exception as e:
            logger.error(f"Error setting smart plug state: {e}")

    def can_change_state(self):
        """Check if enough time has passed since the last state change."""
        if self.state["last_action_time"] is None:
            return True

        try:
            last_action_time = datetime.fromisoformat(self.state["last_action_time"])
            time_since_change = datetime.now() - last_action_time
            cooldown_period = timedelta(minutes=self.cooldown_minutes)

            if time_since_change >= cooldown_period:
                logger.info(
                    f"Cooldown period passed: "
                    f"{time_since_change.total_seconds() / 60:.1f} mins since action"
                )
                return True
            else:
                remaining = cooldown_period - time_since_change
                logger.info(
                    f"In cooldown period. {remaining.total_seconds() / 60:.1f} "
                    f"minutes remaining"
                )
                return False
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing last action time: {e}")
            return True

    async def check_and_adjust(self):
        """Check temperature and adjust the plug state if needed."""
        temperature = self.get_temperature()
        if temperature is None:
            logger.warning("Could not get temperature, skipping adjustment")
            return

        # Save the temperature
        self.state["last_temperature"] = temperature
        self._save_state()

        # If we're in the cooldown period, don't change state
        if not self.can_change_state():
            return

        current_state = await self.check_plug_state()
        if current_state is None:
            logger.warning(
                "Could not determine current plug state, skipping adjustment"
            )
            return

        # Logic for turning AC on/off
        if temperature >= self.temp_threshold_high and not current_state:
            logger.info(
                f"Temperature {temperature:.1f}°{self.temp_unit} >= threshold "
                f"{self.temp_threshold_high}°{self.temp_unit}, turning AC ON"
            )
            await self.set_plug_state(True)
        elif temperature <= self.temp_threshold_low and current_state:
            logger.info(
                f"Temperature {temperature:.1f}°{self.temp_unit} <= threshold "
                f"{self.temp_threshold_low}°{self.temp_unit}, turning AC OFF"
            )
            await self.set_plug_state(False)
        else:
            logger.info(
                f"No action needed. Temperature: {temperature:.1f}°{self.temp_unit}, "
                f"AC is {'ON' if current_state else 'OFF'}"
            )

    async def run_once(self):
        """Run a single check and adjustment cycle."""
        logger.info("Running temperature check and adjustment")
        await self.check_and_adjust()

    async def run_daemon(self, check_interval=DEFAULT_CHECK_INTERVAL):
        """Run continuously as a daemon."""
        logger.info(f"Starting daemon mode, checking every {check_interval} seconds")
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Error in run cycle: {e}")

            # Sleep for the check interval
            logger.info(f"Sleeping for {check_interval} seconds")
            await asyncio.sleep(check_interval)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Virtual Thermostat - Control a smart plug based on temperature."
    )

    parser.add_argument(
        "--host", required=True, help="IP address or hostname of the smart plug"
    )
    parser.add_argument(
        "--zipcode", required=True, help="ZIP code for temperature data"
    )
    parser.add_argument(
        "--state-file",
        default=DEFAULT_STATE_FILE,
        help=f"File to store state between runs (default: {DEFAULT_STATE_FILE})",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=DEFAULT_COOLDOWN_MINUTES,
        help=(
            f"Cooldown period in minutes between state changes "
            f"(default: {DEFAULT_COOLDOWN_MINUTES})"
        ),
    )
    parser.add_argument(
        "--temp-unit",
        type=str,
        choices=["F", "C"],
        default="F",
        help="Temperature unit to use (F=Fahrenheit, C=Celsius, default: F)",
    )
    temp_group = parser.add_argument_group("Temperature thresholds")
    temp_group.add_argument(
        "--temp-low",
        type=float,
        help=(
            f"Temperature threshold to turn off AC "
            f"(default: {DEFAULT_TEMP_THRESHOLD_LOW_F}°F or "
            f"{DEFAULT_TEMP_THRESHOLD_LOW_C}°C, depending on --temp-unit)"
        ),
    )
    temp_group.add_argument(
        "--temp-high",
        type=float,
        help=(
            f"Temperature threshold to turn on AC "
            f"(default: {DEFAULT_TEMP_THRESHOLD_HIGH_F}°F or "
            f"{DEFAULT_TEMP_THRESHOLD_HIGH_C}°C, depending on --temp-unit)"
        ),
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_CHECK_INTERVAL,
        help=(
            f"Check interval in seconds for daemon mode "
            f"(default: {DEFAULT_CHECK_INTERVAL})"
        ),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit instead of running as a daemon",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    return parser.parse_args()


def main():
    """Run the virtual thermostat."""
    args = parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    thermostat = VirtualThermostat(
        host=args.host,
        zipcode=args.zipcode,
        state_file=args.state_file,
        cooldown_minutes=args.cooldown,
        temp_low=args.temp_low,
        temp_high=args.temp_high,
        temp_unit=args.temp_unit,
    )

    try:
        if args.once:
            logger.info("Running in single execution mode")
            asyncio.run(thermostat.run_once())
        else:
            logger.info("Running in daemon mode")
            asyncio.run(thermostat.run_daemon(args.interval))
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
