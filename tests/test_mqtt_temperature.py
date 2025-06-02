import json
import tempfile
import os
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import unittest.mock

# Mock Adafruit_DHT to disable hardware dependency in tests
with unittest.mock.patch.dict(
    "sys.modules", {"Adafruit_DHT": unittest.mock.MagicMock()}
):
    from virtual_thermostat.cli import VirtualThermostat


def test_virtual_thermostat_init():
    """Test VirtualThermostat initialization."""
    config_data = {
        "host": "192.168.1.100",
        "desired_temperature": 24.0,
        "state_file": "/tmp/test_state.json",
        "cooldown_minutes": 15,
        "mqtt": {
            "enabled": True,
            "broker": "localhost",
            "port": 1883,
            "topic": "thermostat/temperature",
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as config_file:
        json.dump(config_data, config_file)
        config_file_path = config_file.name

    try:
        thermostat = VirtualThermostat(config_file_path)
        assert thermostat.config["host"] == "192.168.1.100"
        assert thermostat.config["desired_temperature"] == 24.0
        assert thermostat.config["mqtt"]["enabled"] == True
        assert thermostat.state["last_ac_state"] == False
    finally:
        os.unlink(config_file_path)


def test_read_temperature_mqtt_disabled():
    """Test that MQTT disabled raises exception."""
    config_data = {
        "host": "192.168.1.100",
        "desired_temperature": 24.0,
        "state_file": "/tmp/test_state.json",
        "mqtt": {"enabled": False},
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as config_file:
        json.dump(config_data, config_file)
        config_file_path = config_file.name

    try:
        thermostat = VirtualThermostat(config_file_path)
        with pytest.raises(Exception):  # Should raise ClickException
            thermostat._read_temperature()
    finally:
        os.unlink(config_file_path)


def test_read_temperature_mqtt_failure():
    """Test that MQTT connection failure returns None."""
    config_data = {
        "host": "192.168.1.100",
        "desired_temperature": 24.0,
        "state_file": "/tmp/test_state.json",
        "mqtt": {
            "enabled": True,
            "broker": "nonexistent.broker",
            "port": 1883,
            "topic": "thermostat/temperature",
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as config_file:
        json.dump(config_data, config_file)
        config_file_path = config_file.name

    try:
        thermostat = VirtualThermostat(config_file_path)
        temperature = thermostat._read_temperature()
        assert temperature is None
    finally:
        os.unlink(config_file_path)


@patch("virtual_thermostat.cli.subscribe")
def test_read_temperature_mqtt_success(mock_subscribe):
    """Test successful MQTT temperature reading."""
    # Mock successful MQTT message
    mock_msg = MagicMock()
    mock_msg.payload.decode.return_value = "25"
    mock_subscribe.simple.return_value = mock_msg

    config_data = {
        "host": "192.168.1.100",
        "desired_temperature": 24.0,
        "state_file": "/tmp/test_state.json",
        "mqtt": {
            "enabled": True,
            "broker": "localhost",
            "port": 1883,
            "topic": "thermostat/temperature",
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as config_file:
        json.dump(config_data, config_file)
        config_file_path = config_file.name

    try:
        thermostat = VirtualThermostat(config_file_path)
        with patch.object(thermostat, "_get_temperature_from_mqtt", return_value=25):
            temperature = thermostat._read_temperature()
            assert temperature == 25
    finally:
        os.unlink(config_file_path)


def test_thermostat_run_with_mock():
    """Test full thermostat run with mocked AC control."""
    import asyncio

    config_data = {
        "host": "192.168.1.100",
        "desired_temperature": 22.0,  # Low temp to trigger AC
        "state_file": "/tmp/test_state.json",
        "cooldown_minutes": 0,  # No cooldown for testing
        "mqtt": {
            "enabled": True,
            "broker": "localhost",
            "port": 1883,
            "topic": "thermostat/temperature",
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as config_file:
        json.dump(config_data, config_file)
        config_file_path = config_file.name

    try:
        thermostat = VirtualThermostat(config_file_path)

        # Mock both temperature reading and AC control
        with patch.object(
            thermostat, "_read_temperature", return_value=25
        ), patch.object(
            thermostat, "_control_ac", new_callable=AsyncMock, return_value=True
        ) as mock_control_ac:

            asyncio.run(thermostat.run_once())

            # Should have called _control_ac with True since temp (25) > desired (22)
            mock_control_ac.assert_called_once_with(True)

    finally:
        os.unlink(config_file_path)
        # Clean up state file if created
        try:
            os.unlink("/tmp/test_state.json")
        except FileNotFoundError:
            pass
