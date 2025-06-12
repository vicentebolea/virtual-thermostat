#!/usr/bin/env python3
"""
DHT11 Temperature and Humidity Sensor Reader
Reads data from DHT11 sensor and writes temperature to a file for the thermostat.
Supports MQTT publishing and both hardware and simulation modes.
"""

import json
import logging
import time
from datetime import datetime

import click
import paho.mqtt.publish as publish

try:
    import Adafruit_DHT
except ImportError:
    Adafruit_DHT = None

logger = logging.getLogger("dht11-reader")


class DHT11Sensor:
    """DHT11 temperature and humidity sensor reader with MQTT support."""

    def __init__(
        self,
        pin=4,
        mqtt_broker=None,
        mqtt_port=1883,
        mqtt_topic="thermostat/temperature",
    ):
        self.pin = pin
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic = mqtt_topic

    def read_sensor(self, simulate=False):
        """Read temperature and humidity from DHT11 sensor."""
        if simulate or not Adafruit_DHT:
            import random

            temperature = round(20 + random.uniform(-5, 10), 1)
            humidity = round(40 + random.uniform(-10, 20), 1)
            logger.debug(f"Simulated reading: {temperature}°C, {humidity}%")
            return temperature, humidity

        try:
            humidity, temperature = Adafruit_DHT.read_retry(
                Adafruit_DHT.DHT11, self.pin
            )
            if humidity is not None and temperature is not None:
                return temperature, humidity
            return None, None
        except Exception as e:
            logger.warning(f"DHT11 sensor reading error: {e}")
            return None, None

    def publish_mqtt(self, temperature, humidity):
        """Publish temperature and humidity data to MQTT broker."""
        if not self.mqtt_broker:
            return True

        try:
            data = {
                "temperature": temperature,
                "humidity": round(humidity, 1),
                "timestamp": datetime.now().isoformat(),
            }

            publish.single(
                self.mqtt_topic,
                json.dumps(data),
                hostname=self.mqtt_broker,
                port=self.mqtt_port,
                retain=True,
            )

            logger.debug(
                f"Published to MQTT topic '{self.mqtt_topic}': {json.dumps(data)}"
            )
            return True
        except Exception as e:
            logger.error(f"Error publishing to MQTT: {e}")
            return False

    def log_reading(self, temperature, humidity):
        """Log the sensor reading with timestamp."""
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        logger.info(
            f"[{timestamp}] Temperature: {temperature:.1f}°C, Humidity: {humidity:.1f}%"
        )

    def run_continuous(self, interval, simulate=False):
        """Continuously read sensor and publish to MQTT at specified interval."""
        if not self.mqtt_broker:
            raise click.ClickException("MQTT broker is required")

        mode = "simulation" if simulate or not Adafruit_DHT else "hardware"
        logger.info(
            f"Starting continuous DHT11 reading ({mode} mode, GPIO pin {self.pin}, interval {interval}s)"
        )
        logger.info(f"Publishing to MQTT broker: {self.mqtt_broker}")

        if not Adafruit_DHT:
            logger.warning(
                "Adafruit_DHT library not available - running in simulation mode"
            )

        try:
            while True:
                temperature, humidity = self.read_sensor(simulate or not Adafruit_DHT)

                if temperature is not None and humidity is not None:
                    self.log_reading(temperature, humidity)
                    self.publish_mqtt(temperature, humidity)
                else:
                    logger.warning("Skipping publish due to invalid sensor reading")

                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Stopping DHT11 reader (Ctrl+C pressed)")

    def run_once(self, simulate=False):
        """Read sensor once and publish to MQTT."""
        if not self.mqtt_broker:
            raise click.ClickException("MQTT broker is required")

        mode = "simulation" if simulate or not Adafruit_DHT else "hardware"
        logger.info(f"Reading DHT11 sensor once ({mode} mode, GPIO pin {self.pin})")

        if not Adafruit_DHT:
            logger.warning(
                "Adafruit_DHT library not available - running in simulation mode"
            )

        temperature, humidity = self.read_sensor(simulate or not Adafruit_DHT)

        if temperature is not None and humidity is not None:
            self.log_reading(temperature, humidity)
            self.publish_mqtt(temperature, humidity)
            return True
        else:
            raise click.ClickException("Failed to read valid data from DHT11 sensor")


@click.command()
@click.option("--pin", default=4, help="GPIO pin number for DHT11 sensor")
@click.option(
    "--interval", default=30, help="Reading interval in seconds for continuous mode"
)
@click.option("--once", is_flag=True, help="Read sensor once and exit")
@click.option("--simulate", is_flag=True, help="Simulate sensor readings")
@click.option("--mqtt-broker", required=True, help="MQTT broker hostname or IP address")
@click.option("--mqtt-port", default=1883, help="MQTT broker port")
@click.option(
    "--mqtt-topic",
    default="thermostat/temperature",
    help="MQTT topic for publishing sensor data",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Set the logging level",
)
def main(pin, interval, once, simulate, mqtt_broker, mqtt_port, mqtt_topic, log_level):
    """DHT11 Temperature and Humidity Sensor Reader - MQTT Only"""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if interval < 1:
        raise click.ClickException("Interval must be at least 1 second")

    if pin < 0:
        raise click.ClickException("GPIO pin must be a positive number")

    # Create sensor instance
    sensor = DHT11Sensor(pin, mqtt_broker, mqtt_port, mqtt_topic)

    if once:
        sensor.run_once(simulate)
    else:
        sensor.run_continuous(interval, simulate)


if __name__ == "__main__":
    main()
