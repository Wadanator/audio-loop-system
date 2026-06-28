# Pre-step - Modbus/RS485 bring-up before audio system

## Goal

Before connecting the DIN button panel to the audio app, prove that each
Waveshare IO module, its RS485 wiring to its own Ethernet module, Modbus
addressing, one button input, and one LED output work in isolation - and that
the two boxes do not interfere with each other once both are running.

This step intentionally does not import or run the audio system. It uses only
small test scripts.

## Current hardware status

As of the current bench test, one Waveshare IO 8CH module is already working
through `test/di_monitor.py`:

- current tested IP: `192.168.0.200`
- current tested TCP port: `4196`
- current tested Modbus device/slave id: `1`
- confirmed behavior: reading all 8 DI channels works and button state changes
  are visible in the terminal
- current script style: `pymodbus.client.ModbusTcpClient` with
  `read_discrete_inputs(address=0, count=8, device_id=slave)`

That working script is now the reference for the first implementation step:
register DI state changes first, without audio, GPIO, LED logic, or web UI.

## DI event registration pattern from `di_monitor.py`

The production input handler should reuse the same basic idea, minus the
terminal drawing code:

```python
prev_bits = None

while running:
    result = client.read_discrete_inputs(address=0, count=8, device_id=unit_id)
    bits = list(result.bits[:8])

    if prev_bits is not None:
        for index, (current, previous) in enumerate(zip(bits, prev_bits), start=1):
            if current and not previous:
                on_press(channel=index)

    prev_bits = bits
    time.sleep(poll_interval)
```

Important implementation detail: the monitor prints every change, but the audio
system should trigger only on the rising edge (`False -> True`) so one physical
press becomes one `handle_button_press(...)` call.

## Topology reminder

Box 1 and Box 2 are fully independent: each box has its own Ethernet-to-RS485
module with its own IP address, wired internally to its own Waveshare IO
module. There is **no RS485 cable between the two boxes**. Both IO modules
stay on their factory Modbus address `0x01` - they are told apart by IP, not
by unit ID. The Raspberry Pi therefore opens two separate Modbus TCP
connections, one per box.

## Test order

1. One IO box only (Box 1)
   - power the box
   - confirm Modbus TCP communication through Box 1's own Ethernet module at
     its own IP
   - read DI1
   - write DO1 / LED1
   - run the DO1 -> DO8 output chaser with `test/do_chaser.py`
   - connect one physical button and verify press/release

2. Second IO box independently (Box 2)
   - repeat exactly the same steps using Box 2's own IP address
   - confirm it also responds as unit `0x01` (same Modbus address as Box 1 -
     this is expected and correct, since the boxes are distinguished by IP)
   - read DI from Box 2
   - blink one LED on Box 2
   - ideally test Box 2 with Box 1 powered off, to rule out any network/IP
     conflict

3. Both boxes running concurrently
   - power both boxes
   - confirm one Python process can hold two independent TCP connections (one
     per IP) at the same time without errors
   - read DI from both boxes in the same polling loop
   - blink one LED on each box, one after another
   - verify that pressing a button on Box 1 does not change Box 2's readings,
     and vice versa

4. Only after this passes, continue to `01_DIN_MODBUS_BUTTONS.md`.

## Minimal bench wiring - one box, one button

Use a 12V DC PSU for the Waveshare IO module and button LED. For this bench
smoke test, do not wire the 230V DIN power side. Keep the first test low-voltage
only: PSU 12V DC, the box's own Ethernet-to-RS485 module, its IO module, and
one button. Repeat the identical setup for the second box later, using that
box's own PSU, Ethernet module, and IP address - the two boxes are never wired
to each other.

### Power

| From | To |
| --- | --- |
| PSU +12V | IO module `7~36V` |
| PSU GND | IO module `GND` |
| PSU GND | IO module `DGND` |
| PSU GND | IO module `DI COM` |
| PSU +12V | IO module `DO COM` |

### Ethernet-to-RS485 module to IO module (internal to this one box)

| Ethernet-to-RS485 module | IO module |
| --- | --- |
| `485 A+` | `485 A+` |
| `485 B-` | `485 B-` |
| `GND` | PSU GND / IO `GND` |

This wiring stays entirely inside one box. Do not run any RS485 wire to the
other box - each box's Ethernet module only ever talks to the IO module sitting
next to it in the same enclosure.

### One button on channel 1

Use the same button wiring concept as the DIN guide:

| Button side | Connect to |
| --- | --- |
| Button `COM` | +12V common node |
| Button `LED+` | +12V common node |
| Button `NO` | IO module `DI1` |
| Button `LED-` | IO module `DO1` |

The +12V common node can be a small WAGO or temporary bench jumper from PSU
`+12V`. The important part is:

- pressing the button sends +12V into `DI1`
- writing DO1 controls the LED/backlight path

## Python dependency

Use `pymodbus` for the final topology because each Ethernet module exposes its
own RS485 bus through Modbus TCP.

```bash
pip install pymodbus
```

## Script 1 - one box smoke test

Create `scripts/modbus_smoke_one_module.py`.

```python
#!/usr/bin/env python3
import argparse
import time
from pymodbus.client import ModbusTcpClient


def read_inputs(client, unit):
    result = client.read_discrete_inputs(0, count=8, device_id=unit)
    if result.isError():
        raise RuntimeError(f"DI read failed for unit {unit}: {result}")
    return [bool(x) for x in result.bits[:8]]


def set_led(client, unit, channel, state):
    result = client.write_coil(channel - 1, state, device_id=unit)
    if result.isError():
        raise RuntimeError(
            f"DO write failed for unit {unit}, channel {channel}: {result}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.0.200", help="This box's own IP")
    parser.add_argument("--port", type=int, default=4196)
    parser.add_argument("--unit", type=int, default=1)
    parser.add_argument("--channel", type=int, default=1)
    parser.add_argument("--watch-seconds", type=int, default=20)
    args = parser.parse_args()

    client = ModbusTcpClient(args.host, port=args.port, timeout=1)
    if not client.connect():
        raise SystemExit(f"Cannot connect to {args.host}:{args.port}")

    try:
        print(f"Connected to {args.host}:{args.port}, unit {args.unit}")

        inputs = read_inputs(client, args.unit)
        print("Initial DI:", [int(x) for x in inputs])

        print(f"Blinking DO{args.channel}...")
        set_led(client, args.unit, args.channel, True)
        time.sleep(0.5)
        set_led(client, args.unit, args.channel, False)
        time.sleep(0.5)
        set_led(client, args.unit, args.channel, True)
        time.sleep(0.5)
        set_led(client, args.unit, args.channel, False)
        print("LED blink done.")

        print(
            f"Watching DI{args.channel} for {args.watch_seconds}s. "
            "Press and release the button now."
        )
        end_at = time.time() + args.watch_seconds
        last = None
        while time.time() < end_at:
            inputs = read_inputs(client, args.unit)
            current = inputs[args.channel - 1]
            if current != last:
                print(f"DI{args.channel} = {int(current)}")
                last = current
            time.sleep(0.1)

    finally:
        try:
            set_led(client, args.unit, args.channel, False)
        finally:
            client.close()


if __name__ == "__main__":
    main()
```

Run against Box 1:

```bash
python scripts/modbus_smoke_one_module.py --host 192.168.0.200 --unit 1 --channel 1
```

Run the same script against Box 2 later, just by pointing `--host` at Box 2's
own IP (e.g. `192.168.0.201`) - `--unit` stays `1` since both boxes use the
factory address.

Expected:

- script connects to the box's own IP
- initial DI values print
- LED on channel 1 blinks
- pressing the button changes `DI1` from `0` to `1`
- releasing the button changes it back to `0`

If the value is inverted, note it in the wiring/config before continuing.

## Script 2 - watch all inputs on one box

Create `scripts/modbus_watch_inputs.py`.

```python
#!/usr/bin/env python3
import argparse
import time
from pymodbus.client import ModbusTcpClient


def read_inputs(client, unit):
    result = client.read_discrete_inputs(0, count=8, device_id=unit)
    if result.isError():
        raise RuntimeError(f"DI read failed for unit {unit}: {result}")
    return [bool(x) for x in result.bits[:8]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.0.200", help="This box's own IP")
    parser.add_argument("--port", type=int, default=4196)
    parser.add_argument("--unit", type=int, default=1)
    parser.add_argument("--interval", type=float, default=0.1)
    args = parser.parse_args()

    client = ModbusTcpClient(args.host, port=args.port, timeout=1)
    if not client.connect():
        raise SystemExit(f"Cannot connect to {args.host}:{args.port}")

    print(f"Watching {args.host}, unit {args.unit}. Press Ctrl+C to stop.")
    last = None
    try:
        while True:
            values = read_inputs(client, args.unit)
            if values != last:
                print([int(x) for x in values])
                last = values
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
```

Run:

```bash
python scripts/modbus_watch_inputs.py --host 192.168.0.200 --unit 1
```

Use this after adding more temporary buttons to one box.

## Script 3 - output chaser for all 8 DO channels

Actual file: `test/do_chaser.py`.

This tests the output side independently from the audio system. It turns on only
one output at a time, from DO1 to DO8, with a delay between steps. This is the
same output path that will later drive the button LEDs to show which audio track
is really active.

Run against the currently working Box 1:

```bash
python test/do_chaser.py --ip 192.168.0.200 --port 4196 --slave 1 --delay 0.5 --cycles 3
```

Expected:

- all outputs are turned off at startup
- DO1 turns on for 0.5s, then DO2, then DO3, up to DO8
- only one LED/output is on at a time
- after the script finishes or Ctrl+C is pressed, all outputs are turned off

Use `--cycles 0` for an infinite chaser while checking wiring:

```bash
python test/do_chaser.py --cycles 0
```

If some LED does not match the expected channel, fix the wiring/mapping before
integrating LED state into the audio app.

## Script 4 - two independent boxes smoke test

Create `scripts/modbus_smoke_two_modules.py`. This connects to **two separate
IPs**, not to two unit IDs on a shared bus.

```python
#!/usr/bin/env python3
import argparse
import time
from pymodbus.client import ModbusTcpClient


def read_inputs(client, unit):
    result = client.read_discrete_inputs(0, count=8, device_id=unit)
    if result.isError():
        raise RuntimeError(f"DI read failed for unit {unit}: {result}")
    return [bool(x) for x in result.bits[:8]]


def set_led(client, unit, channel, state):
    result = client.write_coil(channel - 1, state, device_id=unit)
    if result.isError():
        raise RuntimeError(
            f"DO write failed for unit {unit}, channel {channel}: {result}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-a", default="192.168.0.200", help="Box 1 IP")
    parser.add_argument("--host-b", default="192.168.0.201", help="Box 2 IP")
    parser.add_argument("--port", type=int, default=4196)
    parser.add_argument("--unit", type=int, default=1, help="Same on both boxes")
    args = parser.parse_args()

    client_a = ModbusTcpClient(args.host_a, port=args.port, timeout=1)
    client_b = ModbusTcpClient(args.host_b, port=args.port, timeout=1)

    if not client_a.connect():
        client_a.close()
        client_b.close()
        raise SystemExit(f"Cannot connect to Box 1 at {args.host_a}:{args.port}")
    if not client_b.connect():
        client_a.close()
        client_b.close()
        raise SystemExit(f"Cannot connect to Box 2 at {args.host_b}:{args.port}")

    boxes = {"Box 1": client_a, "Box 2": client_b}
    try:
        for name, client in boxes.items():
            print(f"{name} DI:", [int(x) for x in read_inputs(client, args.unit)])

        for name, client in boxes.items():
            print(f"Blinking {name}, DO1")
            set_led(client, args.unit, 1, True)
            time.sleep(0.5)
            set_led(client, args.unit, 1, False)

        print("Watching both boxes for 20s.")
        last = {}
        end_at = time.time() + 20
        while time.time() < end_at:
            for name, client in boxes.items():
                values = read_inputs(client, args.unit)
                if values != last.get(name):
                    print(f"{name} DI:", [int(x) for x in values])
                    last[name] = values
            time.sleep(0.1)
    finally:
        for client in boxes.values():
            try:
                set_led(client, args.unit, 1, False)
            except Exception:
                pass
            client.close()


if __name__ == "__main__":
    main()
```

Run:

```bash
python scripts/modbus_smoke_two_modules.py --host-a 192.168.0.200 --host-b 192.168.0.201
```

Expected:

- Box 1 responds at its own IP
- Box 2 responds at its own IP, also as unit `0x01`
- DO1 blinks on both boxes, one after the other
- pressing a button wired to Box 1 changes only Box 1's DI values
- pressing a button wired to Box 2 changes only Box 2's DI values
- disconnecting or powering off one box does not break Modbus communication
  with the other box

## Common failure checklist

- No TCP connection to a box:
  - check that box's own IP address
  - check RPi/PC is on the same network as that box
  - check the box's Ethernet module port is `4196` for the current tested setup

- TCP connects, but Modbus read/write times out:
  - check A/B polarity between that box's Ethernet-to-RS485 module and IO module
  - check the IO module has 12V power and common GND with the Ethernet module
  - check the Ethernet module is in Modbus TCP to RTU mode, not raw TCP mode
  - check serial settings on the bridge match the IO module
  - check the Modbus device id is `1`
  - try with and without the RS485 terminator if the bench wiring is very short

- Box 1 works, Box 2 does not:
  - confirm Box 2's Ethernet module is configured with its own, correct IP
    address (not a duplicate of Box 1's)
  - test Box 2 completely on its own, with Box 1 powered off, to rule out an
    IP/network conflict
  - within Box 2 only, check A/B polarity and RS485 continuity between its
    own Ethernet module and its own IO module - this wiring is internal to
    the box and never involves Box 1

- DI never changes:
  - check `DI COM` is connected to GND
  - check `DGND` is connected to GND
  - check button `NO` goes to `DI1`
  - check button common node is +12V

- LED never turns on:
  - check `DO COM` is connected according to the module wiring guide
  - check button `LED+` is on +12V common node
  - check button `LED-` goes to `DO1`
  - check LED polarity

- Values are inverted:
  - document it before implementation
  - handle inversion in config rather than changing core audio logic

## Acceptance criteria

- Box 1 responds through Modbus TCP at its own IP.
- Box 2 responds through Modbus TCP at its own IP, independently of Box 1.
- One physical button press per box is visible in DI reads.
- One LED/backlight can be controlled through DO writes, on each box.
- All 8 DO outputs on the working module pass the `test/do_chaser.py` sequence.
- Both boxes can be read and written concurrently from one Python process
  without interference, confirming the two-independent-endpoints topology.
- No audio-system code is required for these tests.
