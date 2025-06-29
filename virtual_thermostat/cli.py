#!/usr/bin/env python3
"""
Virtual Thermostat - Temperature-Controlled AC Script
Reads temperature from system file and controls AC via smart plug.
Supports web controller interface and cooldown functionality.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import click
import paho.mqtt.subscribe as subscribe
from kasa import SmartPlug

logger = logging.getLogger("simple-thermostat")


class VirtualThermostat:
    def __init__(self, config_file):
        self.config_file = config_file
        with open(config_file, "r") as f:
            self.config = json.load(f)
        self.state = self._load_state()

    def _mqtt_subscribe(self, fn, *args, **kwargs):
        timeout = 1
        if "timeout" in kwargs:
            timeout = kwargs["timeout"]
            del kwargs["timeout"]

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except FutureTimeoutError:
                raise TimeoutError(f"Function timed out after {timeout} seconds")

    def _get_temperature_from_mqtt(self, broker, port, topic):
        msg = self._mqtt_subscribe(
            subscribe.simple,
            topic,
            hostname=broker,
            port=port,
            msg_count=1,
            retained=True,
            timeout=1,
        )

        if msg is None:
            return None

        try:
            # Try to parse as JSON first (DHT11 format)
            import json

            data = json.loads(msg.payload.decode())
            return float(data.get("temperature"))
        except (json.JSONDecodeError, KeyError, TypeError):
            # Fall back to plain number format
            try:
                return float(msg.payload.decode().strip())
            except (ValueError, AttributeError):
                return None

    def _read_temperature(self):
        """Read temperature from MQTT source."""
        mqtt_config = self.config.get("mqtt", {})

        if not mqtt_config or not mqtt_config.get("enabled", False):
            raise click.ClickException("MQTT is not enabled in configuration")

        broker = mqtt_config.get("broker", "localhost")
        port = mqtt_config.get("port", 1883)
        topic = mqtt_config.get("topic", "thermostat/temperature")

        try:
            temperature = self._get_temperature_from_mqtt(broker, port, topic)
            if temperature is not None:
                logger.info(f"Temperature from MQTT: {temperature}°C")
                return int(temperature)
            return None
        except Exception as e:
            logger.error(f"Failed to get temperature from MQTT: {e}")
            return None

    def _load_state(self):
        """Load state from file."""
        state_file = self.config["state_file"]
        state_path = Path(state_file)
        try:
            with open(state_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"last_ac_state": False, "last_run": None, "last_ac_change": None}

    def _save_state(self):
        """Save state to file."""
        state_file = self.config["state_file"]
        with open(state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def _is_within_cooldown(self):
        """Check if we're within the cooldown period since last AC state change."""
        cooldown_minutes = self.config.get("cooldown_minutes", 15)
        last_ac_change = self.state.get("last_ac_change")

        if not last_ac_change:
            return False

        try:
            last_change_time = datetime.fromisoformat(last_ac_change)
            cooldown_end = last_change_time + timedelta(minutes=cooldown_minutes)
            return datetime.now() < cooldown_end
        except (ValueError, TypeError):
            return False

    async def _control_ac(self, turn_on):
        """Control the AC via smart plug."""
        host = self.config["host"]
        kasa_username = self.config.get("kasa_username")
        kasa_password = self.config.get("kasa_password")
        try:
            if kasa_username and kasa_password:
                from kasa import Discover

                plug = await Discover.discover_single(
                    host, username=kasa_username, password=kasa_password
                )
            else:
                plug = SmartPlug(host)
            await plug.update()

            current_state = plug.is_on
            if current_state == turn_on:
                logger.info(f"AC already {'ON' if turn_on else 'OFF'}")
                return current_state

            if turn_on:
                await plug.turn_on()
                logger.info("Turned AC ON")
            else:
                await plug.turn_off()
                logger.info("Turned AC OFF")

            return turn_on
        except Exception as e:
            if "authentication" in str(e).lower() or "login" in str(e).lower():
                logger.error(
                    f"Kasa authentication failed - check username/password: {e}"
                )
            else:
                logger.error(f"Error controlling AC: {e}")
            return None

    async def run_once(self):
        """Main thermostat control logic."""
        with open(self.config_file, "r") as f:
            self.config = json.load(f)

        # Check if thermostat is enabled in config
        if not self.config.get("enabled", True):
            logger.info("Thermostat is disabled in configuration")
            return

        desired_temperature = self.config["desired_temperature"]
        last_ac_state = self.state.get("last_ac_state", False)

        # Check current actual AC state from smart plug
        try:
            host = self.config["host"]
            kasa_username = self.config.get("kasa_username")
            kasa_password = self.config.get("kasa_password")
            if kasa_username and kasa_password:
                from kasa import Discover

                plug = await Discover.discover_single(
                    host, username=kasa_username, password=kasa_password
                )
            else:
                plug = SmartPlug(host)
            await plug.update()
            current_ac_state = plug.is_on

            # Update our state if it differs from reality
            if current_ac_state != last_ac_state:
                logger.info(
                    f"AC state mismatch detected. Expected: {last_ac_state}, Actual: {current_ac_state}"
                )
                self.state["last_ac_state"] = current_ac_state
                last_ac_state = current_ac_state

        except Exception as e:
            if "authentication" in str(e).lower() or "login" in str(e).lower():
                logger.error(
                    f"Kasa authentication failed - check username/password: {e}"
                )
                raise click.ClickException(f"Authentication failed: {e}")
            else:
                logger.warning(f"Could not check current AC state: {e}")
            # Continue with stored state if we can't check actual state

        temperature = self._read_temperature()
        if temperature is None:
            temperature = self.state.get("last_temperature")
            if temperature is None:
                raise click.ClickException("No temperature available")
            logger.info(f"Using last known temperature: {temperature}°C")
        else:
            logger.info(f"Current temperature: {temperature}°C")
            self.state["last_temperature"] = temperature

        logger.info(f"Desired temperature: {desired_temperature}°C")

        # Determine AC action
        desired_state = last_ac_state
        if temperature > desired_temperature and not last_ac_state:
            desired_state = True
        elif temperature <= desired_temperature and last_ac_state:
            desired_state = False

        # Control AC if state should change
        if desired_state != last_ac_state:
            if self._is_within_cooldown():
                cooldown_minutes = self.config.get("cooldown_minutes", 15)
                logger.info(
                    f"AC state change desired but within {cooldown_minutes}min cooldown"
                )
            else:
                action_text = "ON" if desired_state else "OFF"
                logger.info(f"Temperature {temperature}°C, turning AC {action_text}")
                new_ac_state = await self._control_ac(desired_state)
                if new_ac_state is not None and new_ac_state != last_ac_state:
                    self.state["last_ac_state"] = new_ac_state
                    self.state["last_ac_change"] = datetime.now().isoformat()
        else:
            logger.info(f"No action needed. AC is {'ON' if last_ac_state else 'OFF'}")

        # Save state
        self.state["last_run"] = datetime.now().isoformat()
        self._save_state()

    async def run_daemon(self, interval):
        """Run thermostat continuously as a daemon."""
        logger.info(f"Starting thermostat daemon (interval: {interval}s)")
        logger.info(
            f"MQTT broker: {self.config.get('mqtt', {}).get('broker', 'localhost')}"
        )

        try:
            while True:
                try:
                    await self.run_once()
                except Exception as e:
                    logger.error(f"Error in thermostat cycle: {e}")

                await asyncio.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Stopping thermostat daemon (Ctrl+C pressed)")


@click.command()
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config file"
)
@click.option("--daemon", is_flag=True, help="Run as daemon (continuous mode)")
@click.option(
    "--interval", default=60, help="Interval in seconds for daemon mode (default: 60)"
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="WARNING",
    help="Set the logging level",
)
def cli_main(config, daemon, interval, log_level):
    """Virtual Thermostat - Temperature-controlled AC script"""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if interval < 1:
        raise click.ClickException("Interval must be at least 1 second")

    thermostat = VirtualThermostat(config)

    if daemon:
        asyncio.run(thermostat.run_daemon(interval))
    else:
        asyncio.run(thermostat.run_once())


if __name__ == "__main__":
    cli_main()
