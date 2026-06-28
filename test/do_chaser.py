"""
Waveshare IO 8CH - DO chaser test
=================================

Test script for checking all 8 digital outputs over Ethernet / Modbus TCP.
It turns outputs on one by one (DO1 -> DO8) like a small LED "snake".

Requirements:
    pip install pymodbus

Usage:
    python test/do_chaser.py
    python test/do_chaser.py --ip 192.168.0.200 --port 4196 --slave 1
    python test/do_chaser.py --delay 0.5 --cycles 5
"""

import argparse
import sys
import time


DEFAULT_IP = "192.168.0.200"
DEFAULT_PORT = 4196
DEFAULT_SLAVE = 1
DEFAULT_DELAY = 0.5


try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    print("\nERROR: pymodbus is not installed.")
    print("Run:  pip install pymodbus\n")
    sys.exit(1)


def write_coil(client, address, value, slave):
    """Write one coil, supporting current and older pymodbus keyword names."""
    try:
        return client.write_coil(address=address, value=value, device_id=slave)
    except TypeError:
        return client.write_coil(address=address, value=value, slave=slave)


def set_output(client, channel, state, slave):
    """Set DO channel 1-8 to on/off."""
    result = write_coil(client, channel - 1, state, slave)
    if result.isError():
        raise RuntimeError(
            f"DO{channel} write failed (state={int(state)}): {result}"
        )


def all_outputs_off(client, slave):
    """Best-effort clear of all eight outputs."""
    for channel in range(1, 9):
        try:
            set_output(client, channel, False, slave)
        except Exception as exc:
            print(f"WARNING: failed to turn DO{channel} off: {exc}")


def run_chaser(client, slave, delay, cycles):
    """Run one-at-a-time DO1 -> DO8 output chase."""
    cycle = 0
    while cycles == 0 or cycle < cycles:
        cycle += 1
        label = f"cycle {cycle}" if cycles else f"cycle {cycle} (infinite)"
        print(f"\nStarting {label}")

        for channel in range(1, 9):
            all_outputs_off(client, slave)
            print(f"  DO{channel} ON")
            set_output(client, channel, True, slave)
            time.sleep(delay)

        all_outputs_off(client, slave)


def main():
    parser = argparse.ArgumentParser(
        description="Waveshare IO 8CH DO chaser / LED output test"
    )
    parser.add_argument("--ip", default=DEFAULT_IP, help="Ethernet module IP")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    parser.add_argument("--slave", default=DEFAULT_SLAVE, type=int)
    parser.add_argument(
        "--delay",
        default=DEFAULT_DELAY,
        type=float,
        help="Seconds each output stays on",
    )
    parser.add_argument(
        "--cycles",
        default=3,
        type=int,
        help="Number of DO1-DO8 cycles. Use 0 for infinite.",
    )
    args = parser.parse_args()

    print(f"Connecting to {args.ip}:{args.port} (slave/device_id={args.slave})")
    client = ModbusTcpClient(args.ip, port=args.port, timeout=2)
    if not client.connect():
        raise SystemExit(f"Cannot connect to {args.ip}:{args.port}")

    try:
        print("Connected. Clearing outputs...")
        all_outputs_off(client, args.slave)
        run_chaser(client, args.slave, args.delay, args.cycles)
        print("\nDone. All outputs are off.")
    except KeyboardInterrupt:
        print("\nInterrupted. Turning all outputs off...")
    finally:
        all_outputs_off(client, args.slave)
        client.close()


if __name__ == "__main__":
    main()
