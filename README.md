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

## Usage

### Temperature Control Script

```bash
# Run once using configuration file
vthermostat-cli

# With custom config and state files
vthermostat-cli --config custom_config.json --state custom_state.json

# With custom temperature file
vthermostat-cli --temp /path/to/temp_sensor.txt
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

Deploy all components using Docker Compose:

```bash
# Quick start with Docker
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

See [DOCKER.md](DOCKER.md) for detailed Docker deployment guide.

## Configuration

### Configuration File (`config/vthermostat_config.json`)

```json
{
  "host": "192.168.1.100",
  "desired_temperature": 24.0,
  "temp_file": "data/temp_sensor.txt",
  "state_file": "config/vthermostat_state.json",
  "cooldown_minutes": 15
}
```

**Configuration Options:**
- `host`: IP address of the smart plug
- `desired_temperature`: Target temperature threshold (°C) - AC turns on when current temperature exceeds this value
- `temp_file`: Path to temperature sensor file
- `state_file`: Path to state persistence file
- `cooldown_minutes`: Minimum time between AC state changes (default: 15)

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

### DHT11 Sensor

Use the built-in DHT11 sensor reader to collect data from hardware sensors:

```bash
# Read DHT11 sensor and write to default file
vthermostat-dht11

# Write to custom file with custom interval
vthermostat-dht11 --output data/temp_data.txt --interval 10

# Specify GPIO pin (default: 4)
vthermostat-dht11 --pin 18
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
# CLI thermostat
vthermostat-cli --help

# Web interface (shows both app and trame options)
vthermostat-ui --help

# Daemon service
vthermostat-daemon --help
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
4. **DHT11 sensor errors**: Check GPIO pin connections and permissions

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
