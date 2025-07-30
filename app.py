#!/usr/bin/env python3
"""
8-Relay Control System with Audio Playback Support
==================================================

A production-ready Flask application for controlling an 8-channel relay module on Raspberry Pi
with comprehensive physical button support and audio playback capabilities.

Features:
- Web-based control interface for 8 relays
- Physical button support for each relay (8 buttons)
- Audio playback system with 7 configurable sound buttons
- Reset button for canceling relay operations
- Admin dashboard for configuration and monitoring
- Robust error handling and logging
- Systemd service integration

Hardware Support:
- 8-Channel Relay Module (active-low or active-high)
- Up to 8 physical buttons for relay control
- Up to 7 audio playback buttons
- 1 reset button for relay cancellation
- Compatible with all Raspberry Pi models with GPIO

Author: Raspberry Pi Relay Control Project
Version: 2.0.0
License: MIT
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, jsonify, request
import RPi.GPIO as GPIO
import time
import threading
import signal
import atexit
from datetime import datetime
import json
from pathlib import Path
import subprocess
import pygame

# Configuration Management
class Config:
    """
    Configuration management with JSON file support.
    
    Handles all configuration aspects of the relay control system including:
    - Relay pin mappings and settings
    - Button configurations (physical and audio)
    - Server settings
    - Logging configuration
    
    The configuration is loaded from a JSON file and can be updated at runtime.
    """

    # Default configuration with all supported features
    _defaults = {
        "relay_pins": {
            "1": 17, "2": 18, "3": 27, "4": 22,
            "5": 23, "6": 24, "7": 25, "8": 4
        },
        "relay_names": {
            "1": "Relay 1", "2": "Relay 2", "3": "Relay 3", "4": "Relay 4",
            "5": "Relay 5", "6": "Relay 6", "7": "Relay 7", "8": "Relay 8"
        },
        "relay_settings": {
            "active_low": True,
            "trigger_durations": {
                "1": 0.5, "2": 0.5, "3": 0.5, "4": 0.5,
                "5": 0.5, "6": 0.5, "7": 0.5, "8": 0.5
            },
            "max_concurrent_triggers": 3
        },
        "button_settings": {
            "enabled": False,
            "button_pin": 26,
            "relay_number": 1,
            "pull_up": True,
            "debounce_time": 0.3,
            "poll_interval": 0.01
        },
        "multi_button_settings": {
            "enabled": True,
            "buttons": {
                "1": {"pin": 26, "relay": 1, "enabled": True},
                "2": {"pin": 5, "relay": 2, "enabled": True},
                "3": {"pin": 6, "relay": 3, "enabled": True},
                "4": {"pin": 12, "relay": 4, "enabled": True},
                "5": {"pin": 20, "relay": 5, "enabled": True},
                "6": {"pin": 21, "relay": 6, "enabled": True},
                "7": {"pin": 7, "relay": 7, "enabled": True},
                "8": {"pin": 8, "relay": 8, "enabled": True}
            },
            "pull_up": True,
            "debounce_time": 0.3,
            "poll_interval": 0.01
        },
        "reset_button": {
            "enabled": True,
            "pin": 16,
            "pull_up": True,
            "debounce_time": 0.3,
            "poll_interval": 0.01
        },
        "audio_buttons": {
            "enabled": True,
            "button1": {
                "pin": 13,
                "audio_file": "/home/tech/8-relay/audio/doorbell.mp3",
                "name": "Doorbell",
                "volume": 70,
                "pull_up": True,
                "debounce_time": 0.3
            },
            "button2": {
                "pin": 19,
                "audio_file": "/home/tech/8-relay/audio/notification.mp3",
                "name": "Notification",
                "volume": 60,
                "pull_up": True,
                "debounce_time": 0.3
            },
            "button3": {
                "pin": 9,
                "audio_file": "/home/tech/8-relay/audio/chime.mp3",
                "name": "Chime",
                "volume": 65,
                "pull_up": True,
                "debounce_time": 0.3
            },
            "button4": {
                "pin": 10,
                "audio_file": "/home/tech/8-relay/audio/alert.mp3",
                "name": "Alert",
                "volume": 75,
                "pull_up": True,
                "debounce_time": 0.3
            },
            "button5": {
                "pin": 11,
                "audio_file": "/home/tech/8-relay/audio/melody.mp3",
                "name": "Melody",
                "volume": 60,
                "pull_up": True,
                "debounce_time": 0.3
            },
            "button6": {
                "pin": 2,
                "audio_file": "/home/tech/8-relay/audio/warning.mp3",
                "name": "Warning",
                "volume": 80,
                "pull_up": False,  # GPIO 2 has built-in pull-up
                "debounce_time": 0.3
            },
            "button7": {
                "pin": 3,
                "audio_file": "/home/tech/8-relay/audio/success.mp3",
                "name": "Success",
                "volume": 70,
                "pull_up": False,  # GPIO 3 has built-in pull-up
                "debounce_time": 0.3
            }
        },
        "server": {
            "host": "0.0.0.0",
            "port": 5000,
            "debug": False
        },
        "logging": {
            "log_dir": "/var/log/relay_control",
            "log_file": "relay_control.log",
            "max_size_mb": 10,
            "backup_count": 5,
            "log_level": "INFO"
        }
    }

    def __init__(self, config_file="config.json"):
        """Initialize configuration from file or defaults."""
        self.config_file = config_file
        self.config = self._load_config()
        self._migrate_config()

    def _migrate_config(self):
        """Migrate old config format to new format if needed."""
        # If multi_button_settings doesn't exist but button_settings does, create it
        if "multi_button_settings" not in self.config and "button_settings" in self.config:
            # Create multi_button_settings with button 1 from old settings
            self.config["multi_button_settings"] = self._defaults["multi_button_settings"].copy()
            if self.config["button_settings"]["enabled"]:
                self.config["multi_button_settings"]["buttons"]["1"] = {
                    "pin": self.config["button_settings"]["button_pin"],
                    "relay": self.config["button_settings"]["relay_number"],
                    "enabled": True
                }
            self.save_config()

    def _load_config(self):
        """Load configuration from JSON file."""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                with open(self.config_file, 'r') as f:
                    user_config = json.load(f)
                config = self._defaults.copy()
                self._deep_update(config, user_config)
                print(f"Configuration loaded from {self.config_file}")
                return config
            else:
                print(f"No config file found, using defaults")
                with open(self.config_file, 'w') as f:
                    json.dump(self._defaults, f, indent=4)
                return self._defaults.copy()
        except Exception as e:
            print(f"Error loading config: {e}, using defaults")
            return self._defaults.copy()

    def _deep_update(self, base, update):
        """Recursively update nested dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def update_config(self, section, updates):
        """Update a configuration section."""
        if section in self.config:
            if isinstance(self.config[section], dict):
                self._deep_update(self.config[section], updates)
            else:
                self.config[section].update(updates)
            return self.save_config()
        return False

    # Property accessors for configuration values
    @property
    def RELAY_PINS(self):
        """Get relay pin mappings."""
        return {int(k): v for k, v in self.config["relay_pins"].items()}

    @property
    def RELAY_NAMES(self):
        """Get relay names."""
        return {int(k): v for k, v in self.config.get("relay_names", {}).items()}

    @property
    def RELAY_ACTIVE_LOW(self):
        """Check if relays are active-low."""
        return self.config["relay_settings"]["active_low"]

    @property
    def RELAY_TRIGGER_DURATIONS(self):
        """Get relay trigger durations."""
        return {int(k): float(v) for k, v in self.config["relay_settings"]["trigger_durations"].items()}

    @property
    def MAX_CONCURRENT_TRIGGERS(self):
        """Get maximum concurrent relay triggers allowed."""
        return self.config["relay_settings"]["max_concurrent_triggers"]

    @property
    def MULTI_BUTTON_ENABLED(self):
        """Check if multi-button mode is enabled."""
        return self.config.get("multi_button_settings", {}).get("enabled", False)

    @property
    def MULTI_BUTTON_CONFIG(self):
        """Get multi-button configuration."""
        return self.config.get("multi_button_settings", {})

    @property
    def BUTTON_ENABLED(self):
        """Check if single button mode is enabled (legacy support)."""
        if self.MULTI_BUTTON_ENABLED:
            return False
        return self.config.get("button_settings", {}).get("enabled", False)

    @property
    def BUTTON_PIN(self):
        """Get single button GPIO pin."""
        return self.config.get("button_settings", {}).get("button_pin", 26)

    @property
    def BUTTON_RELAY(self):
        """Get relay number for single button."""
        return self.config.get("button_settings", {}).get("relay_number", 1)

    @property
    def BUTTON_PULL_UP(self):
        """Check if button uses pull-up resistor."""
        return self.config.get("button_settings", {}).get("pull_up", True)

    @property
    def BUTTON_DEBOUNCE(self):
        """Get button debounce time."""
        return float(self.config.get("button_settings", {}).get("debounce_time", 0.3))

    @property
    def BUTTON_POLL_INTERVAL(self):
        """Get button polling interval."""
        return float(self.config.get("button_settings", {}).get("poll_interval", 0.01))

    @property
    def RESET_BUTTON_ENABLED(self):
        """Check if reset button is enabled."""
        return self.config.get("reset_button", {}).get("enabled", False)

    @property
    def RESET_BUTTON_PIN(self):
        """Get reset button GPIO pin."""
        return self.config.get("reset_button", {}).get("pin")

    @property
    def RESET_BUTTON_PULL_UP(self):
        """Check if reset button uses pull-up resistor."""
        return self.config.get("reset_button", {}).get("pull_up", True)

    @property
    def RESET_BUTTON_DEBOUNCE(self):
        """Get reset button debounce time."""
        return float(self.config.get("reset_button", {}).get("debounce_time", 0.3))

    @property
    def RESET_BUTTON_POLL_INTERVAL(self):
        """Get reset button polling interval."""
        return float(self.config.get("reset_button", {}).get("poll_interval", 0.01))

    @property
    def AUDIO_BUTTONS_ENABLED(self):
        """Check if audio buttons are enabled."""
        return self.config.get("audio_buttons", {}).get("enabled", False)

    # Audio button configuration properties
    @property
    def AUDIO_BUTTON1_CONFIG(self):
        """Get audio button 1 configuration."""
        return self.config.get("audio_buttons", {}).get("button1", {})

    @property
    def AUDIO_BUTTON2_CONFIG(self):
        """Get audio button 2 configuration."""
        return self.config.get("audio_buttons", {}).get("button2", {})

    @property
    def AUDIO_BUTTON3_CONFIG(self):
        """Get audio button 3 configuration."""
        return self.config.get("audio_buttons", {}).get("button3", {})

    @property
    def AUDIO_BUTTON4_CONFIG(self):
        """Get audio button 4 configuration."""
        return self.config.get("audio_buttons", {}).get("button4", {})

    @property
    def AUDIO_BUTTON5_CONFIG(self):
        """Get audio button 5 configuration."""
        return self.config.get("audio_buttons", {}).get("button5", {})

    @property
    def AUDIO_BUTTON6_CONFIG(self):
        """Get audio button 6 configuration."""
        return self.config.get("audio_buttons", {}).get("button6", {})

    @property
    def AUDIO_BUTTON7_CONFIG(self):
        """Get audio button 7 configuration."""
        return self.config.get("audio_buttons", {}).get("button7", {})

    # Server configuration properties
    @property
    def HOST(self):
        """Get server host address."""
        return self.config["server"]["host"]

    @property
    def PORT(self):
        """Get server port."""
        return self.config["server"]["port"]

    @property
    def DEBUG(self):
        """Check if debug mode is enabled."""
        return self.config["server"]["debug"]

    # Logging configuration properties
    @property
    def LOG_DIR(self):
        """Get log directory path."""
        return self.config["logging"]["log_dir"]

    @property
    def LOG_FILE(self):
        """Get log file name."""
        return self.config["logging"]["log_file"]

    @property
    def LOG_MAX_SIZE(self):
        """Get maximum log file size in bytes."""
        return self.config["logging"]["max_size_mb"] * 1024 * 1024

    @property
    def LOG_BACKUP_COUNT(self):
        """Get number of log backup files to keep."""
        return self.config["logging"]["backup_count"]

    @property
    def LOG_LEVEL(self):
        """Get logging level."""
        return self.config["logging"]["log_level"]


# Audio Utility Functions
def validate_audio_file(filepath):
    """
    Validate that an audio file exists and has a supported extension.
    
    Args:
        filepath (str): Path to the audio file
        
    Returns:
        bool: True if file is valid and readable, False otherwise
    """
    if not filepath:
        return False
    
    if not os.path.exists(filepath):
        app.logger.error(f"Audio file not found: {filepath}")
        return False
    
    valid_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a')
    if not filepath.lower().endswith(valid_extensions):
        app.logger.error(f"Invalid audio file extension: {filepath}")
        return False
    
    # Check if file is readable
    try:
        with open(filepath, 'rb') as f:
            f.read(1)
        return True
    except Exception as e:
        app.logger.error(f"Cannot read audio file {filepath}: {e}")
        return False


# Audio Player Class
class AudioPlayer:
    """
    Handle audio playback using pygame mixer.
    
    This class manages audio playback for the system, initializing the pygame
    mixer with appropriate settings and providing thread-safe playback methods.
    Supports multiple audio drivers with fallback options.
    """
    
    def __init__(self):
        """Initialize audio player instance."""
        self.initialized = False
        self.is_playing = False
        self.lock = threading.Lock()
        
    def initialize(self):
        """
        Initialize pygame mixer for audio playback with fallback drivers.
        
        Tries multiple audio drivers in order of preference to ensure compatibility
        across different Raspberry Pi configurations.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        # Try different audio drivers in order of preference
        drivers = ['pulse', 'alsa', 'oss', 'sdl']
        
        for driver in drivers:
            try:
                os.environ['SDL_AUDIODRIVER'] = driver
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                self.initialized = True
                app.logger.info(f"Audio system initialized successfully with {driver} driver")
                return True
            except Exception as e:
                app.logger.debug(f"Failed to initialize audio with {driver} driver: {e}")
                pygame.mixer.quit()  # Clean up any partial initialization
                continue
        
        # If all drivers fail, try without specifying a driver
        try:
            if 'SDL_AUDIODRIVER' in os.environ:
                del os.environ['SDL_AUDIODRIVER']
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.initialized = True
            app.logger.info("Audio system initialized with default driver")
            return True
        except Exception as e:
            app.logger.error(f"Failed to initialize audio system with any driver: {e}")
            return False
    
    def play_sound(self, audio_file, volume=80):
        """
        Play an audio file with specified volume.
        
        Args:
            audio_file (str): Path to the audio file
            volume (int): Volume level (0-100)
            
        Returns:
            bool: True if playback started successfully, False otherwise
        """
        if not self.initialized:
            app.logger.error("Audio system not initialized")
            return False
            
        # Validate audio file before attempting to play
        if not validate_audio_file(audio_file):
            return False
            
        with self.lock:
            try:
                # Stop any currently playing sound
                pygame.mixer.music.stop()
                
                # Load and play the new sound
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.set_volume(volume / 100.0)
                pygame.mixer.music.play()
                
                app.logger.info(f"Playing audio: {audio_file} at {volume}% volume")
                return True
                
            except pygame.error as e:
                app.logger.error(f"Pygame error playing audio: {e}")
                return False
            except Exception as e:
                app.logger.error(f"Unexpected error playing audio: {e}")
                return False
    
    def stop(self):
        """Stop audio playback."""
        if self.initialized:
            try:
                pygame.mixer.music.stop()
            except:
                pass
    
    def cleanup(self):
        """Cleanup audio system resources."""
        if self.initialized:
            try:
                self.stop()
                pygame.mixer.quit()
            except:
                pass
            self.initialized = False


# Audio Button Handler Class
class AudioButtonHandler:
    """
    Handle physical button input for audio playback.
    
    This class manages individual audio buttons, monitoring GPIO input and
    triggering audio playback when pressed. Uses polling method for reliable
    button detection with configurable debouncing.
    """
    
    def __init__(self, button_config, audio_player, button_name):
        """
        Initialize audio button handler.
        
        Args:
            button_config (dict): Button configuration including pin, audio file, etc.
            audio_player (AudioPlayer): Audio player instance
            button_name (str): Display name for the button
        """
        self.pin = button_config.get('pin')
        self.audio_file = button_config.get('audio_file')
        self.name = button_config.get('name', button_name)
        self.volume = button_config.get('volume', 80)
        self.pull_up = button_config.get('pull_up', True)
        self.debounce_time = float(button_config.get('debounce_time', 0.3))
        self.poll_interval = float(button_config.get('poll_interval', config.BUTTON_POLL_INTERVAL))
        self.audio_player = audio_player
        self.last_press_time = 0
        self.last_state = None
        self.polling_thread = None
        self.stop_polling = threading.Event()
        self.initialized = False
        
    def setup(self):
        """Setup GPIO for button input and start polling thread."""
        try:
            if self.pull_up:
                GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            else:
                GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                
            self.last_state = GPIO.input(self.pin)
            self.stop_polling.clear()
            self.polling_thread = threading.Thread(target=self._poll_button, daemon=True)
            self.polling_thread.start()
            self.initialized = True
            app.logger.info(f"Audio button '{self.name}' initialized on GPIO {self.pin}")
        except Exception as e:
            app.logger.error(f"Audio button setup failed: {e}")
            raise
    
    def _poll_button(self):
        """
        Poll the button state continuously.
        
        Runs in a separate thread to monitor button state changes and
        trigger audio playback when button is pressed.
        """
        while not self.stop_polling.is_set():
            try:
                current_state = GPIO.input(self.pin)
                if self.pull_up:
                    pressed = (self.last_state == 1 and current_state == 0)
                else:
                    pressed = (self.last_state == 0 and current_state == 1)
                
                if pressed:
                    now = time.time()
                    if now - self.last_press_time >= self.debounce_time:
                        self.last_press_time = now
                        app.logger.info(f"Audio button '{self.name}' pressed")
                        
                        # Validate audio file before playing
                        if validate_audio_file(self.audio_file):
                            # Play audio in a separate thread to avoid blocking
                            t = threading.Thread(
                                target=self.audio_player.play_sound,
                                args=(self.audio_file, self.volume),
                                daemon=True
                            )
                            t.start()
                            # Update stats
                            with stats_lock:
                                stats['audio_plays'] += 1
                        else:
                            app.logger.error(f"Invalid audio file configured for {self.name}")
                            with stats_lock:
                                stats['errors'] += 1
                
                self.last_state = current_state
            except Exception as e:
                app.logger.error(f"Error in audio button polling: {e}")
                with stats_lock:
                    stats['errors'] += 1
            time.sleep(self.poll_interval)
    
    def cleanup(self):
        """Stop polling thread and cleanup GPIO resources."""
        self.stop_polling.set()
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=1)
        self.initialized = False
        app.logger.info(f"Audio button '{self.name}' cleanup completed")


# Button Handler Class
class ButtonHandler:
    """
    Handle physical button input for relay control using polling.
    
    This class manages individual relay control buttons, monitoring GPIO input
    and triggering relay activation when pressed. Uses polling method for
    reliable button detection with configurable debouncing.
    """

    def __init__(self, button_pin, relay_trigger_function, relay_number=1,
                 debounce_time=0.3, pull_up=True, poll_interval=0.01):
        """
        Initialize button handler.
        
        Args:
            button_pin (int): GPIO pin number for the button
            relay_trigger_function (callable): Function to call when button pressed
            relay_number (int): Relay number this button controls
            debounce_time (float): Debounce time in seconds
            pull_up (bool): Whether to use internal pull-up resistor
            poll_interval (float): Polling interval in seconds
        """
        self.button_pin = button_pin
        self.trigger_relay = relay_trigger_function
        self.relay_number = relay_number
        self.debounce_time = float(debounce_time)
        self.pull_up = pull_up
        self.poll_interval = float(poll_interval)
        self.last_press_time = 0
        self.last_state = None
        self.polling_thread = None
        self.stop_polling = threading.Event()
        self.initialized = False

    def setup(self):
        """Setup GPIO for button input using polling method."""
        try:
            if self.pull_up:
                GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            else:
                GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            self.last_state = GPIO.input(self.button_pin)
            self.stop_polling.clear()
            self.polling_thread = threading.Thread(target=self._poll_button, daemon=True)
            self.polling_thread.start()
            self.initialized = True
            app.logger.info(f"Button polling started on GPIO {self.button_pin} for Relay {self.relay_number}")
        except Exception as e:
            app.logger.error(f"Button setup failed: {e}")
            raise

    def _poll_button(self):
        """Poll the button state continuously and trigger relay when pressed."""
        while not self.stop_polling.is_set():
            try:
                current_state = GPIO.input(self.button_pin)
                if self.pull_up:
                    pressed = (self.last_state == 1 and current_state == 0)
                else:
                    pressed = (self.last_state == 0 and current_state == 1)

                if pressed:
                    now = time.time()
                    if now - self.last_press_time >= self.debounce_time:
                        self.last_press_time = now
                        app.logger.info(f"Physical button pressed for Relay {self.relay_number}")
                        t = threading.Thread(
                            target=self.trigger_relay,
                            args=(self.relay_number,),
                            daemon=True
                        )
                        t.start()
                        # Update button press stats
                        with stats_lock:
                            stats['button_presses'][self.relay_number] = stats['button_presses'].get(self.relay_number, 0) + 1
                self.last_state = current_state
            except Exception as e:
                app.logger.error(f"Error in button polling: {e}")
                with stats_lock:
                    stats['errors'] += 1
            time.sleep(self.poll_interval)

    def cleanup(self):
        """Stop polling thread and cleanup resources."""
        self.stop_polling.set()
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=1)
        self.initialized = False
        app.logger.info(f"Button polling stopped for GPIO {self.button_pin}")


# Reset Button Handler Class
class ResetButtonHandler:
    """
    Handle physical button input for resetting Relay 1.
    
    This special button handler allows cancellation of Relay 1 operation
    while it's active, useful for emergency stops or corrections.
    """

    def __init__(self, pin, pull_up=True, debounce_time=0.3, poll_interval=0.01):
        """Initialize reset button handler with specified parameters."""
        self.pin = pin
        self.pull_up = pull_up
        self.debounce_time = float(debounce_time)
        self.poll_interval = float(poll_interval)
        self.last_press_time = 0
        self.last_state = None
        self.polling_thread = None
        self.stop_polling = threading.Event()
        self.initialized = False

    def setup(self):
        """Setup GPIO for reset button input."""
        try:
            if self.pull_up:
                GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            else:
                GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            self.last_state = GPIO.input(self.pin)
            self.stop_polling.clear()
            self.polling_thread = threading.Thread(target=self._poll_button, daemon=True)
            self.polling_thread.start()
            self.initialized = True
            app.logger.info(f"Reset Button polling started on GPIO {self.pin}")
        except Exception as e:
            app.logger.error(f"Reset button setup failed: {e}")
            raise

    def _poll_button(self):
        """Poll the button state continuously and trigger reset when pressed."""
        while not self.stop_polling.is_set():
            try:
                current_state = GPIO.input(self.pin)
                if self.pull_up:
                    pressed = (self.last_state == 1 and current_state == 0)
                else:
                    pressed = (self.last_state == 0 and current_state == 1)

                if pressed:
                    now = time.time()
                    if now - self.last_press_time >= self.debounce_time:
                        self.last_press_time = now
                        app.logger.info("Reset button pressed, cancelling Relay 1.")
                        # Set the event to interrupt the trigger_relay function
                        relay_reset_events[1].set()
                
                self.last_state = current_state
            except Exception as e:
                app.logger.error(f"Error in reset button polling: {e}")
            time.sleep(self.poll_interval)

    def cleanup(self):
        """Stop polling thread and cleanup resources."""
        self.stop_polling.set()
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=1)
        self.initialized = False
        app.logger.info("Reset button polling stopped")


# Global variables and initialization
app = Flask(__name__)
config = Config()
relay_locks = {}
active_triggers = 0
active_triggers_lock = threading.Lock()
relay_reset_events = {i: threading.Event() for i in range(1, 9)}
cleanup_done = False
button_handler = None  # Legacy single button
button_handlers = {}  # Dictionary for multi-button handlers
reset_button_handler = None
audio_player = None

# Audio button handlers for all 7 buttons
audio_button1_handler = None
audio_button2_handler = None
audio_button3_handler = None
audio_button4_handler = None
audio_button5_handler = None
audio_button6_handler = None
audio_button7_handler = None

stats_lock = threading.Lock()
initialized_pins = []  # Track initialized pins for cleanup

# Statistics tracking
stats = {
    'start_time': datetime.now(),
    'total_triggers': 0,
    'relay_triggers': {i: 0 for i in range(1, 9)},
    'button_presses': {i: 0 for i in range(1, 9)},
    'last_trigger_time': None,
    'audio_plays': 0,
    'errors': 0
}


def setup_logging():
    """
    Configure logging with rotation.
    
    Sets up both file and console logging with appropriate formatting
    and log rotation to prevent disk space issues.
    """
    try:
        Path(config.LOG_DIR).mkdir(parents=True, exist_ok=True)
        level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
        fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # File handler with rotation
        fh = RotatingFileHandler(
            os.path.join(config.LOG_DIR, config.LOG_FILE),
            maxBytes=config.LOG_MAX_SIZE,
            backupCount=config.LOG_BACKUP_COUNT
        )
        fh.setFormatter(fmt)
        fh.setLevel(level)

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        ch.setLevel(level)

        # Configure app logger
        app.logger.setLevel(level)
        app.logger.addHandler(fh)
        app.logger.addHandler(ch)

        # Configure werkzeug logger (Flask's internal logger)
        werk = logging.getLogger('werkzeug')
        werk.setLevel(logging.WARNING)
        werk.addHandler(fh)
        werk.addHandler(ch)

    except Exception as e:
        print(f"Failed to setup logging: {e}")
        logging.basicConfig(level=logging.INFO)


def setup_gpio():
    """
    Initialize GPIO pins for relay control and buttons with improved error handling.
    
    This function sets up all GPIO pins for:
    - 8 relay outputs
    - Up to 8 physical relay control buttons
    - Up to 7 audio playback buttons
    - 1 reset button
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    global button_handler, button_handlers, reset_button_handler, audio_player
    global audio_button1_handler, audio_button2_handler, audio_button3_handler
    global audio_button4_handler, audio_button5_handler, audio_button6_handler
    global audio_button7_handler, initialized_pins
    
    # Track what we've initialized for cleanup on error
    initialized_pins = []
    initialized_handlers = []
    
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Setup relay output pins
        for relay_num, pin in config.RELAY_PINS.items():
            try:
                GPIO.setup(pin, GPIO.OUT)
                initialized_pins.append(pin)
                off_state = GPIO.HIGH if config.RELAY_ACTIVE_LOW else GPIO.LOW
                GPIO.output(pin, off_state)
                relay_locks[relay_num] = threading.Lock()
                app.logger.debug(f"Initialized relay {relay_num} on GPIO {pin}")
            except Exception as e:
                app.logger.error(f"Failed to setup relay {relay_num} on GPIO {pin}: {e}")
                raise

        # Setup physical relay control buttons
        if config.MULTI_BUTTON_ENABLED:
            # Setup multiple buttons (one per relay)
            multi_config = config.MULTI_BUTTON_CONFIG
            buttons_config = multi_config.get('buttons', {})
            
            for button_id, button_cfg in buttons_config.items():
                if button_cfg.get('enabled', True):
                    try:
                        button_pin = button_cfg.get('pin')
                        relay_num = button_cfg.get('relay')
                        
                        if button_pin and relay_num:
                            handler = ButtonHandler(
                                button_pin=button_pin,
                                relay_trigger_function=trigger_relay,
                                relay_number=relay_num,
                                debounce_time=multi_config.get('debounce_time', 0.3),
                                pull_up=multi_config.get('pull_up', True),
                                poll_interval=multi_config.get('poll_interval', 0.01)
                            )
                            handler.setup()
                            button_handlers[int(button_id)] = handler
                            initialized_pins.append(button_pin)
                            initialized_handlers.append(handler)
                            app.logger.info(f"Button {button_id} initialized on GPIO {button_pin} for Relay {relay_num}")
                    except Exception as e:
                        app.logger.error(f"Failed to setup button {button_id}: {e}")
                        # Continue with other buttons if one fails
                        
        elif config.BUTTON_ENABLED:
            # Legacy single button support
            try:
                button_handler = ButtonHandler(
                    button_pin=config.BUTTON_PIN,
                    relay_trigger_function=trigger_relay,
                    relay_number=config.BUTTON_RELAY,
                    debounce_time=config.BUTTON_DEBOUNCE,
                    pull_up=config.BUTTON_PULL_UP,
                    poll_interval=config.BUTTON_POLL_INTERVAL
                )
                button_handler.setup()
                initialized_pins.append(config.BUTTON_PIN)
                initialized_handlers.append(button_handler)
                app.logger.info(
                    f"Physical button initialized on GPIO {config.BUTTON_PIN} for Relay {config.BUTTON_RELAY}"
                )
            except Exception as e:
                app.logger.error(f"Failed to setup physical button: {e}")
                # Continue without button if it fails

        # Setup reset button
        if config.RESET_BUTTON_ENABLED:
            try:
                reset_button_handler = ResetButtonHandler(
                    pin=config.RESET_BUTTON_PIN,
                    pull_up=config.RESET_BUTTON_PULL_UP,
                    debounce_time=config.RESET_BUTTON_DEBOUNCE,
                    poll_interval=config.RESET_BUTTON_POLL_INTERVAL
                )
                reset_button_handler.setup()
                initialized_pins.append(config.RESET_BUTTON_PIN)
                initialized_handlers.append(reset_button_handler)
                app.logger.info(
                    f"Reset button initialized on GPIO {config.RESET_BUTTON_PIN}"
                )
            except Exception as e:
                app.logger.error(f"Failed to setup reset button: {e}")

        # Setup audio system and buttons
        if config.AUDIO_BUTTONS_ENABLED:
            try:
                # Initialize audio player
                audio_player = AudioPlayer()
                if audio_player.initialize():
                    # Setup all 7 audio buttons
                    audio_handlers = [
                        (config.AUDIO_BUTTON1_CONFIG, 'audio_button1_handler', "Audio Button 1"),
                        (config.AUDIO_BUTTON2_CONFIG, 'audio_button2_handler', "Audio Button 2"),
                        (config.AUDIO_BUTTON3_CONFIG, 'audio_button3_handler', "Audio Button 3"),
                        (config.AUDIO_BUTTON4_CONFIG, 'audio_button4_handler', "Audio Button 4"),
                        (config.AUDIO_BUTTON5_CONFIG, 'audio_button5_handler', "Audio Button 5"),
                        (config.AUDIO_BUTTON6_CONFIG, 'audio_button6_handler', "Audio Button 6"),
                        (config.AUDIO_BUTTON7_CONFIG, 'audio_button7_handler', "Audio Button 7"),
                    ]
                    
                    for btn_config, handler_name, btn_label in audio_handlers:
                        if btn_config.get('pin'):
                            try:
                                # Validate audio file before setting up button
                                if validate_audio_file(btn_config.get('audio_file')):
                                    handler = AudioButtonHandler(
                                        btn_config,
                                        audio_player,
                                        btn_label
                                    )
                                    handler.setup()
                                    globals()[handler_name] = handler
                                    initialized_pins.append(btn_config.get('pin'))
                                    initialized_handlers.append(handler)
                                else:
                                    app.logger.warning(f"{btn_label} disabled due to invalid audio file")
                            except Exception as e:
                                app.logger.error(f"Failed to setup {btn_label}: {e}")
                        
                    app.logger.info("Audio system initialization completed")
                else:
                    app.logger.error("Failed to initialize audio system - audio buttons disabled")
            except Exception as e:
                app.logger.error(f"Failed to setup audio system: {e}")
                # Continue without audio if it fails

        app.logger.info(f"GPIO initialization successful. Initialized {len(initialized_pins)} pins")
        return True

    except Exception as e:
        app.logger.error(f"GPIO initialization failed: {e}")
        # Clean up any partially initialized pins
        cleanup_partial_gpio(initialized_handlers)
        return False


def cleanup_partial_gpio(handlers_to_cleanup):
    """
    Clean up partially initialized GPIO pins and handlers.
    
    This function is called when GPIO initialization fails partway through
    to ensure all initialized resources are properly cleaned up.
    
    Args:
        handlers_to_cleanup (list): List of handler objects to clean up
    """
    global initialized_pins
    
    app.logger.info("Cleaning up partially initialized GPIO...")
    
    # Clean up handlers first
    for handler in handlers_to_cleanup:
        try:
            if hasattr(handler, 'cleanup'):
                handler.cleanup()
        except Exception as e:
            app.logger.error(f"Error cleaning up handler: {e}")
    
    # Clean up individual pins
    for pin in initialized_pins:
        try:
            # Reset pin to input to be safe
            GPIO.setup(pin, GPIO.IN)
        except Exception as e:
            app.logger.error(f"Error cleaning up pin {pin}: {e}")
    
    # Final GPIO cleanup
    try:
        GPIO.cleanup()
    except Exception as e:
        app.logger.error(f"Error in final GPIO cleanup: {e}")


def trigger_relay(relay_num):
    """
    Trigger a relay for its configured duration, can be interrupted.
    
    This function activates a relay for a specified duration. The operation
    can be interrupted by the reset button (for Relay 1 only). Includes
    concurrency control to limit the number of simultaneous relay activations.
    
    Args:
        relay_num (int): Relay number to trigger (1-8)
    """
    global active_triggers

    if relay_num not in config.RELAY_PINS:
        app.logger.error(f"Invalid relay number: {relay_num}")
        return

    # Check concurrent trigger limit
    with active_triggers_lock:
        if active_triggers >= config.MAX_CONCURRENT_TRIGGERS:
            app.logger.warning(f"Max concurrent triggers reached, rejecting relay {relay_num}")
            return
        active_triggers += 1

    acquired = False
    pin = config.RELAY_PINS[relay_num]
    off_state = GPIO.HIGH if config.RELAY_ACTIVE_LOW else GPIO.LOW
    
    try:
        # Try to acquire relay lock (non-blocking)
        acquired = relay_locks[relay_num].acquire(blocking=False)
        if not acquired:
            app.logger.warning(f"Relay {relay_num} is already active")
            return

        duration = config.RELAY_TRIGGER_DURATIONS.get(relay_num, 0.5)
        on_state = GPIO.LOW if config.RELAY_ACTIVE_LOW else GPIO.HIGH

        # Clear any previous reset event for this relay before starting
        relay_reset_events[relay_num].clear()

        # Activate relay
        GPIO.output(pin, on_state)
        app.logger.info(f"Relay {relay_num} (GPIO {pin}) turned ON for {duration}s")

        # Update statistics
        with stats_lock:
            stats['total_triggers'] += 1
            stats['relay_triggers'][relay_num] += 1
            stats['last_trigger_time'] = datetime.now()

        # Wait for the duration, but this wait can be interrupted by the event being set
        interrupted = relay_reset_events[relay_num].wait(timeout=duration)

        if interrupted:
            app.logger.info(f"Relay {relay_num} operation was reset by button press.")
        
    except Exception as e:
        app.logger.error(f"Error triggering relay {relay_num}: {e}")
        with stats_lock:
            stats['errors'] += 1
    finally:
        # Always ensure the relay is turned off
        GPIO.output(pin, off_state)
        app.logger.info(f"Relay {relay_num} (GPIO {pin}) turned OFF")
        
        if acquired:
            relay_locks[relay_num].release()
        
        with active_triggers_lock:
            if active_triggers > 0:
                active_triggers -= 1


# Flask Routes
@app.route('/')
def index():
    """
    Serve the main control panel.
    
    Returns:
        HTML template for the main control interface
    """
    relay_info = {}
    for relay_num in config.RELAY_PINS.keys():
        relay_info[relay_num] = {
            'name': config.RELAY_NAMES.get(relay_num, f'Relay {relay_num}'),
            'pin': config.RELAY_PINS[relay_num]
        }
    return render_template('index.html',
                           relay_info=relay_info,
                           relay_count=len(config.RELAY_PINS))


@app.route('/relay/<int:relay_num>', methods=['POST'])
def control_relay(relay_num):
    """
    Handle relay control requests from web interface.
    
    Args:
        relay_num (int): Relay number to control
        
    Returns:
        JSON response with operation status
    """
    if relay_num < 1 or relay_num > len(config.RELAY_PINS):
        app.logger.warning(f"Invalid relay number requested: {relay_num}")
        return jsonify({'status': 'error', 'message': 'Invalid relay number'}), 400

    client_ip = request.remote_addr
    app.logger.info(f"Relay {relay_num} trigger requested from {client_ip}")

    # Check if relay is already active
    if relay_locks[relay_num].locked():
        return jsonify({'status': 'error', 'message': 'Relay is already active'}), 429

    # Trigger relay in a separate thread
    t = threading.Thread(
        target=trigger_relay,
        args=(relay_num,),
        name=f"relay-{relay_num}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    t.daemon = True
    t.start()

    duration = config.RELAY_TRIGGER_DURATIONS.get(relay_num, 0.5)
    return jsonify({'status': 'success', 'relay': relay_num, 'duration': duration})


@app.route('/audio/play/<int:button_num>', methods=['POST'])
def play_audio(button_num):
    """
    Handle audio playback requests from web interface.
    
    Args:
        button_num (int): Audio button number (1-7)
        
    Returns:
        JSON response with playback status
    """
    if not config.AUDIO_BUTTONS_ENABLED:
        return jsonify({'status': 'error', 'message': 'Audio buttons not enabled'}), 400
    
    # Map button numbers to configs
    audio_configs = {
        1: config.AUDIO_BUTTON1_CONFIG,
        2: config.AUDIO_BUTTON2_CONFIG,
        3: config.AUDIO_BUTTON3_CONFIG,
        4: config.AUDIO_BUTTON4_CONFIG,
        5: config.AUDIO_BUTTON5_CONFIG,
        6: config.AUDIO_BUTTON6_CONFIG,
        7: config.AUDIO_BUTTON7_CONFIG,
    }
    
    if button_num not in audio_configs:
        return jsonify({'status': 'error', 'message': 'Invalid audio button number'}), 400
    
    audio_config = audio_configs[button_num]
    
    # Validate audio file before attempting to play
    audio_file = audio_config.get('audio_file')
    if not validate_audio_file(audio_file):
        return jsonify({'status': 'error', 'message': 'Invalid or missing audio file'}), 400
    
    if audio_player and audio_player.initialized:
        success = audio_player.play_sound(
            audio_file,
            audio_config.get('volume', 80)
        )
        if success:
            with stats_lock:
                stats['audio_plays'] += 1
            return jsonify({
                'status': 'success',
                'message': f"Playing {audio_config.get('name', f'Sound {button_num}')}"
            })
        else:
            return jsonify({'status': 'error', 'message': 'Failed to play audio'}), 500
    else:
        return jsonify({'status': 'error', 'message': 'Audio system not initialized'}), 500


@app.route('/status')
def get_status():
    """
    Get current status of all relays and audio system.
    
    Returns:
        JSON response with complete system status including:
        - Relay states and names
        - System information
        - Audio button configuration
        - Physical button status
    """
    try:
        status = {
            'relays': {},
            'system': {
                'active_triggers': active_triggers,
                'max_concurrent': config.MAX_CONCURRENT_TRIGGERS,
                'timestamp': datetime.now().isoformat(),
                'button_enabled': config.BUTTON_ENABLED or config.MULTI_BUTTON_ENABLED,
                'multi_button_enabled': config.MULTI_BUTTON_ENABLED,
                'button_count': len(button_handlers) if config.MULTI_BUTTON_ENABLED else (1 if config.BUTTON_ENABLED else 0),
                'audio_enabled': config.AUDIO_BUTTONS_ENABLED,
                'audio_system_ready': audio_player.initialized if audio_player else False
            },
            'audio_buttons': {},
            'physical_buttons': {}
        }
        
        # Relay status
        for relay_num, pin in config.RELAY_PINS.items():
            try:
                curr = GPIO.input(pin)
                is_on = (curr == GPIO.LOW) if config.RELAY_ACTIVE_LOW else (curr == GPIO.HIGH)
                status['relays'][relay_num] = {
                    'name': config.RELAY_NAMES.get(relay_num, f'Relay {relay_num}'),
                    'state': 'ON' if is_on else 'OFF',
                    'locked': relay_locks[relay_num].locked(),
                    'gpio_pin': pin,
                    'button_presses': stats['button_presses'].get(relay_num, 0)
                }
            except Exception as e:
                app.logger.error(f"Error reading relay {relay_num} status: {e}")
                status['relays'][relay_num] = {
                    'name': config.RELAY_NAMES.get(relay_num, f'Relay {relay_num}'),
                    'state': 'UNKNOWN',
                    'locked': False,
                    'gpio_pin': pin,
                    'error': str(e)
                }
        
        # Physical button status
        if config.MULTI_BUTTON_ENABLED:
            buttons_config = config.MULTI_BUTTON_CONFIG.get('buttons', {})
            for button_id, button_cfg in buttons_config.items():
                if button_cfg.get('enabled', True):
                    status['physical_buttons'][button_id] = {
                        'pin': button_cfg.get('pin'),
                        'relay': button_cfg.get('relay'),
                        'enabled': True,
                        'active': button_id in button_handlers and button_handlers[int(button_id)].initialized
                    }
        
        # Audio button status with validation
        if config.AUDIO_BUTTONS_ENABLED:
            for btn_num in range(1, 8):
                btn_config_name = f'AUDIO_BUTTON{btn_num}_CONFIG'
                btn_config = getattr(config, btn_config_name, {})
                if btn_config.get('pin'):
                    audio_file = btn_config.get('audio_file', '')
                    status['audio_buttons'][f'button{btn_num}'] = {
                        **btn_config,
                        'audio_file_valid': validate_audio_file(audio_file)
                    }
            
        return jsonify(status)
    except Exception as e:
        app.logger.error(f"Error getting status: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/health')
def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns:
        JSON response with system health status
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'uptime': time.process_time(),
        'gpio_initialized': len(initialized_pins) > 0,
        'errors_last_minute': 0  # Could implement rolling error count
    }
    
    # Check if we have critical errors
    if stats['errors'] > 100:  # Arbitrary threshold
        health_status['status'] = 'degraded'
    
    return jsonify(health_status)


@app.route('/admin')
def admin_dashboard():
    """
    Serve the admin dashboard page.
    
    Returns:
        HTML template for the admin interface
    """
    uptime = datetime.now() - stats['start_time']
    uptime_str = str(uptime).split('.')[0]
    log_file = os.path.join(config.LOG_DIR, config.LOG_FILE)
    recent_logs = []
    
    try:
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                recent_logs = f.readlines()[-50:]
    except Exception as e:
        app.logger.error(f"Error reading logs: {e}")
        
    return render_template('admin.html',
                           config=config.config,
                           stats=stats,
                           uptime=uptime_str,
                           recent_logs=recent_logs)


@app.route('/admin/stats')
def admin_stats():
    """
    Get system statistics for admin dashboard.
    
    Returns:
        JSON response with detailed system statistics
    """
    uptime = datetime.now() - stats['start_time']
    return jsonify({
        'uptime': str(uptime).split('.')[0],
        'total_triggers': stats['total_triggers'],
        'relay_triggers': stats['relay_triggers'],
        'button_presses': stats['button_presses'],
        'last_trigger': stats['last_trigger_time'].isoformat() if stats['last_trigger_time'] else None,
        'audio_plays': stats['audio_plays'],
        'errors': stats['errors'],
        'active_triggers': active_triggers,
        'gpio_pins_initialized': len(initialized_pins),
        'physical_buttons_active': len(button_handlers) if config.MULTI_BUTTON_ENABLED else (1 if button_handler else 0)
    })


@app.route('/admin/logs')
def admin_logs():
    """
    Get recent log entries for admin dashboard.
    
    Returns:
        JSON response with recent log entries
    """
    log_file = os.path.join(config.LOG_DIR, config.LOG_FILE)
    logs = []
    
    try:
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                for line in f.readlines()[-100:]:
                    logs.append(line.strip())
    except Exception as e:
        app.logger.error(f"Error reading logs: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
    return jsonify({'logs': logs})


@app.route('/admin/config', methods=['GET', 'POST'])
def admin_config():
    """
    Get or update system configuration.
    
    Methods:
        GET: Return current configuration
        POST: Update configuration section
        
    Returns:
        JSON response with configuration or update status
    """
    if request.method == 'POST':
        try:
            data = request.json or {}
            section = data.get('section')
            settings = data.get('settings')
            
            # Validate audio files if updating audio settings
            if section == 'audio_buttons' and settings:
                for btn_key in ['button1', 'button2', 'button3', 'button4', 
                               'button5', 'button6', 'button7']:
                    if btn_key in settings and 'audio_file' in settings[btn_key]:
                        audio_file = settings[btn_key]['audio_file']
                        if audio_file and not validate_audio_file(audio_file):
                            return jsonify({
                                'status': 'error', 
                                'message': f'Invalid audio file for {btn_key}: {audio_file}'
                            }), 400
            
            if section and settings and config.update_config(section, settings):
                app.logger.info(f"Configuration updated: {section}")
                return jsonify({'status': 'success', 'message': 'Configuration updated. Restart service to apply changes.'})
            return jsonify({'status': 'error', 'message': 'Invalid request'}), 400
        except Exception as e:
            app.logger.error(f"Error updating config: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
            
    return jsonify(config.config)


@app.route('/admin/test/<int:relay_num>', methods=['POST'])
def admin_test_relay(relay_num):
    """
    Test a specific relay from admin panel.
    
    Args:
        relay_num (int): Relay number to test
        
    Returns:
        JSON response with test status
    """
    return control_relay(relay_num)


@app.route('/admin/validate_audio', methods=['POST'])
def admin_validate_audio():
    """
    Validate an audio file path.
    
    Returns:
        JSON response with validation result and file information
    """
    try:
        data = request.json or {}
        filepath = data.get('filepath', '')
        
        if validate_audio_file(filepath):
            # Get file info
            file_size = os.path.getsize(filepath)
            file_ext = os.path.splitext(filepath)[1].lower()
            
            return jsonify({
                'status': 'success',
                'valid': True,
                'message': 'Audio file is valid',
                'file_info': {
                    'size': file_size,
                    'size_mb': round(file_size / (1024 * 1024), 2),
                    'extension': file_ext
                }
            })
        else:
            return jsonify({
                'status': 'success',
                'valid': False,
                'message': 'Audio file is invalid or not found'
            })
    except Exception as e:
        app.logger.error(f"Error validating audio file: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    app.logger.error(f"Internal error: {error}")
    with stats_lock:
        stats['errors'] += 1
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


def cleanup_gpio():
    """
    Clean up GPIO resources with improved error handling.
    
    This function ensures all GPIO resources are properly released when
    the application shuts down. It handles all button handlers, audio
    system, and relay states.
    """
    global cleanup_done, button_handler, button_handlers, reset_button_handler
    global audio_player, audio_button1_handler, audio_button2_handler
    global audio_button3_handler, audio_button4_handler, audio_button5_handler
    global audio_button6_handler, audio_button7_handler
    
    if cleanup_done:
        return
        
    cleanup_done = True
    app.logger.info("Starting GPIO cleanup...")
    
    cleanup_errors = []
    
    try:
        # Clean up single button handler (legacy)
        if button_handler:
            try:
                button_handler.cleanup()
                app.logger.info("Button handler cleanup completed")
            except Exception as e:
                cleanup_errors.append(f"Button handler cleanup error: {e}")
        
        # Clean up multi-button handlers
        for button_id, handler in button_handlers.items():
            try:
                handler.cleanup()
                app.logger.info(f"Button {button_id} handler cleanup completed")
            except Exception as e:
                cleanup_errors.append(f"Button {button_id} handler cleanup error: {e}")
        
        # Clean up reset button
        if reset_button_handler:
            try:
                reset_button_handler.cleanup()
                app.logger.info("Reset button handler cleanup completed")
            except Exception as e:
                cleanup_errors.append(f"Reset button handler cleanup error: {e}")

        # Clean up all audio button handlers
        audio_handlers = [
            audio_button1_handler, audio_button2_handler, audio_button3_handler,
            audio_button4_handler, audio_button5_handler, audio_button6_handler,
            audio_button7_handler
        ]
        
        for i, handler in enumerate(audio_handlers, 1):
            if handler:
                try:
                    handler.cleanup()
                    app.logger.info(f"Audio button {i} handler cleanup completed")
                except Exception as e:
                    cleanup_errors.append(f"Audio button {i} cleanup error: {e}")
        
        # Clean up audio system
        if audio_player:
            try:
                audio_player.cleanup()
                app.logger.info("Audio system cleanup completed")
            except Exception as e:
                cleanup_errors.append(f"Audio system cleanup error: {e}")
        
        # Turn off all relays
        off_state = GPIO.HIGH if config.RELAY_ACTIVE_LOW else GPIO.LOW
        for relay_num, pin in config.RELAY_PINS.items():
            try:
                GPIO.output(pin, off_state)
                app.logger.debug(f"Relay {relay_num} turned off")
            except Exception as e:
                cleanup_errors.append(f"Failed to turn off relay {relay_num}: {e}")
        
        # Final GPIO cleanup
        try:
            GPIO.cleanup()
            app.logger.info("GPIO cleanup completed successfully")
        except Exception as e:
            cleanup_errors.append(f"GPIO.cleanup() error: {e}")
        
        # Log any cleanup errors
        if cleanup_errors:
            app.logger.error(f"Cleanup completed with {len(cleanup_errors)} errors:")
            for error in cleanup_errors:
                app.logger.error(f"  - {error}")
        else:
            app.logger.info("All cleanup operations completed successfully")
            
    except Exception as e:
        app.logger.error(f"Critical error during GPIO cleanup: {e}")


def signal_handler(signum, frame):
    """
    Handle system signals for graceful shutdown.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    app.logger.info(f"Received signal {signum}, shutting down gracefully...")
    cleanup_gpio()
    sys.exit(0)


# Register cleanup handlers
atexit.register(cleanup_gpio)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    """
    Main entry point with improved error handling.
    
    This function initializes the system, sets up GPIO, and starts
    the Flask web server. It includes comprehensive error handling
    to ensure proper cleanup in case of failures.
    """
    setup_logging()
    app.logger.info("==============================================")
    app.logger.info("Starting 8-Relay Control Application v2.0.0")
    app.logger.info("==============================================")
    app.logger.info(f"Configuration loaded from: {config.config_file}")
    
    # Initialize GPIO
    if not setup_gpio():
        app.logger.error("Failed to initialize GPIO, exiting")
        cleanup_gpio()
        sys.exit(1)
    
    # Log configuration summary
    app.logger.info("System Configuration Summary:")
    app.logger.info(f"  - Relay pins configured: {list(config.RELAY_PINS.values())}")
    app.logger.info(f"  - Relay mode: {'Active-Low' if config.RELAY_ACTIVE_LOW else 'Active-High'}")
    app.logger.info(f"  - Multi-button enabled: {config.MULTI_BUTTON_ENABLED}")
    
    if config.MULTI_BUTTON_ENABLED:
        app.logger.info(f"  - Physical buttons configured: {len(button_handlers)}")
    elif config.BUTTON_ENABLED:
        app.logger.info(f"  - Single button on GPIO {config.BUTTON_PIN}")
    
    app.logger.info(f"  - Audio buttons enabled: {config.AUDIO_BUTTONS_ENABLED}")
    if config.AUDIO_BUTTONS_ENABLED:
        audio_count = sum(1 for i in range(1, 8) 
                         if getattr(config, f'AUDIO_BUTTON{i}_CONFIG').get('pin'))
        app.logger.info(f"  - Audio buttons configured: {audio_count}")
    
    app.logger.info(f"  - Reset button enabled: {config.RESET_BUTTON_ENABLED}")
    
    try:
        app.logger.info("==============================================")
        app.logger.info(f"Starting web server on {config.HOST}:{config.PORT}")
        app.logger.info("==============================================")
        
        # Start Flask application
        app.run(
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            use_reloader=False  # Important: prevents double initialization
        )
    except Exception as e:
        app.logger.error(f"Application error: {e}")
        cleanup_gpio()
        sys.exit(1)


if __name__ == '__main__':
    main()
