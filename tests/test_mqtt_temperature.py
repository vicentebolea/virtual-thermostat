import json
import tempfile
import os
from unittest.mock import MagicMock, patch
import pytest

from virtual_thermostat.cli import MQTTTemperatureReader, read_temperature


def test_mqtt_temperature_reader_init():
    """Test MQTTTemperatureReader initialization."""
    reader = MQTTTemperatureReader("localhost", 1883, "test/topic", timeout=5)
    assert reader.broker == "localhost"
    assert reader.port == 1883
    assert reader.topic == "test/topic"
    assert reader.timeout == 5
    assert reader.temperature is None
    assert reader.last_update is None


def test_read_temperature_file_fallback():
    """Test read_temperature falls back to file when MQTT disabled."""
    # Create temporary file with temperature
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("23")
        temp_file_path = temp_file.name
    
    try:
        # Test with MQTT disabled
        mqtt_config = {"enabled": False}
        temperature = read_temperature(temp_file_path, mqtt_config)
        assert temperature == 23
        
        # Test with no MQTT config
        temperature = read_temperature(temp_file_path, None)
        assert temperature == 23
        
    finally:
        os.unlink(temp_file_path)


def test_read_temperature_file_only():
    """Test read_temperature with file only (no MQTT config)."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("26")
        temp_file_path = temp_file.name
    
    try:
        temperature = read_temperature(temp_file_path)
        assert temperature == 26
    finally:
        os.unlink(temp_file_path)


def test_read_temperature_file_error():
    """Test read_temperature handles file errors gracefully."""
    # Non-existent file
    temperature = read_temperature("/nonexistent/file.txt")
    assert temperature is None
    
    # Invalid file content
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("not_a_number")
        temp_file_path = temp_file.name
    
    try:
        temperature = read_temperature(temp_file_path)
        assert temperature is None
    finally:
        os.unlink(temp_file_path)


@patch('virtual_thermostat.cli.HAS_MQTT_LIB', False)
def test_read_temperature_mqtt_no_lib():
    """Test read_temperature when MQTT library not available."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write("22")
        temp_file_path = temp_file.name
    
    try:
        mqtt_config = {"enabled": True, "broker": "localhost"}
        temperature = read_temperature(temp_file_path, mqtt_config)
        # Should fall back to file when MQTT lib not available
        assert temperature == 22
    finally:
        os.unlink(temp_file_path)


def test_mqtt_message_parsing():
    """Test MQTT message parsing logic."""
    reader = MQTTTemperatureReader("localhost", 1883, "test/topic")
    
    # Create mock message
    mock_msg = MagicMock()
    mock_msg.payload.decode.return_value = json.dumps({
        "temperature": 24.5,
        "humidity": 60.0,
        "timestamp": "2025-01-01T12:00:00"
    })
    
    # Test message parsing
    reader._on_message(None, None, mock_msg)
    assert reader.temperature == 24.5
    assert reader.last_update is not None


def test_mqtt_invalid_message():
    """Test MQTT invalid message handling."""
    reader = MQTTTemperatureReader("localhost", 1883, "test/topic")
    
    # Test invalid JSON
    mock_msg = MagicMock()
    mock_msg.payload.decode.return_value = "invalid json"
    
    reader._on_message(None, None, mock_msg)
    assert reader.temperature is None
    
    # Test missing temperature field
    mock_msg.payload.decode.return_value = json.dumps({"humidity": 60.0})
    reader._on_message(None, None, mock_msg)
    assert reader.temperature is None


def test_cli_mqtt_override():
    """Test that CLI arguments override config file MQTT settings."""
    import asyncio
    from unittest.mock import patch, AsyncMock
    from virtual_thermostat.cli import main
    
    # Mock the SmartPlug to avoid actual network calls
    with patch('virtual_thermostat.cli.control_ac', new_callable=AsyncMock) as mock_control_ac:
        mock_control_ac.return_value = True
        
        # Create temp file with temperature
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("23")
            temp_file_path = temp_file.name
        
        # Create config file with MQTT disabled
        config_data = {
            "host": "192.168.1.100",
            "desired_temperature": 24.0,
            "mqtt": {"enabled": False}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as config_file:
            json.dump(config_data, config_file)
            config_file_path = config_file.name
        
        try:
            # Test that CLI MQTT args enable MQTT despite config having it disabled
            # This should try MQTT first, fail, then fallback to file
            asyncio.run(main(
                config_file=config_file_path,
                temp_file=temp_file_path,
                mqtt_broker="nonexistent.broker",  # Will fail and fallback
                mqtt_topic="test/topic"
            ))
            
            # Should have called control_ac since temperature reading succeeded
            assert mock_control_ac.called
            
        finally:
            os.unlink(temp_file_path)
            os.unlink(config_file_path)