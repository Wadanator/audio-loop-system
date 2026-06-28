"""
Waveshare IO 8CH – DI Monitor (Windows)
========================================
Testovací skript pre overenie 8 digitálnych vstupov cez Ethernet (Modbus TCP).
Zobrazuje živý stav všetkých 8 kanálov v termináli.

Požiadavky:
    pip install pymodbus

Použitie:
    python di_monitor.py
    python di_monitor.py --ip 192.168.1.200 --port 502 --slave 1
"""

import time
import sys
import argparse
import os
from datetime import datetime

# ── Konfigurácia (zmeň podľa svojej siete) ─────────────────────────────────
DEFAULT_IP    = "192.168.0.200"
DEFAULT_PORT  = 4196
DEFAULT_SLAVE = 1
POLL_INTERVAL = 0.15   # sekúnd medzi čítaniami
# ───────────────────────────────────────────────────────────────────────────

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    print("\n  CHYBA: pymodbus nie je nainštalovaný.")
    print("  Spusti:  pip install pymodbus\n")
    sys.exit(1)


# ── Windows farby cez ANSI (funguje v Windows Terminal / PowerShell 7+) ────
def enable_ansi():
    """Zapne ANSI escape kódy na Windows."""
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
GRAY   = "\033[90m"
WHITE  = "\033[97m"
BG_GREEN = "\033[42m"
BG_DARK  = "\033[40m"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def draw_header(ip, port, slave):
    print(f"{BOLD}{CYAN}{'═' * 54}{RESET}")
    print(f"{BOLD}{CYAN}  WAVESHARE IO 8CH  –  DI Monitor{RESET}")
    print(f"{CYAN}{'═' * 54}{RESET}")
    print(f"  {GRAY}IP:{RESET} {WHITE}{ip}:{port}{RESET}   "
          f"{GRAY}Slave:{RESET} {WHITE}{slave}{RESET}   "
          f"{GRAY}Interval:{RESET} {WHITE}{int(POLL_INTERVAL*1000)} ms{RESET}")
    print(f"{CYAN}{'─' * 54}{RESET}")


def draw_channels(bits, prev_bits, event_log):
    print(f"\n  {BOLD}{'Kanál':<10} {'Stav':<18} {'Vizuál'}{RESET}")
    print(f"  {'─'*46}")

    for i, bit in enumerate(bits):
        ch = f"DI{i+1}"
        if bit:
            stav_txt = f"{BG_GREEN}{BOLD} STLAČENÉ  {RESET}"
            bar       = f"{GREEN}{'█' * 12}{RESET}"
        else:
            stav_txt = f"{GRAY} voľné     {RESET}"
            bar       = f"{GRAY}{'░' * 12}{RESET}"

        # zvýrazni zmenu
        changed = (prev_bits is not None) and (bit != prev_bits[i])
        marker  = f" {YELLOW}◄ ZMENA{RESET}" if changed else ""

        print(f"  {BOLD}{ch:<10}{RESET}{stav_txt}  {bar}{marker}")

    print(f"\n  {CYAN}{'─' * 54}{RESET}")


def draw_event_log(event_log):
    print(f"  {BOLD}Posledné udalosti:{RESET}")
    if not event_log:
        print(f"  {GRAY}  (žiadna udalosť){RESET}")
    else:
        for entry in event_log[-5:]:  # posledných 5 udalostí
            print(f"  {GRAY}{entry}{RESET}")
    print()


def draw_summary(bits):
    active = [f"DI{i+1}" for i, b in enumerate(bits) if b]
    if active:
        print(f"  {GREEN}Aktívne: {BOLD}{', '.join(active)}{RESET}")
    else:
        print(f"  {GRAY}Žiadny vstup nie je aktívny{RESET}")
    print(f"\n  {GRAY}Ctrl+C = ukončiť{RESET}")
    print(f"{CYAN}{'═' * 54}{RESET}")


def update_event_log(event_log, bits, prev_bits):
    if prev_bits is None:
        return
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    for i in range(8):
        if bits[i] != prev_bits[i]:
            akcia = "STLAČENÉ ▲" if bits[i] else "uvoľnené  ▼"
            event_log.append(f"  [{now}]  DI{i+1}  →  {akcia}")


def try_connect(ip, port):
    client = ModbusTcpClient(ip, port=port, timeout=2)
    connected = client.connect()
    return client if connected else None


def main():
    parser = argparse.ArgumentParser(description="Waveshare IO 8CH – DI Monitor")
    parser.add_argument("--ip",    default=DEFAULT_IP,    help="IP adresa prevodníka")
    parser.add_argument("--port",  default=DEFAULT_PORT,  type=int, help="TCP port (default 502)")
    parser.add_argument("--slave", default=DEFAULT_SLAVE, type=int, help="Modbus slave adresa modulu")
    args = parser.parse_args()

    enable_ansi()
    clear_screen()

    print(f"\n{CYAN}  Pripájam sa na {args.ip}:{args.port} (slave={args.slave})...{RESET}\n")

    client = try_connect(args.ip, args.port)
    if not client:
        print(f"{RED}  CHYBA: Nedá sa pripojiť na {args.ip}:{args.port}{RESET}")
        print(f"  Skontroluj:")
        print(f"    1. IP adresu prevodníka")
        print(f"    2. Či je prevodník v režime  Modbus TCP ↔ RTU")
        print(f"    3. Firewall – vypni ho alebo pridaj výnimku pre port {args.port}")
        sys.exit(1)

    print(f"{GREEN}  Pripojené!{RESET}")
    time.sleep(0.5)

    # pymodbus 3.13+ používa device_id=
    read_kwargs = {"device_id": args.slave}

    prev_bits  = None
    event_log  = []
    error_count = 0

    try:
        while True:
            result = client.read_discrete_inputs(address=0, count=8, **read_kwargs)

            if result.isError():
                error_count += 1
                if error_count > 5:
                    # pokús sa znova pripojiť
                    client.close()
                    client = try_connect(args.ip, args.port)
                    error_count = 0
                time.sleep(0.5)
                continue

            error_count = 0
            bits = list(result.bits[:8])

            update_event_log(event_log, bits, prev_bits)

            clear_screen()
            draw_header(args.ip, args.port, args.slave)
            draw_channels(bits, prev_bits, event_log)
            draw_event_log(event_log)
            draw_summary(bits)

            prev_bits = bits
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        clear_screen()
        print(f"\n{YELLOW}  Monitor ukončený.{RESET}\n")
    finally:
        client.close()


if __name__ == "__main__":
    main()