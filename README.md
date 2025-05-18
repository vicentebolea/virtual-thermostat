# Virtual Thermostat

A Python daemon for controlling smart plugs connected to air conditioners based on external temperature data.

## Features

- Controls TP-Link Kasa smart plugs using the python-kasa library
- Fetches temperature data from wttr.in
- Maintains state between runs with an external file
- Only triggers AC changes after a configurable cool-down period
- Runs as a daemon process

## Installation

```bash
pip install .
```

## Usage

```bash
vthermostat --help
vthermostat --host 192.168.1.100 --zipcode 12866 --state-file /path/to/state.json --cooldown 360
```

## Command Line Arguments

- `--host`: IP address or hostname of the TP-Link Kasa smart plug
- `--zipcode`: ZIP code for temperature data.
- `--state-file`: Path to the file for storing state between runs
- `--cooldown`: Minimum time (in minutes) between AC state changes

## Authors

- Vicente Bolea -- @vicentebolea
