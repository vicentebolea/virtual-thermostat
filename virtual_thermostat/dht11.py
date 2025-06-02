#!/usr/bin/env python3
"""
DHT11 Temperature and Humidity Sensor Reader
Reads data from DHT11 sensor and writes temperature to a file for the thermostat.
Supports MQTT publishing and both hardware and simulation modes.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import board
    import adafruit_dht

    HAS_DHT_LIB = True
except ImportError:
    HAS_DHT_LIB = False

try:
    import paho.mqtt.client as mqtt

    HAS_MQTT_LIB = True
except ImportError:
    HAS_MQTT_LIB = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dht11-reader")

DEFAULT_OUTPUT_FILE = "data/temp_sensor.txt"
DEFAULT_GPIO_PIN = 4
DEFAULT_INTERVAL = 30


class DHT11Reader:
    """DHT11 temperature and humidity sensor reader with MQTT support."""

    def __init__(
        self,
        pin=4,
        mqtt_broker=None,
        mqtt_port=1883,
        mqtt_topic="thermostat/temperature",
    ):
        """Initialize DHT11 reader.

        Args:
            pin: GPIO pin number for DHT11 sensor
            mqtt_broker: MQTT broker hostname/IP (enables MQTT if provided)
            mqtt_port: MQTT broker port
            mqtt_topic: MQTT topic for publishing data
        """
        self.pin = pin
        self.mqtt_enabled = mqtt_broker is not None
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic = mqtt_topic
        self.sensor = None

        # Initialize sensor if hardware is available
        if HAS_DHT_LIB:
            self._init_sensor()

    def _init_sensor(self):
        """Initialize the DHT11 sensor hardware."""
        if not HAS_DHT_LIB:
            return

        try:
            self.sensor = adafruit_dht.DHT11(getattr(board, f"D{self.pin}"))
            logger.debug(f"Initialized DHT11 sensor on GPIO pin {self.pin}")

        except Exception as e:
            logger.debug(
                f"Failed to initialize DHT11 sensor (expected on non-Pi platforms): {e}"
            )
            self.sensor = None

    def read_sensor(self, simulate=False):
        """Read temperature and humidity from DHT11 sensor.

        Args:
            simulate: Use simulated readings instead of hardware

        Returns:
            tuple: (temperature, humidity) or (None, None) if error
        """
        if simulate or not HAS_DHT_LIB or not self.sensor:
            # Simulate sensor reading for testing
            import random

            temperature = round(20 + random.uniform(-5, 10), 1)  # 15-30°C range
            humidity = round(40 + random.uniform(-10, 20), 1)  # 30-60% range
            logger.debug(f"Simulated reading: {temperature}°C, {humidity}%")
            return temperature, humidity

        try:
            # Read sensor data
            temperature = self.sensor.temperature
            humidity = self.sensor.humidity

            if humidity is not None and temperature is not None:
                return temperature, humidity
            else:
                logger.warning("Failed to get valid reading from DHT11 sensor")
                return None, None

        except RuntimeError as e:
            # DHT sensors can be finicky, RuntimeError is common
            logger.warning(f"DHT11 sensor reading error: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Error reading DHT11 sensor: {e}")
            return None, None

    def publish_mqtt(self, temperature, humidity):
        """Publish temperature and humidity data to MQTT broker.

        Args:
            temperature: Temperature reading in Celsius
            humidity: Humidity reading in percent

        Returns:
            bool: True if successful or MQTT disabled, False on error
        """
        if not self.mqtt_enabled:
            return True  # Not an error, just disabled

        if not HAS_MQTT_LIB:
            logger.warning("paho-mqtt library not available - skipping MQTT publish")
            return False

        try:
            client = mqtt.Client()

            # Connect to broker
            client.connect(self.mqtt_broker, self.mqtt_port, 60)

            # Prepare data
            data = {
                "temperature": round(temperature, 1),
                "humidity": round(humidity, 1),
                "timestamp": datetime.now().isoformat(),
            }

            # Publish to topic
            payload = json.dumps(data)
            result = client.publish(self.mqtt_topic, payload)

            if result.rc == 0:
                logger.debug(f"Published to MQTT topic '{self.mqtt_topic}': {payload}")
                return True
            else:
                logger.error(f"Failed to publish to MQTT: {result.rc}")
                return False

        except Exception as e:
            logger.error(f"Error publishing to MQTT: {e}")
            return False
        finally:
            try:
                client.disconnect()
            except Exception:
                pass


def write_temperature(temperature, output_file):
    """Write temperature to file in the format expected by the thermostat."""
    try:
        # Round to nearest integer (as expected by thermostat)
        temp_int = round(temperature)

        # Write to file
        with open(output_file, "w") as f:
            f.write(str(temp_int))

        logger.debug(f"Wrote temperature {temp_int}°C to {output_file}")
        return True

    except IOError as e:
        logger.error(f"Error writing to file {output_file}: {e}")
        return False


def log_reading(temperature, humidity, output_file):
    """Log the sensor reading with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        f"[{timestamp}] Temperature: {temperature:.1f}°C, Humidity: {humidity:.1f}%, "
        f"Written to: {output_file}"
    )


def continuous_read(
    pin,
    output_file,
    interval,
    simulate=False,
    mqtt_broker=None,
    mqtt_port=1883,
    mqtt_topic="thermostat/temperature",
):
    """Continuously read sensor and update file at specified interval."""
    mode = "simulation" if simulate or not HAS_DHT_LIB else "hardware"
    logger.info(
        f"Starting continuous DHT11 reading ({mode} mode, GPIO pin {pin}, interval {interval}s)"
    )
    logger.info(f"Writing temperature data to: {output_file}")

    # Create DHT11 reader instance
    reader = DHT11Reader(pin, mqtt_broker, mqtt_port, mqtt_topic)

    if not HAS_DHT_LIB:
        logger.warning(
            "adafruit-circuitpython-dht library not available - running in simulation mode"
        )

    try:
        while True:
            temperature, humidity = reader.read_sensor(simulate or not HAS_DHT_LIB)

            if temperature is not None and humidity is not None:
                # Write to file
                if write_temperature(temperature, output_file):
                    log_reading(temperature, humidity, output_file)

                    # Publish to MQTT if configured
                    reader.publish_mqtt(temperature, humidity)
                else:
                    logger.error("Failed to write temperature to file")
            else:
                logger.warning("Skipping write due to invalid sensor reading")

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("Stopping DHT11 reader (Ctrl+C pressed)")
    except Exception as e:
        logger.error(f"Unexpected error in continuous reading: {e}")
        sys.exit(1)


def single_read(
    pin,
    output_file,
    simulate=False,
    mqtt_broker=None,
    mqtt_port=1883,
    mqtt_topic="thermostat/temperature",
):
    """Read sensor once and write to file."""
    mode = "simulation" if simulate or not HAS_DHT_LIB else "hardware"
    logger.info(f"Reading DHT11 sensor once ({mode} mode, GPIO pin {pin})")

    # Create DHT11 reader instance
    reader = DHT11Reader(pin, mqtt_broker, mqtt_port, mqtt_topic)

    if not HAS_DHT_LIB:
        logger.warning(
            "adafruit-circuitpython-dht library not available - running in simulation mode"
        )

    temperature, humidity = reader.read_sensor(simulate or not HAS_DHT_LIB)

    if temperature is not None and humidity is not None:
        if write_temperature(temperature, output_file):
            log_reading(temperature, humidity, output_file)

            # Publish to MQTT if configured
            reader.publish_mqtt(temperature, humidity)

            return True
        else:
            logger.error("Failed to write temperature to file")
            return False
    else:
        logger.error("Failed to read valid data from DHT11 sensor")
        return False


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="DHT11 Temperature and Humidity Sensor Reader"
    )
    parser.add_argument(
        "--pin",
        type=int,
        default=DEFAULT_GPIO_PIN,
        help=f"GPIO pin number for DHT11 sensor (default: {DEFAULT_GPIO_PIN}). Supported pins: 4, 17, 18, 22, 23, 24, 25, 27",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output file for temperature data (default: {DEFAULT_OUTPUT_FILE})",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Reading interval in seconds for continuous mode (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Read sensor once and exit (default: continuous reading)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Simulate sensor readings (for testing without hardware)",
    )
    parser.add_argument(
        "--mqtt-broker",
        help="MQTT broker hostname or IP address",
    )
    parser.add_argument(
        "--mqtt-port",
        type=int,
        default=1883,
        help="MQTT broker port (default: 1883)",
    )
    parser.add_argument(
        "--mqtt-topic",
        default="thermostat/temperature",
        help="MQTT topic for publishing sensor data (default: thermostat/temperature)",
    )
    return parser.parse_args()


def main():
    """Main function."""
    args = parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate arguments
    if args.interval < 1:
        logger.error("Interval must be at least 1 second")
        sys.exit(1)

    if args.pin < 0:
        logger.error("GPIO pin must be a positive number")
        sys.exit(1)

    # Create output directory if it doesn't exist
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if we can write to the output file
    try:
        with open(args.output, "w") as f:
            f.write("0")  # Test write
        logger.debug(f"Output file {args.output} is writable")
    except IOError as e:
        logger.error(f"Cannot write to output file {args.output}: {e}")
        sys.exit(1)

    # Run sensor reading
    if args.once:
        success = single_read(
            args.pin,
            args.output,
            args.simulate,
            args.mqtt_broker,
            args.mqtt_port,
            args.mqtt_topic,
        )
        sys.exit(0 if success else 1)
    else:
        continuous_read(
            args.pin,
            args.output,
            args.interval,
            args.simulate,
            args.mqtt_broker,
            args.mqtt_port,
            args.mqtt_topic,
        )


if __name__ == "__main__":
    main()
