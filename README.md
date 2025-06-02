# Virtual Thermostat

A Python application for controlling smart plugs connected to air conditioners
based on temperature sensor data. The AC turns on when temperature exceeds a
desired threshold, featuring a modern web-based controller interface with dark
theme and real-time monitoring.

## Features

- **Smart AC Control**: Controls TP-Link Kasa smart plugs using the python-kasa library
- **Temperature Monitoring**: Reads temperature data from local sensor files
- **Modern Web Interface**: Dark-themed trame-based web interface with responsive design
- **Real-time Auto-refresh**: Configurable automatic data refresh every 5 seconds
- **Dual Temperature Units**: Support for both Celsius and Fahrenheit display with live conversion
- **Intuitive Controls**: Slider-based temperature and cooldown configuration
- **Mobile-Friendly**: Responsive design that works on phones and tablets
- **Cooldown Protection**: Configurable cooldown period to prevent frequent AC cycling
- **State Management**: Maintains state between runs with persistent JSON files
- **Real-time Control**: Enable/disable thermostat functionality via web interface
- **DHT11 Sensor Support**: Built-in support for DHT11 temperature/humidity sensors
- **MQTT Integration**: Publish temperature data to MQTT brokers for IoT integration

## Installation

### Development Installation

```bash
# Clone the repository
git clone <repository-url>
cd virtual-thermostat

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e .[dev]
```

### Production Installation

```bash
pip install .
```

### Sensor Installation (DHT11 + MQTT)

For installations that need DHT11 sensor and MQTT support (uses modern CircuitPython libraries):

```bash
pip install .[sensor]
```

### Control Installation (Web UI + CLI)

For installations that only need the thermostat control features:

```bash
pip install .[control]
```

## Usage

### Temperature Control Script

```bash
# Run once using configuration file
vthermostat-cli

# With custom config and state files
vthermostat-cli --config custom_config.json --state custom_state.json

# With custom temperature file
vthermostat-cli --temp /path/to/temp_sensor.txt

# With MQTT options (overrides config file)
vthermostat-cli --mqtt-broker 192.168.1.50 --mqtt-port 1883 --mqtt-topic sensors/temperature

# Force MQTT usage even if config has it disabled
vthermostat-cli --mqtt-broker localhost --mqtt-topic home/temperature
```

### Web Controller

```bash
# Start the web controller interface (default port 8080)
vthermostat-ui

# With custom config and state files
vthermostat-ui --config custom_config.json --state custom_state.json

# With custom port (trame argument)
vthermostat-ui --port 9090

# Show all available options (including trame options)
vthermostat-ui --help
```

The web interface provides:
- **Dark Theme**: Modern dark interface optimized for readability
- **Real-time Monitoring**: Live temperature display with auto-refresh toggle
- **Slider Controls**: Intuitive temperature and cooldown time adjustment
- **Responsive Layout**: Mobile-friendly design that adapts to screen size
- **Unit Conversion**: Seamless switching between °C and °F
- **Status Display**: Current AC state, last run time, and refresh status

### Running as Daemon

```bash
# Start daemon with default 60s interval
vthermostat-daemon

# Custom interval and config files
vthermostat-daemon --interval 30 --config custom_config.json
```

### Docker Deployment

Deploy all components including MQTT broker using Docker Compose:

```bash
# Quick start with Docker (includes MQTT broker)
docker-compose up -d

# View logs for all services
docker-compose logs -f

# View MQTT broker logs specifically
docker-compose logs -f mqtt

# Stop services
docker-compose down
```

**Docker Services:**
- **mqtt**: Eclipse Mosquitto MQTT broker (ports 1883, 9001)
- **dht11**: DHT11 sensor reader (publishes to MQTT)
- **daemon**: Thermostat daemon (subscribes to MQTT for temperature)
- **ui**: Web interface

**MQTT Integration:**
- DHT11 sensor publishes temperature data to `thermostat/temperature`
- Thermostat daemon subscribes to receive temperature updates
- No file-based communication needed when using MQTT

See [DOCKER.md](DOCKER.md) for detailed Docker deployment guide.

## Configuration

### Configuration File (`config/vthermostat_config.json`)

```json
{
  "host": "192.168.1.100",
  "desired_temperature": 24.0,
  "temp_file": "data/temp_sensor.txt",
  "state_file": "config/vthermostat_state.json",
  "cooldown_minutes": 15,
  "mqtt": {
    "enabled": false,
    "broker": "localhost",
    "port": 1883,
    "topic": "thermostat/temperature"
  }
}
```

**Configuration Options:**
- `host`: IP address of the smart plug
- `desired_temperature`: Target temperature threshold (°C) - AC turns on when current temperature exceeds this value
- `temp_file`: Path to temperature sensor file
- `state_file`: Path to state persistence file
- `cooldown_minutes`: Minimum time between AC state changes (default: 15)
- `mqtt`: MQTT configuration object
  - `enabled`: Enable/disable MQTT publishing
  - `broker`: MQTT broker hostname or IP
  - `port`: MQTT broker port (default: 1883)
  - `topic`: MQTT topic for temperature data

### State File (`config/vthermostat_state.json`)

The state file automatically tracks:
- Last AC state (on/off)
- Last run timestamp
- Current temperature reading
- Thermostat enabled status
- Display unit preference (°C/°F)
- Last AC state change time (for cooldown tracking)

## Temperature Sources

### File-based Sensor

The application can read temperature from a text file containing the temperature value in Celsius:

```
# data/temp_sensor.txt
25
```

### DHT11 Sensor with MQTT Support

The DHT11 sensor reader uses modern Adafruit CircuitPython libraries and supports both hardware sensors and simulation mode. MQTT publishing is configured via CLI arguments.

**Key Features:**
- Class-based architecture for better code organization
- Modern CircuitPython DHT library (`adafruit-circuitpython-dht`)
- Automatic hardware detection and graceful simulation fallback
- Built-in MQTT publishing with JSON payload
- Supports common Raspberry Pi GPIO pins (4, 17, 18, 22, 23, 24, 25, 27)
- Robust error handling for sensor reading failures

```bash
# Basic usage - continuous reading from GPIO pin 4
vthermostat-dht11

# Single reading with verbose output
vthermostat-dht11 --once --verbose

# Custom GPIO pin and output file
vthermostat-dht11 --pin 18 --output /tmp/temperature.txt

# Custom reading interval (30 seconds default)
vthermostat-dht11 --interval 60

# MQTT publishing to custom broker
vthermostat-dht11 --mqtt-broker 192.168.1.50 --mqtt-port 1883 --mqtt-topic home/sensors/temperature

# Simulation mode (no hardware required)
vthermostat-dht11 --simulate --once --verbose

# Production example with MQTT
vthermostat-dht11 --pin 4 --interval 30 --mqtt-broker homeassistant.local --mqtt-topic thermostat/dht11
```

**MQTT Payload Format:**
```json
{
  "temperature": 23.5,
  "humidity": 65.2,
  "timestamp": "2025-01-01T12:30:45.123456"
}
```

## How It Works

The thermostat uses simple threshold control with hysteresis:
- **AC turns ON** when current temperature > desired temperature
- **AC turns OFF** when current temperature ≤ desired temperature
- **Cooldown period** prevents rapid cycling and protects equipment
- **Web interface** provides real-time monitoring and control

## Web Interface Features

### Main Controls
- **Enable/Disable Toggle**: Master control for thermostat operation
- **Temperature Slider**: Visual adjustment of desired temperature (10-35°C range)
- **Unit Toggle**: Switch between Celsius and Fahrenheit display
- **Auto-refresh Toggle**: Enable/disable 5-second automatic updates

### Status Display
- **Current Temperature**: Live reading with unit display
- **AC State**: Current on/off status
- **Last Run**: Timestamp of last thermostat operation
- **Cooldown Time**: Visual slider for adjustment (1-60 minutes)

### Advanced Features
- **Responsive Design**: Adapts to mobile screens with proper touch targets
- **Dark Theme**: Reduces eye strain in low-light conditions
- **Real-time Updates**: Background refresh keeps data current
- **Persistent Settings**: All preferences saved automatically

## Command Line Options

All commands support `--help` to see available options:

```bash
# CLI thermostat (with MQTT support)
vthermostat-cli --help

# Web interface (shows both app and trame options)
vthermostat-ui --help

# Daemon service
vthermostat-daemon --help

# DHT11 sensor reader (with MQTT CLI options)
vthermostat-dht11 --help
```

## Development

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=virtual_thermostat

# Run specific test
pytest tests/test_specific.py
```

### Code Quality

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .
```

### Project Structure

```
virtual-thermostat/
├── virtual_thermostat/
│   ├── __init__.py
│   ├── cli.py          # Command-line interface
│   ├── ui.py           # Web interface
│   ├── daemon.py       # Background service
│   └── dht11.py        # DHT11 sensor reader
├── config/             # Configuration files
│   ├── vthermostat_config.json
│   └── vthermostat_state.json
├── data/               # Runtime data
│   └── temp_sensor.txt
├── tests/
│   └── test_*.py
├── docker-compose.yml  # Docker deployment
├── pyproject.toml      # Project configuration
└── README.md
```

## Troubleshooting

### Common Issues

1. **Smart plug not responding**: Check network connectivity and IP address
2. **Temperature file not found**: Verify temp_file path in configuration
3. **Web interface not loading**: Check port availability and firewall settings
4. **DHT11 sensor errors**: Check GPIO pin connections, permissions, and ensure using supported pins (4, 17, 18, 22, 23, 24, 25, 27)
5. **CircuitPython warnings**: Generic platform warnings are normal on non-Raspberry Pi systems when using simulation mode

### Logging

Enable debug logging for troubleshooting:

```bash
# Set log level in code or via environment
export PYTHONPATH=/path/to/virtual-thermostat
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
```

## License

MIT License

## Authors

- Vicente Bolea -- @vicentebolea
