# 8-Relay Control System for Raspberry Pi

A production-ready web-based control system for managing an 8-channel relay module with physical button support and audio playback capabilities.

## Features

- **Web Interface**: Modern, responsive control panel with dark theme support
- **8 Relay Control**: Individual control of 8 relays with configurable durations
- **Physical Buttons**: Hardware button support for triggering relays
- **Audio Playback**: Two configurable audio buttons for sound effects
- **Reset Button**: Hardware reset button to cancel relay operations
- **Admin Dashboard**: Configure relay names, durations, and monitor system stats
- **Systemd Service**: Runs as a system service with automatic startup
- **Nginx Integration**: Optional reverse proxy support
- **Comprehensive Logging**: Rotating log files with configurable levels

## Hardware Requirements

- Raspberry Pi (any model with GPIO pins)
- 8-Channel Relay Module (5V, active-low recommended)
- Optional: Physical buttons (momentary push buttons)
- Optional: Speaker/audio output for sound playback
- Jumper wires for connections
- 5V Power supply for relay module (if needed)

## Software Requirements

- Raspberry Pi OS (Raspbian)
- Python 3.7+
- Internet connection for initial setup

## Quick Installation

1. **Clone or download the project** to your Raspberry Pi:
```bash
cd /home/tech
git clone https://github.com/yourusername/8-relay.git
cd 8-relay
```

2. **Make the setup script executable**:
```bash
chmod +x setup.sh
```

3. **Run the setup script**:
```bash
sudo bash setup.sh
```

4. **For audio support** (optional):
```bash
chmod +x setup-audio.sh
sudo bash setup-audio.sh
```

## Wiring Guide

### Relay Module Connections

Connect your 8-channel relay module to the Raspberry Pi GPIO pins:

| Relay | GPIO Pin | Physical Pin |
|-------|----------|--------------|
| Relay 1 | GPIO 17 | Pin 11 |
| Relay 2 | GPIO 18 | Pin 12 |
| Relay 3 | GPIO 27 | Pin 13 |
| Relay 4 | GPIO 22 | Pin 15 |
| Relay 5 | GPIO 23 | Pin 16 |
| Relay 6 | GPIO 24 | Pin 18 |
| Relay 7 | GPIO 25 | Pin 22 |
| Relay 8 | GPIO 4  | Pin 7  |

**Power Connections:**
- VCC → 5V (Pin 2 or 4)
- GND → Ground (Pin 6, 9, 14, 20, 25, 30, 34, or 39)
- Some relay modules require separate 5V power for the relays (JD-VCC)

### Physical Button Connections (Optional)

**Relay Trigger Button:**
- Button Pin 1 → GPIO 26 (Pin 37)
- Button Pin 2 → Ground

**Reset Button:**
- Button Pin 1 → GPIO 16 (Pin 36)
- Button Pin 2 → Ground

**Audio Buttons:**
- Audio Button 1: GPIO 13 (Pin 33) → Ground
- Audio Button 2: GPIO 19 (Pin 35) → Ground

**Note:** All buttons use internal pull-up resistors, so they should connect between GPIO and Ground.

### Wiring Diagram
```
Raspberry Pi                    8-Channel Relay Module
+-----------+                   +------------------+
|        5V |-------------------| VCC              |
|       GND |-------------------| GND              |
|   GPIO 17 |-------------------| IN1              |
|   GPIO 18 |-------------------| IN2              |
|   GPIO 27 |-------------------| IN3              |
|   GPIO 22 |-------------------| IN4              |
|   GPIO 23 |-------------------| IN5              |
|   GPIO 24 |-------------------| IN6              |
|   GPIO 25 |-------------------| IN7              |
|    GPIO 4 |-------------------| IN8              |
+-----------+                   +------------------+

Physical Buttons (Optional)
+-----------+
|   GPIO 26 |----[Button]----GND  (Relay Trigger)
|   GPIO 16 |----[Button]----GND  (Reset)
|   GPIO 13 |----[Button]----GND  (Audio 1)
|   GPIO 19 |----[Button]----GND  (Audio 2)
+-----------+
```

## Configuration

The system uses a `config.json` file for all settings. Key configuration options:

### Relay Settings
```json
{
    "relay_pins": {
        "1": 17, "2": 18, "3": 27, "4": 22,
        "5": 23, "6": 24, "7": 25, "8": 4
    },
    "relay_names": {
        "1": "Front Light",
        "2": "Back Light",
        // ... customize as needed
    },
    "relay_settings": {
        "active_low": true,  // Set to false for active-high relays
        "trigger_durations": {
            "1": 0.5,  // Duration in seconds
            "2": 1.0,
            // ... per relay
        }
    }
}
```

### Button Configuration
```json
{
    "button_settings": {
        "enabled": true,
        "button_pin": 26,
        "relay_number": 1,  // Which relay to trigger
        "pull_up": true,
        "debounce_time": 0.3
    }
}
```

### Audio Configuration
```json
{
    "audio_buttons": {
        "enabled": true,
        "button1": {
            "pin": 13,
            "audio_file": "/home/tech/8-relay/audio/doorbell.mp3",
            "name": "Doorbell",
            "volume": 80
        }
    }
}
```

## Usage

### Starting the Service
```bash
sudo systemctl start relay-control
# or use the convenience script:
./start.sh
```

### Accessing the Web Interface
Open a web browser and navigate to:
- `http://YOUR_RASPBERRY_PI_IP:5000`
- Or if Nginx is configured: `http://YOUR_RASPBERRY_PI_IP`

### Admin Dashboard
Access the admin dashboard at:
- `http://YOUR_RASPBERRY_PI_IP:5000/admin`

Features available:
- Configure relay names and durations
- Enable/disable physical buttons
- Configure audio settings
- View system statistics
- Monitor real-time logs

### Service Management
```bash
# Start service
sudo systemctl start relay-control

# Stop service
sudo systemctl stop relay-control

# Restart service
sudo systemctl restart relay-control

# View service status
sudo systemctl status relay-control

# View logs
sudo journalctl -u relay-control -f

# Or use convenience scripts:
./start.sh
./stop.sh
./logs.sh
```

## API Endpoints

### Relay Control
- `POST /relay/<relay_number>` - Trigger a relay
- `GET /status` - Get current status of all relays

### Audio Control
- `POST /audio/play/<button_number>` - Play audio file

### Admin
- `GET /admin` - Admin dashboard
- `GET /admin/stats` - System statistics
- `POST /admin/config` - Update configuration

## Troubleshooting

### Common Issues

1. **Permission Denied Errors**
   - Ensure the user is in the `gpio` group: `sudo usermod -a -G gpio tech`
   - Logout and login again for group changes to take effect

2. **Relays Not Working**
   - Check wiring connections
   - Verify correct GPIO pins in config.json
   - Test with: `sudo python3 test_gpio.py`

3. **Audio Not Playing**
   - Check audio file paths in config.json
   - Ensure audio files exist and are readable
   - Test audio output: `speaker-test -t sine -f 1000 -l 1`
   - Set audio output: `sudo amixer cset numid=3 1` (for 3.5mm jack)

4. **Web Interface Not Loading**
   - Check if service is running: `sudo systemctl status relay-control`
   - Check firewall settings
   - Verify port 5000 is not in use

### Debug Mode
Enable debug logging in config.json:
```json
{
    "logging": {
        "log_level": "DEBUG"
    }
}
```

## Safety Considerations

⚠️ **WARNING**: When working with relays that control mains voltage (110V/220V):
- Always use proper insulation
- Never work on live circuits
- Use appropriate rated relays for your load
- Consider using optically isolated relay modules
- Follow local electrical codes and regulations

## File Structure
```
8-relay/
├── app.py              # Main Flask application
├── config.json         # Configuration file
├── setup.sh            # Installation script
├── setup-audio.sh      # Audio setup script
├── templates/
│   ├── index.html      # Main control panel
│   ├── v2-index.html   # Dark theme version
│   └── admin.html      # Admin dashboard
├── audio/              # Audio files directory
├── logs/               # Log files
├── start.sh            # Start service script
├── stop.sh             # Stop service script
├── logs.sh             # View logs script
└── test_gpio.py        # GPIO test utility
```

## Advanced Configuration

### Using Different GPIO Pins
Edit `config.json` and update the pin mappings:
```json
{
    "relay_pins": {
        "1": 5,  // Change to your desired GPIO pin
        "2": 6,
        // ...
    }
}
```

### Changing Relay Behavior
For active-high relays (relay turns ON when GPIO is HIGH):
```json
{
    "relay_settings": {
        "active_low": false
    }
}
```

### Custom Audio Files
1. Place MP3/WAV files in the `/home/tech/8-relay/audio/` directory
2. Update paths in config.json
3. Restart the service

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

This project is open source and available under the MIT License.

## Credits

Created for Raspberry Pi enthusiasts who need reliable relay control with web interface and physical button support.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs: `./logs.sh`
3. Submit an issue on GitHub with:
   - Raspberry Pi model
   - OS version
   - Error messages from logs
   - Wiring configuration
