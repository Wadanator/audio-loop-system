# button_handler.py
import logging
import RPi.GPIO as GPIO
import threading
import time

logger = logging.getLogger(__name__)

class UniversalButtonHandler:
    """
    A reliable handler for GPIO buttons with pull-up resistors using polling.
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
        self.button_pins = self.config.get('button_pins', {})
        self.gpio_pins_to_instruments = {pin: int(key) for key, pin in self.button_pins.items()}
        
        self.last_states = {}
        self.running = False
        self.poll_thread = None

        try:
            self._setup_gpio()
            logger.info(f"GPIO handler successfully set up for {len(self.button_pins)} buttons.")
        except RuntimeError as e:
            logger.error(f"Critical error during GPIO setup: {e}")
            logger.error("Please ensure the script is running on a Raspberry Pi with the necessary permissions.")
            raise

    def _setup_gpio(self):
        """Initializes GPIO pins and their initial state."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        pull_resistor = GPIO.PUD_UP if self.config.get('pull_up', True) else GPIO.PUD_DOWN
        
        for pin in self.button_pins.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=pull_resistor)
            self.last_states[pin] = GPIO.input(pin)

    def _poll_loop(self):
        """Main loop that continuously checks pin states."""
        while self.running:
            for pin, instrument_num in self.gpio_pins_to_instruments.items():
                current_state = GPIO.input(pin)
                # Detect falling edge (from HIGH to LOW)
                if self.last_states[pin] == GPIO.HIGH and current_state == GPIO.LOW:
                    logger.debug(f"Valid press registered on GPIO {pin} (instrument {instrument_num}).")
                    self.callback(instrument_num)
                
                # Save the current state for the next iteration
                self.last_states[pin] = current_state
            
            time.sleep(0.01)

    def start(self):
        """Starts the polling in a separate thread."""
        if self.running:
            return
        self.running = True
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        logger.info("Button handler is ready and actively listening for buttons.")

    def stop(self):
        """Safely stops the thread and cleans up GPIO."""
        if not self.running:
            return
        self.running = False
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=1.0)
        GPIO.cleanup()
        logger.info("Button handler stopped and GPIO cleaned up.")