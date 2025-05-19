#!/usr/bin/env python3
"""
Virtual Thermostat - Web interface for controlling smart plugs based on temperature.
"""

import asyncio
import threading
from pathlib import Path
import logging

from flask import Flask, render_template, jsonify, request

# Configure logging
logger = logging.getLogger("virtual-thermostat")

def create_flask_app(thermostat):
    """Create a Flask app for the web interface."""
    app = Flask(__name__)
    
    # Define static directory for templates
    template_dir = Path(__file__).resolve().parent / "templates"
    if not template_dir.exists():
        template_dir.mkdir()
        
    # Create the templates directory and index.html
    index_html_path = template_dir / "index.html"
    if not index_html_path.exists():
        html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Virtual Thermostat</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .status {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 4px;
            font-weight: bold;
        }
        .enabled {
            background-color: #d4edda;
            color: #155724;
        }
        .disabled {
            background-color: #f8d7da;
            color: #721c24;
        }
        .ac-on {
            background-color: #cce5ff;
            color: #004085;
        }
        .ac-off {
            background-color: #e2e3e5;
            color: #383d41;
        }
        .temperature {
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }
        button {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
        }
        .primary {
            background-color: #007bff;
            color: white;
        }
        .danger {
            background-color: #dc3545;
            color: white;
        }
        .success {
            background-color: #28a745;
            color: white;
        }
        .refresh {
            float: right;
            padding: 5px 10px;
            background-color: #6c757d;
            color: white;
        }
    </style>
</head>
<body>
    <h1>Virtual Thermostat Control Panel</h1>
    <button onclick="refresh()" class="refresh">Refresh</button>
    
    <div class="card">
        <h2>Thermostat Status</h2>
        <p>Status: <span id="status-label" class="status">Loading...</span></p>
        <p>AC Status: <span id="ac-status-label" class="status">Loading...</span></p>
        <p>Last action: <span id="last-action">Loading...</span></p>
        <div id="controls">
            <button id="enable-btn" onclick="enableThermostat()" class="success">Enable Thermostat</button>
            <button id="disable-btn" onclick="disableThermostat()" class="danger">Disable Thermostat</button>
        </div>
        
        <h3>AC Controls</h3>
        <div id="ac-controls">
            <button onclick="turnACOn()" class="primary">Turn AC ON</button>
            <button onclick="turnACOff()" class="primary">Turn AC OFF</button>
        </div>
    </div>
    
    <div class="card">
        <h2>Temperature</h2>
        <div class="temperature" id="current-temp">Loading...</div>
        <p>Temperature thresholds: <span id="thresholds">Loading...</span></p>
        <p>Last updated: <span id="last-updated">Loading...</span></p>
    </div>
    
    <div class="card">
        <h2>Settings</h2>
        <p>Host: <span id="host">Loading...</span></p>
        <p>Zipcode: <span id="zipcode">Loading...</span></p>
        
        <h3>Temperature Thresholds</h3>
        <div style="margin-bottom: 10px;">
            <label for="temp-low">Low (°<span id="temp-unit">F</span>): </label>
            <input type="number" id="temp-low" style="width: 80px;"> 
            <label for="temp-high" style="margin-left: 10px;">High (°<span id="temp-unit2">F</span>): </label>
            <input type="number" id="temp-high" style="width: 80px;">
            <button onclick="updateTemperatureThresholds()" class="primary" style="margin-left: 10px;">Update</button>
        </div>
        
        <h3>Cooldown Period</h3>
        <div>
            <label for="cooldown-minutes">Minutes: </label>
            <input type="number" id="cooldown-minutes" style="width: 80px;">
            <button onclick="updateCooldownPeriod()" class="primary" style="margin-left: 10px;">Update</button>
        </div>
        <p style="margin-top: 10px;">Current cooldown period: <span id="cooldown">Loading...</span></p>
    </div>
    
    <script>
        // Refresh timer ID for auto-refresh
        let refreshTimerId = null;
        
        function refresh() {
            fetchInfo();
        }
        
        function startAutoRefresh(intervalSeconds = 10) {
            stopAutoRefresh();
            refreshTimerId = setInterval(fetchInfo, intervalSeconds * 1000);
            console.log(`Auto-refresh started: every ${intervalSeconds} seconds`);
        }
        
        function stopAutoRefresh() {
            if (refreshTimerId) {
                clearInterval(refreshTimerId);
                refreshTimerId = null;
                console.log('Auto-refresh stopped');
            }
        }
        
        function fetchInfo() {
            fetch('/api/info')
                .then(response => response.json())
                .then(data => updateUI(data))
                .catch(error => console.error('Error fetching data:', error));
        }
        
        function updateUI(data) {
            // Update status
            const statusLabel = document.getElementById('status-label');
            statusLabel.textContent = data.enabled ? 'Enabled' : 'Disabled';
            statusLabel.className = data.enabled ? 'status enabled' : 'status disabled';
            
            // Update AC status
            const acStatus = document.getElementById('ac-status-label');
            if (data.last_action === 'turn_on') {
                acStatus.textContent = 'ON';
                acStatus.className = 'status ac-on';
            } else if (data.last_action === 'turn_off') {
                acStatus.textContent = 'OFF';
                acStatus.className = 'status ac-off';
            } else {
                acStatus.textContent = 'Unknown';
                acStatus.className = 'status';
            }
            
            // Update temperature
            if (data.current_temperature) {
                document.getElementById('current-temp').textContent = 
                    `${data.current_temperature.toFixed(1)}°${data.temp_unit}`;
            } else {
                document.getElementById('current-temp').textContent = 'No data';
            }
            
            // Update thresholds
            document.getElementById('thresholds').textContent = 
                `Low: ${data.temp_threshold_low}°${data.temp_unit}, High: ${data.temp_threshold_high}°${data.temp_unit}`;
            
            // Update last action
            if (data.last_action_time) {
                const lastActionTime = new Date(data.last_action_time);
                document.getElementById('last-action').textContent = 
                    `${data.last_action === 'turn_on' ? 'Turned ON' : 'Turned OFF'} at ${lastActionTime.toLocaleString()}`;
                document.getElementById('last-updated').textContent = lastActionTime.toLocaleString();
            } else {
                document.getElementById('last-action').textContent = 'No actions yet';
                document.getElementById('last-updated').textContent = 'No data';
            }
            
            // Update settings
            document.getElementById('host').textContent = data.host;
            document.getElementById('zipcode').textContent = data.zipcode;
            document.getElementById('cooldown').textContent = `${data.cooldown_minutes} minutes`;
            
            // Update temperature threshold inputs
            document.getElementById('temp-low').value = data.temp_threshold_low;
            document.getElementById('temp-high').value = data.temp_threshold_high;
            document.getElementById('temp-unit').textContent = data.temp_unit;
            document.getElementById('temp-unit2').textContent = data.temp_unit;
            
            // Update cooldown input
            document.getElementById('cooldown-minutes').value = data.cooldown_minutes;
            
            // Update buttons visibility
            document.getElementById('enable-btn').style.display = data.enabled ? 'none' : 'inline-block';
            document.getElementById('disable-btn').style.display = data.enabled ? 'inline-block' : 'none';
        }
        
        function enableThermostat() {
            fetch('/api/enable', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        fetchInfo();
                    } else {
                        alert('Failed to enable thermostat: ' + data.message);
                    }
                })
                .catch(error => console.error('Error:', error));
        }
        
        function disableThermostat() {
            fetch('/api/disable', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        fetchInfo();
                    } else {
                        alert('Failed to disable thermostat: ' + data.message);
                    }
                })
                .catch(error => console.error('Error:', error));
        }
        
        function turnACOn() {
            fetch('/api/ac/on', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Wait a moment for the AC to respond then refresh
                        setTimeout(fetchInfo, 1000);
                    } else {
                        alert('Failed to turn AC on: ' + data.message);
                    }
                })
                .catch(error => console.error('Error:', error));
        }
        
        function turnACOff() {
            fetch('/api/ac/off', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Wait a moment for the AC to respond then refresh
                        setTimeout(fetchInfo, 1000);
                    } else {
                        alert('Failed to turn AC off: ' + data.message);
                    }
                })
                .catch(error => console.error('Error:', error));
        }
        
        function updateTemperatureThresholds() {
            const tempLow = document.getElementById('temp-low').value;
            const tempHigh = document.getElementById('temp-high').value;
            
            if (!tempLow || !tempHigh) {
                alert('Please enter both low and high temperature thresholds.');
                return;
            }
            
            if (parseFloat(tempLow) >= parseFloat(tempHigh)) {
                alert('Low temperature must be less than high temperature.');
                return;
            }
            
            fetch('/api/settings/temperature', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ temp_low: parseFloat(tempLow), temp_high: parseFloat(tempHigh) })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Temperature thresholds updated successfully!');
                    fetchInfo(); // Refresh the UI
                } else {
                    alert('Failed to update temperature thresholds: ' + data.message);
                }
            })
            .catch(error => console.error('Error:', error));
        }
        
        function updateCooldownPeriod() {
            const cooldownMinutes = document.getElementById('cooldown-minutes').value;
            
            if (!cooldownMinutes) {
                alert('Please enter a cooldown period.');
                return;
            }
            
            if (parseInt(cooldownMinutes) < 1) {
                alert('Cooldown period must be at least 1 minute.');
                return;
            }
            
            fetch('/api/settings/cooldown', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cooldown_minutes: parseInt(cooldownMinutes) })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Cooldown period updated successfully!');
                    fetchInfo(); // Refresh the UI
                } else {
                    alert('Failed to update cooldown period: ' + data.message);
                }
            })
            .catch(error => console.error('Error:', error));
        }
        
        // Initial load and start auto-refresh
        document.addEventListener('DOMContentLoaded', () => {
            fetchInfo();
            startAutoRefresh(10); // Auto-refresh every 10 seconds
        });
    </script>
</body>
</html>
"""
        with open(index_html_path, "w") as f:
            f.write(html_content)
            
    # API routes
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/api/info')
    def get_info():
        return jsonify(thermostat.get_info())
    
    @app.route('/api/enable', methods=['POST'])
    def enable_thermostat():
        thermostat.enable()
        return jsonify({"success": True, "enabled": True})
    
    @app.route('/api/disable', methods=['POST'])
    def disable_thermostat():
        thermostat.disable()
        return jsonify({"success": True, "enabled": False})
    
    @app.route('/api/ac/on', methods=['POST'])
    def turn_ac_on():
        # Run async function in a new thread to avoid blocking
        thread = threading.Thread(target=lambda: asyncio.run(thermostat.set_plug_state(True)))
        thread.daemon = True
        thread.start()
        return jsonify({"success": True, "message": "AC turning ON"})
    
    @app.route('/api/ac/off', methods=['POST'])
    def turn_ac_off():
        # Run async function in a new thread to avoid blocking
        thread = threading.Thread(target=lambda: asyncio.run(thermostat.set_plug_state(False)))
        thread.daemon = True
        thread.start()
        return jsonify({"success": True, "message": "AC turning OFF"})
    
    @app.route('/api/settings/temperature', methods=['POST'])
    def update_temperature_settings():
        data = request.json
        temp_low = data.get('temp_low')
        temp_high = data.get('temp_high')
        
        if temp_low is None or temp_high is None:
            return jsonify({"success": False, "message": "Missing temperature thresholds"})
        
        if temp_low >= temp_high:
            return jsonify({"success": False, "message": "Low threshold must be less than high threshold"})
        
        # Update thermostat settings
        thermostat.temp_threshold_low = temp_low
        thermostat.temp_threshold_high = temp_high
        thermostat._save_state()
        
        logger.info(f"Updated temperature thresholds: LOW={temp_low}°{thermostat.temp_unit}, HIGH={temp_high}°{thermostat.temp_unit}")
        return jsonify({"success": True, "message": "Temperature thresholds updated successfully"})
    
    @app.route('/api/settings/cooldown', methods=['POST'])
    def update_cooldown_settings():
        data = request.json
        cooldown_minutes = data.get('cooldown_minutes')
        
        if cooldown_minutes is None or cooldown_minutes < 1:
            return jsonify({"success": False, "message": "Invalid cooldown period"})
        
        # Update thermostat settings
        thermostat.cooldown_minutes = cooldown_minutes
        thermostat._save_state()
        
        logger.info(f"Updated cooldown period: {cooldown_minutes} minutes")
        return jsonify({"success": True, "message": "Cooldown period updated successfully"})
    
    return app

def run_flask_app(app, port):
    """Run the Flask app in a separate thread."""
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)