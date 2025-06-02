import tempfile
import os
from pathlib import Path
import pytest

from virtual_thermostat.dht11 import DHT11Reader, write_temperature


def test_dht11_reader_initialization():
    """Test DHT11Reader class initialization."""
    # Test without MQTT
    reader = DHT11Reader(pin=4)
    assert reader.pin == 4
    assert not reader.mqtt_enabled
    
    # Test with MQTT
    reader = DHT11Reader(pin=18, mqtt_broker="localhost", mqtt_port=1883, mqtt_topic="test/topic")
    assert reader.pin == 18
    assert reader.mqtt_enabled
    assert reader.mqtt_broker == "localhost"
    assert reader.mqtt_port == 1883
    assert reader.mqtt_topic == "test/topic"


def test_dht11_reader_simulation():
    """Test DHT11Reader simulation mode."""
    reader = DHT11Reader(pin=4)
    temperature, humidity = reader.read_sensor(simulate=True)
    
    assert temperature is not None
    assert humidity is not None
    assert 15 <= temperature <= 30  # Expected range
    assert 30 <= humidity <= 60     # Expected range


def test_write_temperature():
    """Test temperature writing to file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file_path = temp_file.name
    
    try:
        # Test writing temperature
        result = write_temperature(23.7, temp_file_path)
        assert result is True
        
        # Verify file contents
        with open(temp_file_path, 'r') as f:
            content = f.read().strip()
        assert content == "24"  # Should be rounded to nearest integer
        
    finally:
        # Clean up
        os.unlink(temp_file_path)


def test_mqtt_config():
    """Test MQTT configuration handling."""
    # Test MQTT disabled
    reader = DHT11Reader(pin=4)
    result = reader.publish_mqtt(25.0, 60.0)
    assert result is True  # Should return True when MQTT is disabled
    
    # Test MQTT enabled but no broker (will fail but should handle gracefully)
    reader = DHT11Reader(pin=4, mqtt_broker="nonexistent.broker")
    result = reader.publish_mqtt(25.0, 60.0)
    # Should return False due to connection error, but not crash
    assert isinstance(result, bool)