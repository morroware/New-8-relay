#!/bin/bash
# Enhanced Setup script for 8-Relay Control Service with Audio Support
# Run with: sudo bash setup.sh

set -e

# --- CONFIGURATION ---
# Set your username here
USERNAME="tech"
PROJECT_NAME="8-relay"
# --- END CONFIGURATION ---

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/home/${USERNAME}/${PROJECT_NAME}"
SERVICE_NAME="relay-control"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LOG_DIR="/var/log/relay_control"
NGINX_AVAILABLE="/etc/nginx/sites-available/relay-control"
NGINX_ENABLED="/etc/nginx/sites-enabled/relay-control"
AUDIO_DIR="${APP_DIR}/audio"

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          8-Relay Control Service Enhanced Setup Script          ║${NC}"
echo -e "${GREEN}║                     with Audio Support                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo -e "${CYAN}User: ${USERNAME} | Project: ${PROJECT_NAME}${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

# Check if project directory exists
if [ ! -d "$APP_DIR" ]; then
    echo -e "${RED}Project directory $APP_DIR does not exist!${NC}"
    exit 1
fi

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo -e "${YELLOW}Warning: This doesn't appear to be a Raspberry Pi${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Function to print step headers
print_step() {
    echo -e "${BLUE}╭─────────────────────────────────────────────────────────────────╮${NC}"
    echo -e "${BLUE}│ $1${NC}"
    echo -e "${BLUE}╰─────────────────────────────────────────────────────────────────╯${NC}"
}

print_step "Step 1: Installing system dependencies..."
apt-get update
apt-get install -y python3-pip python3-venv python3-dev python3-rpi.gpio nginx \
                   espeak espeak-data alsa-utils pulseaudio sox ffmpeg \
                   libportaudio2 portaudio19-dev python3-pyaudio \
                   libsox-fmt-all

echo -e "${GREEN}✓ System dependencies installed${NC}"

print_step "Step 2: Creating required directories..."
mkdir -p $APP_DIR/templates
mkdir -p $APP_DIR/static
mkdir -p $AUDIO_DIR
mkdir -p $LOG_DIR
chown -R ${USERNAME}:${USERNAME} $APP_DIR
chown ${USERNAME}:${USERNAME} $LOG_DIR

echo -e "${GREEN}✓ Directories created${NC}"

print_step "Step 3: Setting up HTML templates..."
# Copy HTML file to templates directory
if [ -f "$APP_DIR/index.html" ]; then
    cp "$APP_DIR/index.html" "$APP_DIR/templates/"
    echo -e "${GREEN}✓ Copied index.html to templates directory${NC}"
fi

# If v2-index.html exists and user wants dark theme
if [ -f "$APP_DIR/v2-index.html" ]; then
    echo -e "${YELLOW}Found v2-index.html (dark theme version)${NC}"
    read -p "Do you want to use the dark theme version? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        cp "$APP_DIR/v2-index.html" "$APP_DIR/templates/index.html"
        echo -e "${GREEN}✓ Using dark theme version${NC}"
    fi
fi

print_step "Step 4: Creating Python virtual environment..."
cd $APP_DIR
if [ ! -d "venv" ]; then
    sudo -u ${USERNAME} python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}✓ Virtual environment already exists${NC}"
fi

print_step "Step 5: Installing Python dependencies..."
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install flask gunicorn RPi.GPIO pygame

echo -e "${GREEN}✓ Python dependencies installed${NC}"

print_step "Step 6: Setting up GPIO and audio permissions..."
# Add user to required groups
for group in gpio audio; do
    if ! groups ${USERNAME} | grep -q $group; then
        usermod -a -G $group ${USERNAME}
        echo -e "${GREEN}✓ Added user '${USERNAME}' to '$group' group${NC}"
    else
        echo -e "${YELLOW}✓ User '${USERNAME}' already in '$group' group${NC}"
    fi
done

print_step "Step 7: Setting up audio system..."

# Set audio output to 3.5mm jack by default
echo -e "${CYAN}Setting default audio output to 3.5mm jack...${NC}"
amixer cset numid=3 1 2>/dev/null || echo -e "${YELLOW}Could not set audio output (normal on some systems)${NC}"

# Test basic audio
echo -e "${CYAN}Testing audio system...${NC}"
if command -v speaker-test &> /dev/null; then
    echo -e "${CYAN}Running quick audio test...${NC}"
    timeout 3 speaker-test -t sine -f 1000 -l 1 -c 1 2>/dev/null || true
fi

# Test espeak
echo -e "${CYAN}Testing espeak...${NC}"
espeak --stdout "Audio system ready" 2>/dev/null | aplay -q 2>/dev/null || \
    echo -e "${YELLOW}Espeak test failed - audio may need configuration${NC}"

echo -e "${GREEN}✓ Audio system configured${NC}"

print_step "Step 8: Creating sample audio files..."

# Create sample audio files using espeak
echo -e "${CYAN}Generating sample audio files with espeak...${NC}"

# Function to create audio file with espeak
create_audio_file() {
    local text="$1"
    local filename="$2"
    local voice_options="$3"
    
    echo -e "${CYAN}  Creating: ${filename}${NC}"
    
    # Create WAV file first
    espeak $voice_options "$text" -w "${AUDIO_DIR}/${filename%.mp3}.wav" 2>/dev/null
    
    # Convert to MP3 if ffmpeg is available
    if command -v ffmpeg &> /dev/null; then
        ffmpeg -i "${AUDIO_DIR}/${filename%.mp3}.wav" -y "${AUDIO_DIR}/${filename}" 2>/dev/null
        rm "${AUDIO_DIR}/${filename%.mp3}.wav"
    else
        # Rename WAV to MP3 (espeak MP3 output isn't always reliable)
        mv "${AUDIO_DIR}/${filename%.mp3}.wav" "${AUDIO_DIR}/${filename%.mp3}.wav"
        echo -e "${YELLOW}    Using WAV format (ffmpeg not available for MP3 conversion)${NC}"
    fi
}

# Create sample sounds with different voices and effects
create_audio_file "Doorbell" "doorbell.mp3" "-s 150 -p 50"
create_audio_file "You have a notification" "notification.mp3" "-s 160 -v en+f3"
create_audio_file "Chime" "chime.mp3" "-s 140 -p 40"
create_audio_file "Alert! Attention required" "alert.mp3" "-s 180 -p 60 -v en+m3"
create_audio_file "Sweet melody" "melody.mp3" "-s 130 -p 30 -v en+f2"
create_audio_file "Warning! Check system status" "warning.mp3" "-s 170 -p 70 -v en+m5"
create_audio_file "Operation completed successfully" "success.mp3" "-s 160 -p 45 -v en+f4"

# Create more advanced sounds with sox if available
if command -v sox &> /dev/null; then
    echo -e "${CYAN}Creating additional sound effects with sox...${NC}"
    
    # Create a simple doorbell chime
    sox -n "${AUDIO_DIR}/doorbell_chime.wav" synth 0.5 sine 800 sine 1200 fade 0.1 0.5 0.1 2>/dev/null || true
    
    # Create notification beep
    sox -n "${AUDIO_DIR}/notification_beep.wav" synth 0.3 sine 1000 fade 0.05 0.3 0.05 2>/dev/null || true
    
    # Create alert sound
    sox -n "${AUDIO_DIR}/alert_tone.wav" synth 0.2 sine 1500 sine 2000 repeat 2 fade 0.05 0.2 0.05 2>/dev/null || true
    
    echo -e "${GREEN}✓ Created sox-generated sound effects${NC}"
fi

# Set proper permissions
chown -R ${USERNAME}:${USERNAME} ${AUDIO_DIR}
chmod 755 ${AUDIO_DIR}
chmod 644 ${AUDIO_DIR}/*

echo -e "${GREEN}✓ Sample audio files created in ${AUDIO_DIR}${NC}"

print_step "Step 9: Creating systemd service..."
cat > $SERVICE_FILE <<EOF
[Unit]
Description=8-Relay Control Service with Audio Support
After=network.target sound.target

[Service]
Type=simple
User=${USERNAME}
Group=${USERNAME}
WorkingDirectory=${APP_DIR}
Environment="PATH=${APP_DIR}/venv/bin"
Environment="PULSE_RUNTIME_PATH=/run/user/$(id -u ${USERNAME})/pulse"
ExecStart=${APP_DIR}/venv/bin/python ${APP_DIR}/app.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal

# Audio permissions
SupplementaryGroups=audio

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE_NAME

echo -e "${GREEN}✓ Systemd service created and enabled${NC}"

print_step "Step 10: Setting up Nginx reverse proxy (optional)..."
read -p "Do you want to set up Nginx reverse proxy? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    cat > $NGINX_AVAILABLE <<EOF
server {
    listen 80;
    server_name _;

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (if any)
    location /static/ {
        alias ${APP_DIR}/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

    # Remove default nginx site if it exists
    if [ -f "/etc/nginx/sites-enabled/default" ]; then
        rm /etc/nginx/sites-enabled/default
    fi

    ln -sf $NGINX_AVAILABLE $NGINX_ENABLED
    nginx -t && systemctl restart nginx
    echo -e "${GREEN}✓ Nginx configured successfully${NC}"
else
    echo -e "${YELLOW}✓ Skipping Nginx setup${NC}"
fi

print_step "Step 11: Creating convenience and test scripts..."

# Create start script
cat > $APP_DIR/start.sh <<'EOF'
#!/bin/bash
echo "Starting Relay Control service..."
sudo systemctl start relay-control
sleep 2
echo "Service status:"
sudo systemctl status relay-control --no-pager -l
EOF
chmod +x $APP_DIR/start.sh

# Create stop script
cat > $APP_DIR/stop.sh <<'EOF'
#!/bin/bash
echo "Stopping Relay Control service..."
sudo systemctl stop relay-control
echo "Service stopped"
EOF
chmod +x $APP_DIR/stop.sh

# Create logs script
cat > $APP_DIR/logs.sh <<'EOF'
#!/bin/bash
echo "=== Recent Relay Control Service Logs ==="
sudo journalctl -u relay-control -n 50 --no-pager
echo ""
echo "=== Application Log ==="
if [ -f /var/log/relay_control/relay_control.log ]; then
    sudo tail -n 50 /var/log/relay_control/relay_control.log
else
    echo "No application log file found yet"
fi
EOF
chmod +x $APP_DIR/logs.sh

# Create enhanced test script with audio testing
cat > $APP_DIR/test_system.py <<'EOF'
#!/usr/bin/env python3
"""
Enhanced system test for 8-Relay Control with Audio Support
Tests GPIO pins, audio system, and configuration
"""
import RPi.GPIO as GPIO
import time
import os
import sys
import json
import pygame

# Load configuration
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
except Exception as e:
    print(f"Error loading config: {e}")
    sys.exit(1)

RELAY_PINS = [int(pin) for pin in config['relay_pins'].values()]
AUDIO_DIR = "./audio"

def test_gpio_relays():
    """Test GPIO pins for relay module"""
    print("\n" + "="*60)
    print("GPIO RELAY PIN TEST")
    print("="*60)
    print("This will turn each relay ON for 1 second")
    print("Press Ctrl+C to stop\n")

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Setup pins
        for i, pin in enumerate(RELAY_PINS):
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)  # Start with relays OFF (active-low)
            print(f"✓ Initialized Relay {i+1} on GPIO {pin}")

        print("\nStarting relay tests...\n")

        # Test each relay
        for i, pin in enumerate(RELAY_PINS):
            relay_name = config['relay_names'].get(str(i+1), f'Relay {i+1}')
            print(f"Testing {relay_name} (GPIO {pin})... ", end='')
            GPIO.output(pin, GPIO.LOW)   # Turn ON
            time.sleep(1)
            GPIO.output(pin, GPIO.HIGH)  # Turn OFF
            print("✓ PASS")

        print(f"\n✓ All {len(RELAY_PINS)} relays tested successfully!")
        return True

    except KeyboardInterrupt:
        print("\n⚠ Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False
    finally:
        try:
            GPIO.cleanup()
            print("✓ GPIO cleaned up")
        except:
            pass

def test_audio_system():
    """Test audio system and sample files"""
    print("\n" + "="*60)
    print("AUDIO SYSTEM TEST")
    print("="*60)
    
    # Test pygame audio initialization
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        print("✓ Pygame audio initialized successfully")
    except Exception as e:
        print(f"✗ Pygame audio initialization failed: {e}")
        return False
    
    # Test audio files
    if not os.path.exists(AUDIO_DIR):
        print(f"✗ Audio directory {AUDIO_DIR} not found")
        return False
    
    audio_files = []
    for file in os.listdir(AUDIO_DIR):
        if file.endswith(('.mp3', '.wav', '.ogg')):
            audio_files.append(file)
    
    if not audio_files:
        print(f"✗ No audio files found in {AUDIO_DIR}")
        return False
    
    print(f"✓ Found {len(audio_files)} audio files")
    
    # Test playing a sample file
    try:
        test_file = os.path.join(AUDIO_DIR, audio_files[0])
        print(f"Testing playback of: {audio_files[0]}")
        pygame.mixer.music.load(test_file)
        pygame.mixer.music.play()
        time.sleep(2)  # Play for 2 seconds
        pygame.mixer.music.stop()
        print("✓ Audio playback test completed")
        return True
    except Exception as e:
        print(f"✗ Audio playback test failed: {e}")
        return False
    finally:
        try:
            pygame.mixer.quit()
        except:
            pass

def test_configuration():
    """Test configuration file completeness"""
    print("\n" + "="*60)
    print("CONFIGURATION TEST")
    print("="*60)
    
    required_sections = [
        'relay_pins', 'relay_names', 'relay_settings',
        'multi_button_settings', 'audio_buttons', 'server'
    ]
    
    for section in required_sections:
        if section in config:
            print(f"✓ {section} section present")
        else:
            print(f"✗ {section} section missing")
    
    # Test relay configuration
    relay_count = len(config.get('relay_pins', {}))
    print(f"✓ {relay_count} relays configured")
    
    # Test audio button configuration
    audio_buttons = config.get('audio_buttons', {})
    if audio_buttons.get('enabled'):
        audio_count = sum(1 for key in audio_buttons.keys() 
                         if key.startswith('button') and audio_buttons[key].get('pin'))
        print(f"✓ {audio_count} audio buttons configured")
    else:
        print("⚠ Audio buttons disabled")
    
    return True

def main():
    """Main test function"""
    print("8-Relay Control System Test Suite")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 3
    
    # Test configuration
    if test_configuration():
        tests_passed += 1
    
    # Test GPIO relays
    if test_gpio_relays():
        tests_passed += 1
    
    # Test audio system
    if test_audio_system():
        tests_passed += 1
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("✓ All tests PASSED! System is ready.")
        return True
    else:
        print("⚠ Some tests FAILED. Check configuration and wiring.")
        return False

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        GPIO.cleanup()
        sys.exit(1)
EOF
chmod +x $APP_DIR/test_system.py

# Create simple GPIO test script (legacy)
cat > $APP_DIR/test_gpio.py <<'EOF'
#!/usr/bin/env python3
"""Simple GPIO pin test for relay module"""
import RPi.GPIO as GPIO
import time
import json

# Load relay pins from config
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    RELAY_PINS = [int(pin) for pin in config['relay_pins'].values()]
except:
    RELAY_PINS = [17, 18, 27, 22, 23, 24, 25, 4]  # Default pins

print("GPIO Pin Test for Relay Module")
print("==============================")
print("This will turn each relay ON for 1 second")
print("Press Ctrl+C to stop")

try:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Setup pins
    for pin in RELAY_PINS:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)  # Start with relays OFF (active-low)

    # Test each relay
    for i, pin in enumerate(RELAY_PINS):
        print(f"\nTesting Relay {i+1} (GPIO {pin})...")
        GPIO.output(pin, GPIO.LOW)   # Turn ON
        time.sleep(1)
        GPIO.output(pin, GPIO.HIGH)  # Turn OFF
        print(f"Relay {i+1} test complete")

    print("\nAll relays tested successfully!")

except KeyboardInterrupt:
    print("\nTest interrupted")
except Exception as e:
    print(f"Error: {e}")
finally:
    GPIO.cleanup()
    print("GPIO cleaned up")
EOF
chmod +x $APP_DIR/test_gpio.py

# Create audio test script
cat > $APP_DIR/test_audio.py <<'EOF'
#!/usr/bin/env python3
"""Test audio system and sample files"""
import pygame
import os
import time
import sys

AUDIO_DIR = "./audio"

def test_audio():
    print("Audio System Test")
    print("================")
    
    try:
        pygame.mixer.init()
        print("✓ Audio system initialized")
    except Exception as e:
        print(f"✗ Audio initialization failed: {e}")
        return False
    
    if not os.path.exists(AUDIO_DIR):
        print(f"✗ Audio directory {AUDIO_DIR} not found")
        return False
    
    audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.ogg'))]
    
    if not audio_files:
        print(f"✗ No audio files found in {AUDIO_DIR}")
        return False
    
    print(f"Found {len(audio_files)} audio files:")
    for i, file in enumerate(audio_files, 1):
        print(f"  {i}. {file}")
    
    print("\nTesting each file (press Ctrl+C to skip):")
    
    for file in audio_files:
        try:
            print(f"\nPlaying: {file}")
            pygame.mixer.music.load(os.path.join(AUDIO_DIR, file))
            pygame.mixer.music.play()
            time.sleep(3)  # Play for 3 seconds
            pygame.mixer.music.stop()
        except KeyboardInterrupt:
            print("\nSkipping remaining tests...")
            break
        except Exception as e:
            print(f"Error playing {file}: {e}")
    
    pygame.mixer.quit()
    print("\n✓ Audio test completed")
    return True

if __name__ == '__main__':
    test_audio()
EOF
chmod +x $APP_DIR/test_audio.py

echo -e "${GREEN}✓ Test and convenience scripts created${NC}"

print_step "Step 12: Setting final permissions..."
chown -R ${USERNAME}:${USERNAME} $APP_DIR
chmod -R 755 $APP_DIR

# Make scripts executable
chmod +x $APP_DIR/*.sh
chmod +x $APP_DIR/*.py

echo -e "${GREEN}✓ Permissions set correctly${NC}"

print_step "Setup Complete!"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                         SETUP SUMMARY                           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Installation Details:${NC}"
echo -e "  📁 Application directory: ${APP_DIR}"
echo -e "  🔧 Service name: ${SERVICE_NAME}"
echo -e "  📝 Log directory: ${LOG_DIR}"
echo -e "  🔊 Audio directory: ${AUDIO_DIR}"
echo ""
echo -e "${CYAN}Generated Files:${NC}"
echo -e "  🎵 $(find ${AUDIO_DIR} -name "*.mp3" -o -name "*.wav" | wc -l) sample audio files"
echo -e "  📋 System test scripts"
echo -e "  ⚙️ Service management scripts"
echo ""
echo -e "${CYAN}Useful Commands:${NC}"
echo -e "  🚀 Start service:     ${APP_DIR}/start.sh"
echo -e "  🛑 Stop service:      ${APP_DIR}/stop.sh"
echo -e "  📊 View logs:         ${APP_DIR}/logs.sh"
echo -e "  🧪 Test system:      cd ${APP_DIR} && sudo python3 test_system.py"
echo -e "  🔌 Test GPIO only:   cd ${APP_DIR} && sudo python3 test_gpio.py"
echo -e "  🔊 Test audio only:  cd ${APP_DIR} && python3 test_audio.py"
echo ""
echo -e "${CYAN}Manual Commands:${NC}"
echo -e "  📈 Service status:    sudo systemctl status ${SERVICE_NAME}"
echo -e "  📜 Live logs:         sudo journalctl -u ${SERVICE_NAME} -f"
echo -e "  🔄 Restart service:   sudo systemctl restart ${SERVICE_NAME}"
echo ""

read -p "🚀 Do you want to start the service now? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    systemctl start $SERVICE_NAME
    sleep 3
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${GREEN}✓ Service started successfully!${NC}"
        echo ""
        echo -e "${CYAN}🌐 Access the web interface at:${NC}"
        PI_IP=$(hostname -I | cut -d' ' -f1)
        echo -e "  🔗 Main interface:  http://${PI_IP}:5000"
        if [[ -f $NGINX_ENABLED ]]; then
            echo -e "  🔗 Nginx proxy:     http://${PI_IP}"
        fi
        echo -e "  ⚙️ Admin panel:     http://${PI_IP}:5000/admin"
        echo ""
        echo -e "${YELLOW}💡 Pro tip: Run the system test to verify everything works:${NC}"
        echo -e "   cd ${APP_DIR} && sudo python3 test_system.py"
    else
        echo -e "${RED}✗ Service failed to start. Check logs:${NC}"
        echo -e "   sudo journalctl -u ${SERVICE_NAME} -n 20"
    fi
else
    echo -e "${CYAN}You can start the service later with:${NC}"
    echo -e "   sudo systemctl start ${SERVICE_NAME}"
    echo -e "   or use: ${APP_DIR}/start.sh"
fi

echo ""
echo -e "${GREEN}🎉 Enhanced setup completed successfully!${NC}"
echo -e "${PURPLE}   Logout and login again for group changes to take effect${NC}"
echo ""
