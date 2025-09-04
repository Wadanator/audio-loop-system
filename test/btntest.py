# btntest_curses_counter.py
import RPi.GPIO as GPIO
import time
import curses

# tvoje piny zo súboru config.json
pins = {
    "1": 4,
    "2": 17,
    "3": 27,
    "4": 22,
    "5": 5,
    "6": 6,
    "7": 13,
    "8": 19,
    "9": 26,
    "10": 18,
    "11": 23,
    "12": 24,
    "13": 25,
    "14": 12,
    "15": 16,
    "16": 20,
    "17": 21,
    "18": 1
}

# --- nastavenie GPIO ---
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for name, pin in pins.items():
    try:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    except Exception as e:
        print(f"⚠️ Pin {pin} ({name}) sa nepodarilo nastaviť: {e}")

# počítadlá stlačení
press_counts = {name: 0 for name in pins}

# posledný stav pinov (na detekciu hrany)
last_states = {name: GPIO.input(pin) for name, pin in pins.items()}

# --- hlavná funkcia curses ---
def main(stdscr):
    curses.curs_set(0)  # skryť kurzor
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)   # L = červené
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK) # H = zelené
    stdscr.nodelay(True)

    while True:
        max_y, max_x = stdscr.getmaxyx()
        row = 2

        for name, pin in pins.items():
            if row + 1 >= max_y:
                break  # nepíš mimo okna

            state = GPIO.input(pin)

            # detekcia stlačenia (HIGH → LOW)
            if last_states[name] == 1 and state == 0:
                press_counts[name] += 1
            last_states[name] = state

            status = "L" if state == 0 else "H"
            text = f"Tlačidlo {name} (GPIO {pin}): "
            text = text[:max_x-2]  # orez, aby sa zmestilo
            stdscr.addstr(row, 0, text)
            if len(text) < max_x:
                stdscr.addstr(row, len(text), status, curses.color_pair(1) if state == 0 else curses.color_pair(2))

            # vypíš počet stlačení pod tlačidlo
            row += 1
            count_text = f"  Počet stlačení: {press_counts[name]}"
            count_text = count_text[:max_x-1]
            stdscr.addstr(row, 0, count_text)

            row += 1  # ďalšie tlačidlo

        stdscr.refresh()
        time.sleep(0.1)

# --- spustenie ---
try:
    curses.wrapper(main)
except KeyboardInterrupt:
    print("\nKoniec testu.")
finally:
    GPIO.cleanup()
