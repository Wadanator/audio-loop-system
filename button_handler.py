# button_handler.py
import logging
import RPi.GPIO as GPIO
import threading
import time

logger = logging.getLogger(__name__)

class UniversalButtonHandler:
    """
    A reliable handler for GPIO buttons with advanced debouncing using polling.
    Implements proper mechanical debouncing with configurable parameters.
    """
    
    def __init__(self, callback, config: dict):
        """
        Initializes the button handler.

        Args:
            callback (callable): The function to call on a button press.
            config (dict): The configuration dictionary for GPIO pins.
        """
        if not callable(callback):
            raise TypeError("Provided callback is not a function!")
            
        self.callback = callback
        self.config = config.get('raspberry_pi', {})
        self.debounce_config = config.get('debouncing', {})
        
        # Button configuration
        self.button_pins = self.config.get('button_pins', {})
        self.gpio_pins_to_instruments = {pin: int(key) for key, pin in self.button_pins.items()}
        
        # Debouncing parameters (configurable)
        self.debounce_time_ms = self.debounce_config.get('debounce_time_ms', 50)  # Time to wait for stable signal
        self.min_press_duration_ms = self.debounce_config.get('min_press_duration_ms', 20)  # Minimum press time
        self.poll_interval_ms = self.debounce_config.get('poll_interval_ms', 5)  # Polling frequency
        self.double_press_protection_ms = self.debounce_config.get('double_press_protection_ms', 200)  # Prevent double presses
        
        # State tracking for each button
        self.button_states = {}  # Current stable state
        self.raw_states = {}     # Raw GPIO readings
        self.state_change_times = {}  # When state last changed
        self.last_trigger_times = {}  # When button was last triggered
        self.stable_counters = {}    # Counter for stable readings
        
        # Threading
        self.running = False
        self.poll_thread = None
        
        # Convert ms to seconds for internal use
        self.debounce_time = self.debounce_time_ms / 1000.0
        self.min_press_duration = self.min_press_duration_ms / 1000.0
        self.poll_interval = self.poll_interval_ms / 1000.0
        self.double_press_protection = self.double_press_protection_ms / 1000.0
        
        try:
            self._setup_gpio()
            logger.info(f"GPIO handler successfully set up for {len(self.button_pins)} buttons.")
            logger.info(f"Debouncing config - Time: {self.debounce_time_ms}ms, "
                       f"Min press: {self.min_press_duration_ms}ms, "
                       f"Poll: {self.poll_interval_ms}ms, "
                       f"Double protection: {self.double_press_protection_ms}ms")
        except RuntimeError as e:
            logger.error(f"Critical error during GPIO setup: {e}")
            logger.error("Please ensure the script is running on a Raspberry Pi with the necessary permissions.")
            raise

    def _setup_gpio(self):
        """Initializes GPIO pins and their initial state."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        pull_resistor = GPIO.PUD_UP if self.config.get('pull_up', True) else GPIO.PUD_DOWN
        expected_idle_state = GPIO.HIGH if self.config.get('pull_up', True) else GPIO.LOW
        
        current_time = time.time()
        
        for pin in self.button_pins.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=pull_resistor)
            initial_state = GPIO.input(pin)
            
            # Initialize all state tracking
            self.button_states[pin] = initial_state
            self.raw_states[pin] = initial_state
            self.state_change_times[pin] = current_time
            self.last_trigger_times[pin] = 0
            self.stable_counters[pin] = 0
            
            logger.debug(f"Initialized GPIO {pin} - Initial state: {initial_state}, Expected idle: {expected_idle_state}")

    def _is_pressed(self, pin_state):
        """Determines if a pin state represents a button press based on pull-up/down configuration."""
        if self.config.get('pull_up', True):
            return pin_state == GPIO.LOW  # With pull-up, pressed = LOW
        else:
            return pin_state == GPIO.HIGH  # With pull-down, pressed = HIGH

    def _debounce_button(self, pin, current_time):
        """
        Advanced debouncing logic for a single button.
        
        Args:
            pin: GPIO pin number
            current_time: Current timestamp
            
        Returns:
            bool: True if a valid button press should be triggered
        """
        raw_state = GPIO.input(pin)
        previous_raw = self.raw_states[pin]
        current_stable = self.button_states[pin]
        
        # Update raw state
        self.raw_states[pin] = raw_state
        
        # Check if raw state changed
        if raw_state != previous_raw:
            # State transition detected, reset debounce timer
            self.state_change_times[pin] = current_time
            self.stable_counters[pin] = 0
            return False
        
        # State is stable, check if enough time has passed for debouncing
        time_since_change = current_time - self.state_change_times[pin]
        
        if time_since_change < self.debounce_time:
            # Still in debounce period
            return False
        
        # Check if state has actually changed from our stable state
        if raw_state == current_stable:
            # No change in stable state
            return False
        
        # State has changed and is stable, update our stable state
        old_stable_state = self.button_states[pin]
        self.button_states[pin] = raw_state
        
        # Check if this is a press (transition to pressed state)
        was_pressed = self._is_pressed(old_stable_state)
        is_now_pressed = self._is_pressed(raw_state)
        
        if not was_pressed and is_now_pressed:
            # This is a new press
            
            # Check minimum press duration by looking ahead briefly
            # (This helps filter out very short glitches)
            time.sleep(self.min_press_duration)
            if GPIO.input(pin) != raw_state:
                logger.debug(f"GPIO {pin}: Press too short, ignoring")
                return False
            
            # Check double-press protection
            if (current_time - self.last_trigger_times[pin]) < self.double_press_protection:
                logger.debug(f"GPIO {pin}: Double press protection active, ignoring")
                return False
            
            # Valid press detected
            self.last_trigger_times[pin] = current_time
            return True
        
        return False

    def _poll_loop(self):
        """Main polling loop with advanced debouncing."""
        logger.info(f"Starting button polling loop (interval: {self.poll_interval_ms}ms)")
        
        while self.running:
            current_time = time.time()
            
            for pin, instrument_num in self.gpio_pins_to_instruments.items():
                try:
                    if self._debounce_button(pin, current_time):
                        logger.debug(f"Valid press detected on GPIO {pin} (instrument {instrument_num})")
                        # Call the callback in a separate thread to avoid blocking polling
                        threading.Thread(
                            target=self.callback,
                            args=(instrument_num,),
                            daemon=True
                        ).start()
                except Exception as e:
                    logger.error(f"Error processing GPIO {pin}: {e}")
            
            time.sleep(self.poll_interval)

    def start(self):
        """Starts the polling in a separate thread."""
        if self.running:
            logger.warning("Button handler already running")
            return
        
        self.running = True
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        logger.info("Button handler is ready and actively listening for buttons.")

    def stop(self):
        """Safely stops the thread and cleans up GPIO."""
        if not self.running:
            return
        
        logger.info("Stopping button handler...")
        self.running = False
        
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=1.0)
        
        try:
            GPIO.cleanup()
            logger.info("Button handler stopped and GPIO cleaned up.")
        except Exception as e:
            logger.error(f"Error during GPIO cleanup: {e}")

    def get_button_status(self):
        """Returns current status of all buttons for debugging."""
        status = {}
        for pin, instrument_num in self.gpio_pins_to_instruments.items():
            status[instrument_num] = {
                'pin': pin,
                'stable_state': self.button_states.get(pin, 'unknown'),
                'raw_state': self.raw_states.get(pin, 'unknown'),
                'is_pressed': self._is_pressed(self.button_states.get(pin, GPIO.HIGH)),
                'last_trigger': self.last_trigger_times.get(pin, 0)
            }
        return status