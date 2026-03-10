# button_handler.py
"""GPIO button handler with polling-based mechanical debouncing."""

import logging
import RPi.GPIO as GPIO
import threading
import time


logger = logging.getLogger(__name__)


class UniversalButtonHandler:
    """Reliable GPIO button handler with configurable polling debounce.

    Uses a polling loop rather than interrupt-driven GPIO callbacks,
    which avoids missing events under high system load. Debouncing is
    implemented as a non-blocking state machine so all pins are serviced
    on every polling tick.
    """

    def __init__(self, callback, config: dict):
        """Initialize the button handler and configure all GPIO pins.

        Args:
            callback: Callable invoked with the instrument number (int)
                when a valid button press is detected.
            config: Application configuration dictionary. Must contain
                ``'raspberry_pi'`` and ``'debouncing'`` sub-dictionaries.

        Raises:
            TypeError: If ``callback`` is not callable.
            RuntimeError: If GPIO setup fails (e.g. not running on RPi).
        """
        if not callable(callback):
            raise TypeError("Provided callback is not a function!")

        self.callback = callback
        self.config = config.get('raspberry_pi', {})
        self.debounce_config = config.get('debouncing', {})

        # Map instrument number strings to GPIO pin numbers.
        self.button_pins = self.config.get('button_pins', {})
        self.gpio_pins_to_instruments = {
            pin: int(key) for key, pin in self.button_pins.items()
        }

        # Debouncing timing parameters (all sourced from config).
        self.debounce_time_ms = self.debounce_config.get(
            'debounce_time_ms', 50
        )
        self.min_press_duration_ms = self.debounce_config.get(
            'min_press_duration_ms', 20
        )
        self.poll_interval_ms = self.debounce_config.get(
            'poll_interval_ms', 5
        )
        self.double_press_protection_ms = self.debounce_config.get(
            'double_press_protection_ms', 200
        )

        # Per-pin state tracking dictionaries.
        self.button_states = {}       # Last confirmed stable pin state.
        self.raw_states = {}          # Raw GPIO reading from last poll.
        self.state_change_times = {}  # Timestamp of most recent state edge.
        self.last_trigger_times = {}  # Timestamp of last accepted press.
        self.stable_counters = {}     # Stable-reading counter (unused guard).
        # Non-blocking press-start tracking for min_press_duration check.
        self.press_start_times = {}

        # Polling thread state.
        self.running = False
        self.poll_thread = None

        # Convert milliseconds to seconds for use with time.time().
        self.debounce_time = self.debounce_time_ms / 1000.0
        self.min_press_duration = self.min_press_duration_ms / 1000.0
        self.poll_interval = self.poll_interval_ms / 1000.0
        self.double_press_protection = self.double_press_protection_ms / 1000.0

        try:
            self._setup_gpio()
            logger.info(
                f"GPIO handler successfully set up for "
                f"{len(self.button_pins)} buttons."
            )
            logger.info(
                f"Debouncing config - Time: {self.debounce_time_ms}ms, "
                f"Min press: {self.min_press_duration_ms}ms, "
                f"Poll: {self.poll_interval_ms}ms, "
                f"Double protection: {self.double_press_protection_ms}ms"
            )
        except RuntimeError as e:
            logger.error(f"Critical error during GPIO setup: {e}")
            logger.error(
                "Please ensure the script is running on a Raspberry Pi "
                "with the necessary permissions."
            )
            raise

    def _setup_gpio(self):
        """Configure all GPIO pins and initialize per-pin state tracking."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Select pull resistor direction based on configuration.
        pull_resistor = (
            GPIO.PUD_UP if self.config.get('pull_up', True)
            else GPIO.PUD_DOWN
        )
        expected_idle_state = (
            GPIO.HIGH if self.config.get('pull_up', True)
            else GPIO.LOW
        )

        current_time = time.time()

        for pin in self.button_pins.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=pull_resistor)
            initial_state = GPIO.input(pin)

            # Populate all per-pin tracking dictionaries at startup.
            self.button_states[pin] = initial_state
            self.raw_states[pin] = initial_state
            self.state_change_times[pin] = current_time
            self.last_trigger_times[pin] = 0
            self.stable_counters[pin] = 0
            self.press_start_times[pin] = 0

            logger.debug(
                f"Initialized GPIO {pin} - Initial state: {initial_state}, "
                f"Expected idle: {expected_idle_state}"
            )

    def _is_pressed(self, pin_state):
        """Return whether a raw GPIO state represents a button press.

        With pull-up wiring a press drives the pin LOW; with pull-down
        wiring a press drives the pin HIGH.

        Args:
            pin_state: Raw GPIO value (``GPIO.HIGH`` or ``GPIO.LOW``).

        Returns:
            True if the pin state indicates a button press.
        """
        if self.config.get('pull_up', True):
            return pin_state == GPIO.LOW   # Pull-up: pressed -> LOW
        else:
            return pin_state == GPIO.HIGH  # Pull-down: pressed -> HIGH

    def _debounce_button(self, pin, current_time):
        """Run one debounce evaluation cycle for a single GPIO pin.

        Implements a fully non-blocking state machine so the polling loop
        is never delayed by a ``time.sleep`` call. The minimum press
        duration check is satisfied across successive polling cycles by
        recording the first-detected press time in ``press_start_times``.

        Args:
            pin: GPIO BCM pin number to evaluate.
            current_time: Current monotonic timestamp from the polling loop.

        Returns:
            True if a validated button press event should be dispatched.
        """
        raw_state = GPIO.input(pin)
        previous_raw = self.raw_states[pin]
        current_stable = self.button_states[pin]

        self.raw_states[pin] = raw_state

        # A state transition resets the debounce timer and invalidates any
        # in-progress press tracking.
        if raw_state != previous_raw:
            self.state_change_times[pin] = current_time
            self.stable_counters[pin] = 0
            return False

        # Wait until the signal has been stable for the full debounce window.
        time_since_change = current_time - self.state_change_times[pin]
        if time_since_change < self.debounce_time:
            return False

        # If the stable state matches what we already recorded, nothing changed.
        if raw_state == current_stable:
            self.press_start_times[pin] = 0  # Reset press tracking on release.
            return False

        is_now_pressed = self._is_pressed(raw_state)
        was_pressed = self._is_pressed(current_stable)

        if not was_pressed and is_now_pressed:
            # First cycle after a new press is detected: record the timestamp
            # and defer acceptance until min_press_duration has elapsed.
            if self.press_start_times[pin] == 0:
                self.press_start_times[pin] = current_time
                return False

            # Check that the signal has been pressed long enough to rule out
            # transient glitches (evaluated non-blocking across poll cycles).
            if (current_time - self.press_start_times[pin]
                    < self.min_press_duration):
                return False

            # Reset tracking before updating stable state.
            self.press_start_times[pin] = 0

            # Reject presses that arrive too quickly after the previous one.
            if ((current_time - self.last_trigger_times[pin])
                    < self.double_press_protection):
                logger.debug(
                    f"GPIO {pin}: Double press protection active, ignoring"
                )
                # Update stable state to prevent repeated rejection messages.
                self.button_states[pin] = raw_state
                return False

            # All checks passed -- accept the press.
            self.button_states[pin] = raw_state
            self.last_trigger_times[pin] = current_time
            return True

        # Any other stable-state transition (e.g. release): update state only.
        self.button_states[pin] = raw_state
        self.press_start_times[pin] = 0
        return False

    def _poll_loop(self):
        """Continuously poll all GPIO pins and dispatch validated press events.

        Each validated press spawns a short-lived daemon thread to invoke the
        callback, ensuring the polling loop itself is never blocked by
        upper-layer processing time.
        """
        logger.info(
            f"Starting button polling loop "
            f"(interval: {self.poll_interval_ms}ms)"
        )

        while self.running:
            current_time = time.time()

            for pin, instrument_num in self.gpio_pins_to_instruments.items():
                try:
                    if self._debounce_button(pin, current_time):
                        logger.debug(
                            f"Valid press detected on GPIO {pin} "
                            f"(instrument {instrument_num})"
                        )
                        # Run the callback in its own thread so the poll loop
                        # is not blocked by audio or logic processing.
                        threading.Thread(
                            target=self.callback,
                            args=(instrument_num,),
                            daemon=True
                        ).start()
                except Exception as e:
                    logger.error(f"Error processing GPIO {pin}: {e}")

            time.sleep(self.poll_interval)

    def start(self):
        """Start the GPIO polling thread."""
        if self.running:
            logger.warning("Button handler already running")
            return

        self.running = True
        self.poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True
        )
        self.poll_thread.start()
        logger.info(
            "Button handler is ready and actively listening for buttons."
        )

    def stop(self):
        """Stop the polling thread and release all GPIO resources."""
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
        """Return the current debounce state for all buttons.

        Intended for debugging and diagnostic purposes.

        Returns:
            Dictionary keyed by instrument number with sub-dictionaries
            containing ``'pin'``, ``'stable_state'``, ``'raw_state'``,
            ``'is_pressed'``, and ``'last_trigger'``.
        """
        status = {}
        for pin, instrument_num in self.gpio_pins_to_instruments.items():
            status[instrument_num] = {
                'pin': pin,
                'stable_state': self.button_states.get(pin, 'unknown'),
                'raw_state': self.raw_states.get(pin, 'unknown'),
                'is_pressed': self._is_pressed(
                    self.button_states.get(pin, GPIO.HIGH)
                ),
                'last_trigger': self.last_trigger_times.get(pin, 0)
            }
        return status