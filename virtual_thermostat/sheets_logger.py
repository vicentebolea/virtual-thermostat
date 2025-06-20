#!/usr/bin/env python3
"""
Google Sheets Temperature Logger - MQTT to Google Sheets
Subscribes to MQTT temperature/humidity data and uploads to Google Sheets at configurable intervals.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import click
import paho.mqtt.subscribe as subscribe
import gspread
import requests
from google.oauth2.service_account import Credentials
from kasa import SmartPlug

logger = logging.getLogger("sheets-logger")


class SheetsLogger:
    def __init__(self, config_file):
        self.config_file = config_file
        with open(config_file, "r") as f:
            self.config = json.load(f)

        self.last_upload = None
        self.current_data = {
            "temperature": None,
            "humidity": None,
            "outside_temperature": None,
        }
        self.state_data = {}
        self.current_power = 0
        self.gc = None
        self.worksheet = None

        # Initialize Google Sheets connection
        self._setup_sheets_connection()

    def _setup_sheets_connection(self):
        """Setup Google Sheets API connection."""
        sheets_config = self.config.get("google_sheets", {})

        if not sheets_config or not sheets_config.get("enabled", False):
            raise click.ClickException("Google Sheets is not enabled in configuration")

        credentials_file = sheets_config.get("credentials_file")
        if not credentials_file or not Path(credentials_file).exists():
            raise click.ClickException(
                f"Google Sheets credentials file not found: {credentials_file}"
            )

        try:
            # Setup credentials
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_file(
                credentials_file, scopes=scopes
            )
            self.gc = gspread.authorize(creds)

            # Open the spreadsheet
            spreadsheet_id = sheets_config.get("spreadsheet_id")
            if not spreadsheet_id:
                raise click.ClickException("No spreadsheet_id configured")

            spreadsheet = self.gc.open_by_key(spreadsheet_id)
            worksheet_name = sheets_config.get("worksheet_name", "Temperature_Data")

            try:
                self.worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                # Create worksheet if it doesn't exist
                self.worksheet = spreadsheet.add_worksheet(
                    title=worksheet_name, rows=1000, cols=11
                )
                # Add headers including state file fields and power usage
                headers = [
                    "Timestamp",
                    "Temperature (°C)",
                    "Humidity (%)",
                    "Outside Temp (°C)",
                    "Device",
                    "AC State",
                    "Last Run",
                    "Last AC Change",
                    "Thermostat Enabled",
                    "Desired Temp (°C)",
                    "Power (W)",
                ]
                self.worksheet.update("A1:K1", [headers])
                logger.info(f"Created new worksheet: {worksheet_name}")

            logger.info(
                f"Connected to Google Sheets: {spreadsheet.title} -> {worksheet_name}"
            )

        except Exception as e:
            raise click.ClickException(f"Failed to setup Google Sheets connection: {e}")

    def _mqtt_subscribe(self, fn, *args, **kwargs):
        """Helper to run MQTT subscribe with timeout."""
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

    def _get_data_from_mqtt(self, broker, port, topic):
        """Get temperature and humidity data from MQTT."""
        msg = self._mqtt_subscribe(
            subscribe.simple,
            topic,
            hostname=broker,
            port=port,
            msg_count=1,
            retained=True,
            timeout=15,
        )

        if msg is None:
            return None, None

        try:
            # Try to parse as JSON first (DHT11 format)
            data = json.loads(msg.payload.decode())
            temperature = data.get("temperature")
            humidity = data.get("humidity")
            return float(temperature) if temperature is not None else None, (
                float(humidity) if humidity is not None else None
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            # Fall back to plain number format (temperature only)
            try:
                temperature = float(msg.payload.decode().strip())
                return temperature, None
            except (ValueError, AttributeError):
                return None, None

    def _get_outside_temperature(self):
        """Get outside temperature from wttr.in weather service."""
        try:
            # Use wttr.in with format %t to get just temperature
            response = requests.get("http://wttr.in/?m&format=%t", timeout=5)
            response.raise_for_status()

            # Parse the response (format: "+15°C" or "-5°C")
            temp_str = response.text.strip()
            if temp_str.endswith("°C"):
                temp_value = temp_str[:-2]  # Remove '°C'
                # Remove leading '+' if present
                if temp_value.startswith("+"):
                    temp_value = temp_value[1:]
                temperature = float(temp_value)
                logger.debug(f"Outside temperature from wttr.in: {temperature}°C")
                return temperature
            else:
                logger.warning(f"Unexpected format from wttr.in: {temp_str}")
                return None

        except requests.RequestException as e:
            logger.warning(f"Failed to get outside temperature from wttr.in: {e}")
            return None
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse outside temperature: {e}")
            return None

    def _read_sensor_data(self):
        """Read temperature and humidity from MQTT source."""
        mqtt_config = self.config.get("mqtt", {})

        if not mqtt_config or not mqtt_config.get("enabled", False):
            raise click.ClickException("MQTT is not enabled in configuration")

        broker = mqtt_config.get("broker", "localhost")
        port = mqtt_config.get("port", 1883)
        topic = mqtt_config.get("topic", "thermostat/temperature")

        try:
            temperature, humidity = self._get_data_from_mqtt(broker, port, topic)
            if temperature is not None:
                logger.debug(
                    f"Data from MQTT - Temperature: {temperature}°C, Humidity: {humidity}%"
                )
                self.current_data["temperature"] = temperature
                self.current_data["humidity"] = humidity

                # Get outside temperature
                outside_temp = self._get_outside_temperature()
                self.current_data["outside_temperature"] = outside_temp

                return True
            return False
        except Exception as e:
            logger.error(f"Failed to get data from MQTT: {e}")
            return False

    def _read_state_data(self):
        """Read current state from state file."""
        state_file = self.config.get("state_file", "config/vthermostat_state.json")
        state_path = Path(state_file)

        try:
            if state_path.exists():
                with open(state_path, "r") as f:
                    state_data = json.load(f)
                    self.state_data = {
                        "last_ac_state": state_data.get("last_ac_state", False),
                        "last_run": state_data.get("last_run", "Never"),
                        "last_ac_change": state_data.get("last_ac_change", "Never"),
                        "last_temperature": state_data.get("last_temperature", None),
                    }
                    logger.debug(f"Read state data: {self.state_data}")
                    return True
            else:
                logger.warning(f"State file not found: {state_file}")
                self.state_data = {
                    "last_ac_state": False,
                    "last_run": "Never",
                    "last_ac_change": "Never",
                    "last_temperature": None,
                }
                return False
        except Exception as e:
            logger.error(f"Failed to read state file: {e}")
            self.state_data = {
                "last_ac_state": False,
                "last_run": "Never",
                "last_ac_change": "Never",
                "last_temperature": None,
            }
            return False

    async def _read_current_power(self):
        """Read power consumption data directly from smart plug."""
        host = self.config.get("host")
        if not host:
            logger.warning("No smart plug host configured")
            self.current_power = 0
            return False

        try:
            plug = SmartPlug(host)
            await plug.update()

            # Check AC state and record appropriate power consumption
            if not plug.is_on:
                logger.debug("AC is off, recording 0W power consumption")
                return True

            if plug.has_emeter:
                emeter_data = plug.emeter_realtime
                self.current_power = emeter_data.get("power", 0)
                logger.debug(f"Power consumption: {self.current_power:.1f}W")
                return True
            else:
                logger.debug("Smart plug does not support power monitoring")
                return False
        except Exception as e:
            logger.error(f"Failed to get power data from smart plug: {e}")
            return False

    def _should_upload(self, interval_minutes):
        """Check if it's time to upload data."""
        if self.last_upload is None:
            return True

        next_upload = self.last_upload + timedelta(minutes=interval_minutes)
        return datetime.now() >= next_upload

    def _upload_to_sheets(self):
        """Upload current data to Google Sheets."""
        if not self.worksheet:
            logger.error("Google Sheets worksheet not available")
            return False

        try:
            timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            temperature = self.current_data.get("temperature", "")
            humidity = self.current_data.get("humidity", "")
            outside_temperature = self.current_data.get("outside_temperature", "")
            device = self.config.get("device_name", "virtual-thermostat")

            # State data
            ac_state = "ON" if self.state_data.get("last_ac_state", False) else "OFF"
            last_run = self.state_data.get("last_run", "Never")
            last_ac_change = self.state_data.get("last_ac_change", "Never")
            thermostat_enabled = "YES" if self.config.get("enabled", True) else "NO"
            desired_temp = self.config.get("desired_temperature", "")

            # Format timestamps for better readability
            if last_run and last_run != "Never":
                try:
                    last_run_dt = datetime.fromisoformat(
                        last_run.replace("Z", "+00:00")
                    )
                    last_run = last_run_dt.strftime("%Y/%m/%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass  # Keep original format if parsing fails

            if last_ac_change and last_ac_change != "Never":
                try:
                    last_ac_change_dt = datetime.fromisoformat(
                        last_ac_change.replace("Z", "+00:00")
                    )
                    last_ac_change = last_ac_change_dt.strftime("%Y/%m/%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass  # Keep original format if parsing fails

            # Append row to the worksheet with all data including power usage
            row_data = [
                timestamp,
                temperature,
                humidity,
                outside_temperature,
                device,
                ac_state,
                last_run,
                last_ac_change,
                thermostat_enabled,
                desired_temp,
                self.current_power,
            ]
            self.worksheet.append_row(row_data)

            logger.info(
                f"Uploaded to Google Sheets: {timestamp}, {temperature}°C, {humidity}%, Outside: {outside_temperature}°C, AC: {ac_state}, Enabled: {thermostat_enabled}{self.current_power}"
            )
            self.last_upload = datetime.now()
            return True

        except Exception as e:
            logger.error(f"Failed to upload to Google Sheets: {e}")
            return False

    async def run_once(self):
        """Single execution cycle - read data and upload if needed."""
        with open(self.config_file, "r") as f:
            self.config = json.load(f)

        sheets_config = self.config.get("google_sheets", {})
        if not sheets_config.get("enabled", False):
            logger.info("Google Sheets logging is disabled in configuration")
            return

        interval_minutes = sheets_config.get("upload_interval_minutes", 15)

        # Read sensor data, state data, and power data
        sensor_data_available = self._read_sensor_data()
        state_data_available = self._read_state_data()
        await self._read_current_power()

        if not sensor_data_available or not state_data_available:
            logger.warning("No sensor or state data available, skipping upload")
            return

        # Check if it's time to upload
        if self._should_upload(interval_minutes):
            logger.info(f"Uploading data (interval: {interval_minutes} minutes)")
            self._upload_to_sheets()
        else:
            next_upload = self.last_upload + timedelta(minutes=interval_minutes)
            logger.debug(
                f"Next upload scheduled for: {next_upload.strftime('%H:%M:%S')}"
            )

    async def run_daemon(self, check_interval):
        """Run logger continuously as a daemon."""
        sheets_config = self.config.get("google_sheets", {})
        upload_interval = sheets_config.get("upload_interval_minutes", 15)

        logger.info("Starting Google Sheets logger daemon")
        logger.info(f"Upload interval: {upload_interval} minutes")
        logger.info(f"Check interval: {check_interval} seconds")
        logger.info(
            f"MQTT broker: {self.config.get('mqtt', {}).get('broker', 'localhost')}"
        )

        try:
            while True:
                try:
                    await self.run_once()
                except Exception as e:
                    logger.error(f"Error in logger cycle: {e}")

                await asyncio.sleep(check_interval)
        except KeyboardInterrupt:
            logger.info("Stopping Google Sheets logger daemon (Ctrl+C pressed)")


@click.command()
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config file"
)
@click.option("--daemon", is_flag=True, help="Run as daemon (continuous mode)")
@click.option(
    "--check-interval",
    default=30,
    help="Interval in seconds for checking/reading data in daemon mode (default: 30)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Set the logging level",
)
def cli_main(config, daemon, check_interval, log_level):
    """Google Sheets Temperature Logger - MQTT to Google Sheets uploader"""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if check_interval < 1:
        raise click.ClickException("Check interval must be at least 1 second")

    logger = SheetsLogger(config)

    if daemon:
        asyncio.run(logger.run_daemon(check_interval))
    else:
        asyncio.run(logger.run_once())


if __name__ == "__main__":
    cli_main()
