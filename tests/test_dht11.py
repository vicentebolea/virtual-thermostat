import pytest
import unittest.mock

# Mock Adafruit_DHT to disable hardware dependency in tests
with unittest.mock.patch.dict(
    "sys.modules", {"Adafruit_DHT": unittest.mock.MagicMock()}
):
    from virtual_thermostat.dht11 import DHT11Sensor


def test_dht11_sensor_initialization():
    """Test DHT11Sensor class initialization."""
    # Test without MQTT
    sensor = DHT11Sensor(pin=4)
    assert sensor.pin == 4
    assert sensor.mqtt_broker is None

    # Test with MQTT
    sensor = DHT11Sensor(
        pin=18, mqtt_broker="localhost", mqtt_port=1883, mqtt_topic="test/topic"
    )
    assert sensor.pin == 18
    assert sensor.mqtt_broker == "localhost"
    assert sensor.mqtt_port == 1883
    assert sensor.mqtt_topic == "test/topic"


def test_dht11_sensor_simulation():
    """Test DHT11Sensor simulation mode."""
    sensor = DHT11Sensor(pin=4)
    temperature, humidity = sensor.read_sensor(simulate=True)

    assert temperature is not None
    assert humidity is not None
    assert 15 <= temperature <= 30  # Expected range
    assert 30 <= humidity <= 60  # Expected range


def test_mqtt_required():
    """Test that MQTT broker is required for operations."""
    sensor = DHT11Sensor(pin=4)  # No MQTT broker

    with pytest.raises(Exception):  # Should raise ClickException
        sensor.run_once(simulate=True)

    with pytest.raises(Exception):  # Should raise ClickException
        sensor.run_continuous(30, simulate=True)


def test_mqtt_config():
    """Test MQTT configuration handling."""
    # Test MQTT disabled
    sensor = DHT11Sensor(pin=4)
    result = sensor.publish_mqtt(25.0, 60.0)
    assert result is True  # Should return True when MQTT is disabled

    # Test MQTT enabled but no broker (will fail but should handle gracefully)
    sensor = DHT11Sensor(pin=4, mqtt_broker="nonexistent.broker")
    result = sensor.publish_mqtt(25.0, 60.0)
    # Should return False due to connection error, but not crash
    assert isinstance(result, bool)
