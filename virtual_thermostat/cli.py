#!/usr/bin/env python3
"""
Virtual Thermostat - Temperature-Controlled AC Script
Reads temperature from system file and controls AC via smart plug.
Supports web controller interface and cooldown functionality.
"""

import argparse
import asyncio
import json
import logging
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from kasa import SmartPlug

try:
    import paho.mqtt.client as mqtt

    HAS_MQTT_LIB = True
except ImportError:
    HAS_MQTT_LIB = False

logger = logging.getLogger("simple-thermostat")

DEFAULT_CONFIG_FILE = "config/vthermostat_config.json"
DEFAULT_STATE_FILE = "config/vthermostat_state.json"
DEFAULT_TEMP_FILE = "data/temp_sensor.txt"


def create_default_config(config_file, host=None):
    """Create a default configuration file."""
    default_config = {
        "host": host or "192.168.1.100",
        "desired_temperature": 24.0,
        "temp_file": "data/temp_sensor.txt",
        "state_file": "config/vthermostat_state.json",
        "cooldown_minutes": 15,
        "mqtt": {
            "enabled": False,
            "broker": "localhost",
            "port": 1883,
            "topic": "thermostat/temperature",
        },
    }

    config_path = Path(config_file)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2)
        logger.info(f"Created default config file: {config_file}")
        return default_config
    except IOError as e:
        logger.error(f"Error creating config file: {e}")
        sys.exit(1)


def read_config(config_file=DEFAULT_CONFIG_FILE, host=None):
    """Read configuration from file, create default if it doesn't exist."""
    config_path = Path(config_file)
    if not config_path.exists():
        logger.info(f"Config file {config_file} not found, creating default")
        return create_default_config(config_file, host)

    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error reading config: {e}")
        sys.exit(1)


class MQTTTemperatureReader:
    """MQTT temperature reader that subscribes to sensor data."""

    def __init__(self, broker, port, topic, timeout=10):
        """Initialize MQTT temperature reader.

        Args:
            broker: MQTT broker hostname/IP
            port: MQTT broker port
            topic: MQTT topic to subscribe to
            timeout: Timeout in seconds for receiving temperature data
        """
        self.broker = broker
        self.port = port
        self.topic = topic
        self.timeout = timeout
        self.temperature = None
        self.last_update = None
        self.client = None
        self._lock = threading.Lock()

    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client receives a CONNACK response."""
        if rc == 0:
            logger.debug(f"Connected to MQTT broker {self.broker}:{self.port}")
            client.subscribe(self.topic)
            logger.debug(f"Subscribed to topic {self.topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")

    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received."""
        try:
            payload = json.loads(msg.payload.decode())
            temperature = payload.get("temperature")

            if temperature is not None:
                with self._lock:
                    self.temperature = float(temperature)
                    self.last_update = datetime.now()
                    logger.debug(f"Received temperature via MQTT: {temperature}°C")
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Invalid MQTT message format: {e}")

    def get_temperature(self):
        """Get the latest temperature reading from MQTT.

        Returns:
            int: Temperature in Celsius (rounded) or None if no recent data
        """
        if not HAS_MQTT_LIB:
            logger.error("paho-mqtt library not available")
            return None

        try:
            # Create and configure MQTT client
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message

            # Connect to broker
            self.client.connect(self.broker, self.port, 60)

            # Start the loop in a separate thread
            self.client.loop_start()

            # Wait for temperature data with timeout
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                with self._lock:
                    if self.temperature is not None:
                        # Return rounded temperature (as expected by thermostat)
                        temp_celsius = round(self.temperature)
                        self.client.loop_stop()
                        self.client.disconnect()
                        return temp_celsius
                time.sleep(0.1)

            # Timeout reached
            self.client.loop_stop()
            self.client.disconnect()
            logger.error(f"Timeout waiting for MQTT temperature data from {self.topic}")
            return None

        except Exception as e:
            logger.error(f"Error reading temperature via MQTT: {e}")
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
            return None


def read_temperature(temp_file=DEFAULT_TEMP_FILE, mqtt_config=None):
    """Read temperature from MQTT or file source.

    Args:
        temp_file: Path to temperature file (fallback)
        mqtt_config: MQTT configuration dict (if enabled)

    Returns:
        int: Temperature in Celsius or None if error
    """
    # Try MQTT first if enabled
    if mqtt_config and mqtt_config.get("enabled", False):
        if not HAS_MQTT_LIB:
            logger.warning(
                "MQTT enabled but paho-mqtt not available, falling back to file"
            )
        else:
            broker = mqtt_config.get("broker", "localhost")
            port = mqtt_config.get("port", 1883)
            topic = mqtt_config.get("topic", "thermostat/temperature")

            mqtt_reader = MQTTTemperatureReader(broker, port, topic)
            temperature = mqtt_reader.get_temperature()

            if temperature is not None:
                logger.info(f"Temperature from MQTT: {temperature}°C")
                return temperature
            else:
                logger.warning(
                    "Failed to get temperature from MQTT, falling back to file"
                )

    # Fallback to file reading
    try:
        with open(temp_file, "r") as f:
            # System thermal files are in whole units of Celsius
            temp_celsius = int(f.read().strip())
            logger.debug(f"Temperature from file: {temp_celsius}°C")
            return temp_celsius
    except (IOError, ValueError) as e:
        logger.error(f"Error reading temperature from {temp_file}: {e}")
        return None


def load_state(state_file=DEFAULT_STATE_FILE):
    """Load state from file."""
    state_path = Path(state_file)
    if not state_path.exists():
        return {
            "last_ac_state": False,
            "last_run": None,
            "enabled": True,
            "last_ac_change": None,
        }

    try:
        with open(state_path, "r") as f:
            state = json.load(f)
            # Ensure enabled field exists for backward compatibility
            if "enabled" not in state:
                state["enabled"] = True
            # Ensure last_ac_change field exists for backward compatibility
            if "last_ac_change" not in state:
                state["last_ac_change"] = None
            return state
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading state: {e}")
        return {
            "last_ac_state": False,
            "last_run": None,
            "enabled": True,
            "last_ac_change": None,
        }


def save_state(state, state_file=DEFAULT_STATE_FILE):
    """Save state to file."""
    try:
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        logger.error(f"Error saving state: {e}")


def is_within_cooldown(config, state):
    """Check if we're within the cooldown period since last AC state change."""
    cooldown_minutes = config.get("cooldown_minutes", 15)
    last_ac_change = state.get("last_ac_change")

    if not last_ac_change:
        return False

    try:
        last_change_time = datetime.fromisoformat(last_ac_change)
        cooldown_end = last_change_time + timedelta(minutes=cooldown_minutes)
        return datetime.now() < cooldown_end
    except (ValueError, TypeError):
        # If we can't parse the last change time, assume we're not in cooldown
        return False


async def control_ac(host, turn_on):
    """Control the AC via smart plug."""
    try:
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
        logger.error(f"Error controlling AC: {e}")
        return None


async def main(
    config_file=None,
    state_file=None,
    temp_file=None,
    host=None,
    mqtt_broker=None,
    mqtt_port=None,
    mqtt_topic=None,
):
    """Main function."""
    # Use provided arguments or defaults
    config_file = config_file or DEFAULT_CONFIG_FILE
    state_file = state_file or DEFAULT_STATE_FILE
    temp_file = temp_file or DEFAULT_TEMP_FILE

    # Read configuration
    config = read_config(config_file, host)

    required_keys = ["host", "desired_temperature"]
    for key in required_keys:
        if key not in config:
            logger.error(f"Missing required config key: {key}")
            sys.exit(1)

    host = config["host"]
    desired_temperature = config["desired_temperature"]

    # Override config file paths with command line arguments if provided
    temp_file = temp_file or config.get("temp_file", DEFAULT_TEMP_FILE)
    state_file = state_file or config.get("state_file", DEFAULT_STATE_FILE)

    # Read current temperature (MQTT or file)
    mqtt_config = config.get("mqtt", {})

    # Override MQTT config with CLI arguments if provided
    if mqtt_broker is not None:
        mqtt_config = {
            "enabled": True,
            "broker": mqtt_broker,
            "port": mqtt_port or mqtt_config.get("port", 1883),
            "topic": mqtt_topic or mqtt_config.get("topic", "thermostat/temperature"),
        }

    temperature = read_temperature(temp_file, mqtt_config)
    if temperature is None:
        logger.error("Could not read temperature")
        sys.exit(1)

    logger.info(f"Current temperature: {temperature}°C")
    logger.info(f"Desired temperature: {desired_temperature}°C")

    # Load current state
    state = load_state(state_file)
    last_ac_state = state.get("last_ac_state", False)
    enabled = state.get("enabled", True)

    # Check if thermostat is enabled
    if not enabled:
        logger.info("Thermostat is disabled, skipping temperature control")
        # Update state with current run info but don't change AC state
        state["last_run"] = datetime.now().isoformat()
        state["last_temperature"] = temperature
        save_state(state, state_file)
        return

    # Determine if AC should be on or off
    action_needed = False
    desired_state = last_ac_state

    if temperature > desired_temperature and not last_ac_state:
        # Temperature too high, want to turn AC on
        desired_state = True
        action_needed = True
        action_reason = f"Temperature {temperature}°C > {desired_temperature}°C"
    elif temperature <= desired_temperature and last_ac_state:
        # Temperature at or below desired, want to turn AC off
        desired_state = False
        action_needed = True
        action_reason = f"Temperature {temperature}°C <= {desired_temperature}°C"

    if action_needed:
        # Check if we're within cooldown period
        if is_within_cooldown(config, state):
            cooldown_minutes = config.get("cooldown_minutes", 15)
            logger.info(
                f"AC state change desired ({action_reason}) but within {cooldown_minutes}min cooldown period"
            )
            new_ac_state = last_ac_state  # Keep current state
        else:
            # Not in cooldown, proceed with AC control
            action_text = "ON" if desired_state else "OFF"
            logger.info(f"{action_reason}, turning AC {action_text}")
            new_ac_state = await control_ac(host, desired_state)

            # If AC state actually changed, record the change time
            if new_ac_state is not None and new_ac_state != last_ac_state:
                state["last_ac_change"] = datetime.now().isoformat()
    else:
        # No change needed
        logger.info(f"No action needed. AC is {'ON' if last_ac_state else 'OFF'}")
        new_ac_state = last_ac_state

    # Save new state
    if new_ac_state is not None:
        state["last_ac_state"] = new_ac_state
        state["last_run"] = datetime.now().isoformat()
        state["last_temperature"] = temperature
        save_state(state, state_file)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Virtual Thermostat - Temperature-controlled AC script"
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILE,
        help=f"Path to config file (default: {DEFAULT_CONFIG_FILE})",
    )
    parser.add_argument(
        "--state",
        default=DEFAULT_STATE_FILE,
        help=f"Path to state file (default: {DEFAULT_STATE_FILE})",
    )
    parser.add_argument(
        "--temp",
        default=DEFAULT_TEMP_FILE,
        help=f"Path to temperature file (default: {DEFAULT_TEMP_FILE})",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="WARNING",
        help="Set the logging level (default: WARNING)",
    )
    parser.add_argument(
        "--host",
        help="Smart plug host IP address (used when creating default config)",
    )
    parser.add_argument(
        "--mqtt-broker",
        help="MQTT broker host address",
    )
    parser.add_argument(
        "--mqtt-port",
        type=int,
        default=1883,
        help="MQTT broker port (default: 1883)",
    )
    parser.add_argument(
        "--mqtt-topic",
        help="MQTT topic for temperature publishing",
    )
    return parser.parse_args()


def cli_main():
    """Entry point for CLI."""
    args = parse_args()

    # Configure logging with the specified level
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    asyncio.run(
        main(
            config_file=args.config,
            state_file=args.state,
            temp_file=args.temp,
            host=args.host,
            mqtt_broker=args.mqtt_broker,
            mqtt_port=args.mqtt_port,
            mqtt_topic=args.mqtt_topic,
        )
    )


if __name__ == "__main__":
    cli_main()
