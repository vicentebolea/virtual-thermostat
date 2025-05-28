#!/usr/bin/env python3
"""
DHT11 Temperature and Humidity Sensor Reader
Reads data from DHT11 sensor and writes temperature to a file for the thermostat.
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import Adafruit_DHT

    HAS_DHT_LIB = True
except ImportError:
    HAS_DHT_LIB = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dht11-reader")

DEFAULT_OUTPUT_FILE = "data/temp_sensor.txt"
DEFAULT_GPIO_PIN = 4
DEFAULT_INTERVAL = 30


def read_dht11(pin, simulate=False):
    """Read temperature and humidity from DHT11 sensor."""
    if simulate or not HAS_DHT_LIB:
        # Simulate sensor reading for testing
        import random

        temperature = round(20 + random.uniform(-5, 10), 1)  # 15-30°C range
        humidity = round(40 + random.uniform(-10, 20), 1)  # 30-60% range
        logger.debug(f"Simulated reading: {temperature}°C, {humidity}%")
        return temperature, humidity

    try:
        # DHT11 sensor type
        sensor = Adafruit_DHT.DHT11

        # Read sensor data
        humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)

        if humidity is not None and temperature is not None:
            return temperature, humidity
        else:
            logger.warning("Failed to get valid reading from DHT11 sensor")
            return None, None

    except Exception as e:
        logger.error(f"Error reading DHT11 sensor: {e}")
        return None, None


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


def continuous_read(pin, output_file, interval, simulate=False):
    """Continuously read sensor and update file at specified interval."""
    mode = "simulation" if simulate or not HAS_DHT_LIB else "hardware"
    logger.info(
        f"Starting continuous DHT11 reading ({mode} mode, GPIO pin {pin}, interval {interval}s)"
    )
    logger.info(f"Writing temperature data to: {output_file}")

    if not HAS_DHT_LIB:
        logger.warning(
            "Adafruit_DHT library not available - running in simulation mode"
        )

    try:
        while True:
            temperature, humidity = read_dht11(pin, simulate or not HAS_DHT_LIB)

            if temperature is not None and humidity is not None:
                if write_temperature(temperature, output_file):
                    log_reading(temperature, humidity, output_file)
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


def single_read(pin, output_file, simulate=False):
    """Read sensor once and write to file."""
    mode = "simulation" if simulate or not HAS_DHT_LIB else "hardware"
    logger.info(f"Reading DHT11 sensor once ({mode} mode, GPIO pin {pin})")

    if not HAS_DHT_LIB:
        logger.warning(
            "Adafruit_DHT library not available - running in simulation mode"
        )

    temperature, humidity = read_dht11(pin, simulate or not HAS_DHT_LIB)

    if temperature is not None and humidity is not None:
        if write_temperature(temperature, output_file):
            log_reading(temperature, humidity, output_file)
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
        help=f"GPIO pin number for DHT11 sensor (default: {DEFAULT_GPIO_PIN})",
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
        success = single_read(args.pin, args.output, args.simulate)
        sys.exit(0 if success else 1)
    else:
        continuous_read(args.pin, args.output, args.interval, args.simulate)


if __name__ == "__main__":
    main()
