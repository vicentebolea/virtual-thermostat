# Docker Deployment Guide

This guide explains how to deploy the Virtual Thermostat using Docker Compose with three containers using host networking.

## Architecture

The Docker Compose setup deploys three containers using host networking:

1. **UI Container** (`vthermostat-ui`): Web interface on port 8080
2. **Daemon Container** (`vthermostat-daemon`): Background thermostat control service
3. **DHT11 Container** (`vthermostat-dht11`): Temperature sensor reader

All containers use host networking for direct access to local network devices (smart plugs) and GPIO pins (Raspberry Pi).

## Quick Start

1. **Clone and navigate to the repository:**
   ```bash
   git clone <repository-url>
   cd virtual-thermostat
   ```

2. **Configure the system:**
   ```bash
   # Edit the configuration file
   nano config/vthermostat_config.json
   ```

3. **Start all services:**
   ```bash
   docker-compose up -d
   ```

4. **Access the web interface:**
   - Open http://localhost:8080 in your browser

## Configuration

### Main Configuration (`config/vthermostat_config.json`)

```json
{
  "host": "192.168.1.100",          // Smart plug IP address
  "desired_temperature": 24.0,      // Target temperature in Celsius
  "temp_file": "/app/data/temp_sensor.txt",
  "state_file": "/app/data/vthermostat_state.json",
  "cooldown_minutes": 15            // Cooldown period between AC state changes
}
```

### Directory Structure

```
virtual-thermostat/
├── docker-compose.yml
├── config/
│   └── vthermostat_config.json    // Configuration file
└── data/                          // Persistent data (auto-created)
    ├── temp_sensor.txt           // Current temperature reading
    └── vthermostat_state.json    // Application state
```

## Container Details

### UI Container
- **Port**: 8080 (web interface)
- **Purpose**: Provides web-based control and monitoring
- **Features**: Dark theme, responsive design, real-time updates

### Daemon Container
- **Purpose**: Background service that controls the smart plug
- **Interval**: Runs every 60 seconds (configurable)
- **Function**: Reads temperature and controls AC based on settings

### DHT11 Container
- **Purpose**: Reads temperature from DHT11 sensor (or simulates readings)
- **Output**: Writes temperature to shared data file
- **Mode**: Simulation mode by default (for testing without hardware)

## Hardware Setup (Raspberry Pi)

For actual DHT11 sensor on Raspberry Pi, modify the docker-compose.yml:

```yaml
dht11:
  image: ghcr.io/vicentebolea/virtual-thermostat:latest
  container_name: vthermostat-dht11
  privileged: true
  devices:
    - /dev/gpiomem:/dev/gpiomem
  volumes:
    - ./data:/app/data
  command: ["vthermostat-dht11", "--output", "/app/data/temp_sensor.txt", "--interval", "30", "--pin", "4"]
```

## Docker Commands

### Start Services
```bash
# Start all containers
docker-compose up -d

# Start specific container
docker-compose up -d ui
```

### Monitor Services
```bash
# View logs from all containers
docker-compose logs -f

# View logs from specific container
docker-compose logs -f ui
docker-compose logs -f daemon
docker-compose logs -f dht11
```

### Stop Services
```bash
# Stop all containers
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Update Image
```bash
# Pull latest image and restart
docker-compose pull
docker-compose up -d
```

## Customization

### Change Ports
With host networking, modify the command to use a different port:
```yaml
ui:
  command: ["vthermostat-ui", "--config", "/app/config/vthermostat_config.json", "--state", "/app/data/vthermostat_state.json", "--port", "9090"]
```
Then access the UI at http://localhost:9090

### Adjust Intervals
Modify the command arguments:
```yaml
daemon:
  command: ["vthermostat-daemon", "--interval", "30"]  # Check every 30 seconds

dht11:
  command: ["vthermostat-dht11", "--interval", "15"]   # Read every 15 seconds
```

### Use Different GPIO Pin
For Raspberry Pi hardware:
```yaml
dht11:
  command: ["vthermostat-dht11", "--pin", "18"]  # Use GPIO pin 18
```

## Troubleshooting

### Check Container Status
```bash
docker-compose ps
```

### View Container Logs
```bash
# All containers
docker-compose logs

# Specific container with timestamps
docker-compose logs -t ui
```

### Restart Specific Container
```bash
docker-compose restart daemon
```

### Access Container Shell
```bash
docker-compose exec ui bash
```

### Check Temperature File
```bash
cat data/temp_sensor.txt
```

### Network Issues
- With host networking, containers have direct access to the host's network
- Ensure smart plug IP is accessible from the host machine
- Check firewall settings
- Verify smart plug is on same network

### Permission Issues
```bash
# Fix permissions on data directory
chmod -R 755 data/
```

## Environment Variables

You can override settings using environment variables:

```yaml
services:
  daemon:
    environment:
      - SMART_PLUG_HOST=192.168.1.200
      - DESIRED_TEMP=22.0
```

## Data Persistence

Data is persisted in the `./data` directory:
- `temp_sensor.txt`: Current temperature reading
- `vthermostat_state.json`: Application state (AC status, last run, etc.)

## Security Notes

- The containers run with minimal privileges by default
- For hardware access (DHT11), privileged mode is required
- Consider using Docker secrets for sensitive configuration
- Restrict network access as needed

## Scaling

To run multiple instances (e.g., different rooms):

```bash
# Copy configuration
cp -r config config-room2
# Edit config-room2/vthermostat_config.json with different settings

# Run second instance
docker-compose -f docker-compose.yml -f docker-compose.room2.yml up -d
```