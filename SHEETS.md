# Google Sheets Logger Setup

The Google Sheets logger uploads temperature and humidity data from MQTT to a Google Sheets spreadsheet at configurable intervals.

## Setup Instructions

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Sheets API and Google Drive API

### 2. Create Service Account

1. Go to IAM & Admin > Service Accounts
2. Click "Create Service Account"
3. Give it a name like "virtual-thermostat-sheets"
4. Grant it "Editor" role (or create custom role with Sheets/Drive permissions)
5. Create a key (JSON format) and download it

### 3. Setup Spreadsheet

1. Create a new Google Sheets spreadsheet
2. Copy the spreadsheet ID from the URL (the long string between `/d/` and `/edit`)
3. Share the spreadsheet with the service account email (found in the credentials JSON)
4. Give it "Editor" permissions

### 4. Configure the Application

1. Copy your credentials JSON file to `config/google_sheets_credentials.json`
2. Update `config/vthermostat_config.json`:
   ```json
   {
     "google_sheets": {
       "enabled": true,
       "credentials_file": "config/google_sheets_credentials.json",
       "spreadsheet_id": "YOUR_SPREADSHEET_ID_HERE",
       "worksheet_name": "Temperature_Data",
       "upload_interval_minutes": 15
     }
   }
   ```

### 5. Install Dependencies

```bash
pip install -e ".[sheets]"
```

## Usage

### Run Once (Single Upload)
```bash
vthermostat-sheets --config config/vthermostat_config.json
```

### Run as Daemon (Continuous Logging)
```bash
vthermostat-sheets --config config/vthermostat_config.json --daemon --check-interval 30
```

### Command Line Options

- `--config`: Path to configuration file
- `--daemon`: Run continuously as a daemon
- `--check-interval`: How often to check for new data (seconds, default: 30)
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## Configuration Options

- `enabled`: Enable/disable Google Sheets logging
- `credentials_file`: Path to Google service account credentials JSON
- `spreadsheet_id`: Google Sheets spreadsheet ID
- `worksheet_name`: Name of the worksheet (will be created if it doesn't exist)
- `upload_interval_minutes`: How often to upload data to sheets (default: 15 minutes)

## Data Format

The logger creates a worksheet with these columns:
- **Timestamp**: Date and time of the reading
- **Temperature (°C)**: Temperature in Celsius from MQTT
- **Humidity (%)**: Relative humidity percentage from MQTT
- **Device**: Device name from configuration
- **AC State**: Current AC state (ON/OFF) from state file
- **Last Run**: Last time the thermostat ran from state file
- **Last AC Change**: Last time AC state changed from state file
- **Thermostat Enabled**: Whether thermostat is enabled (YES/NO) from config
- **Desired Temp (°C)**: Target temperature from configuration

## Troubleshooting

### Common Issues

1. **"Google Sheets is not enabled"**: Set `enabled: true` in the google_sheets config section
2. **"Credentials file not found"**: Ensure the path to your credentials JSON is correct
3. **"No spreadsheet_id configured"**: Add your spreadsheet ID to the configuration
4. **Permission denied**: Make sure the service account email has edit access to the spreadsheet

### Logs

Use `--log-level DEBUG` to see detailed logging information about MQTT connections and Google Sheets operations.