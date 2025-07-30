#!/bin/bash
# Setup audio support for the 8-Relay Control Service
# Run with: sudo bash setup_audio.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
USERNAME="tech"
PROJECT_DIR="/home/${USERNAME}/8-relay"
AUDIO_DIR="${PROJECT_DIR}/audio"

echo -e "${GREEN}Audio Setup for 8-Relay Control Service${NC}"
echo "========================================"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

echo -e "${GREEN}1. Installing audio dependencies...${NC}"
apt-get update
apt-get install -y python3-pygame pulseaudio alsa-utils mpg123

echo -e "${GREEN}2. Creating audio directory...${NC}"
mkdir -p ${AUDIO_DIR}
chown ${USERNAME}:${USERNAME} ${AUDIO_DIR}

echo -e "${GREEN}3. Installing Python audio libraries...${NC}"
cd ${PROJECT_DIR}
if [ -d "venv" ]; then
    sudo -u ${USERNAME} ${PROJECT_DIR}/venv/bin/pip install pygame
else
    echo -e "${RED}Virtual environment not found! Run setup.sh first.${NC}"
    exit 1
fi

echo -e "${GREEN}4. Setting up audio permissions...${NC}"
# Add user to audio group
if ! groups ${USERNAME} | grep -q audio; then
    usermod -a -G audio ${USERNAME}
    echo -e "${YELLOW}Added user '${USERNAME}' to 'audio' group${NC}"
fi

echo -e "${GREEN}5. Testing audio output...${NC}"
# Set default audio output to 3.5mm jack (card 0, device 0)
amixer cset numid=3 1 2>/dev/null || true

# Create a test beep sound
echo -e "${YELLOW}Playing test sound...${NC}"
speaker-test -t sine -f 1000 -l 1 -P 2 -c 1 2>/dev/null || echo -e "${YELLOW}Audio test failed - please check your speakers${NC}"

echo -e "${GREEN}6. Creating sample audio files...${NC}"
# Create sample beep sounds using sox if available
if command -v sox &> /dev/null; then
    # Create a 440Hz beep for 0.5 seconds
    sox -n ${AUDIO_DIR}/beep1.wav synth 0.5 sine 440
    sox -n ${AUDIO_DIR}/beep2.wav synth 0.3 sine 880
    chown ${USERNAME}:${USERNAME} ${AUDIO_DIR}/*.wav
    echo -e "${GREEN}Created sample beep sounds in ${AUDIO_DIR}${NC}"
else
    echo -e "${YELLOW}sox not installed - install it to generate sample sounds:${NC}"
    echo "sudo apt-get install sox"
fi

echo -e "${GREEN}7. Audio configuration tips:${NC}"
echo "- Place your MP3 files in: ${AUDIO_DIR}"
echo "- Update the audio file paths in the config.json"
echo "- Default GPIO pins for audio buttons: 13 and 19"
echo "- Supported formats: MP3, WAV, OGG"
echo ""
echo "To set audio output:"
echo "- For 3.5mm jack: sudo amixer cset numid=3 1"
echo "- For HDMI: sudo amixer cset numid=3 2"
echo "- For USB: sudo amixer cset numid=3 0"
echo ""

echo -e "${GREEN}8. Example audio files:${NC}"
echo "You can download free sound effects from:"
echo "- https://freesound.org"
echo "- https://www.zapsplat.com"
echo "- https://soundbible.com"
echo ""
echo "Or create your own with:"
echo "- sox -n doorbell.wav synth 0.5 sine 800 sine 1200"
echo "- espeak 'Hello World' -w greeting.wav"
echo ""

echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Copy your MP3 files to ${AUDIO_DIR}"
echo "2. Update /home/${USERNAME}/8-relay/config.json with:"
echo "   - Audio file paths"
echo "   - GPIO pins for buttons (default: 5 and 6)"
echo "   - Volume levels (0-100)"
echo "3. Restart the service: sudo systemctl restart relay-control"
echo ""
echo -e "${YELLOW}Note: After adding user to audio group, you may need to logout/login or reboot${NC}"
