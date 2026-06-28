# Goal 1 - DIN Modbus buttons and LED panel

## Goal

Replace the production use of direct Raspberry Pi GPIO buttons with the DIN box
button system from the hardware guide. The DIN buttons must trigger the same
audio logic as today, and the DIN button backlights must show which audio layers
are active.

Prerequisite: complete `00A_MODBUS_BRINGUP.md` first. Do not start integrating
DIN buttons into the audio app until the currently working box can be read by a
small input adapter outside the audio system.

First implementation milestone: remove the production dependency on RPi GPIO
completely, then make the app react to the already-working Box 1 DI monitor
pattern. This gives a Windows/RPi-compatible path with 8 physical inputs before
adding Box 2 and the full 16-input panel.

## Current state

- `button_handler.py` imports `RPi.GPIO` directly.
- `main.py` always creates `UniversalButtonHandler`.
- `test/di_monitor.py` already proves that the first external IO module can be
  read over Modbus TCP on Windows, without RPi GPIO.
- `LooperEngine.handle_button_press(instrument_num)` is already the correct
  shared entry point for any input source.
- `LooperEngine.instrument_active` already tracks active layers.
- `stats_server.py` is only a stats page and has no remote control API.

## Hardware target

From `navod.md` (V11):

- Box 1: Waveshare IO 8CH module + its own Ethernet-to-RS485 module, own IP
  (e.g. `192.168.0.200`), Modbus unit `0x01`
- Box 2: Waveshare IO 8CH module + its own Ethernet-to-RS485 module, own IP
  (e.g. `192.168.0.201`), Modbus unit `0x01`
- Box 1 and Box 2 are fully independent Modbus TCP endpoints - there is no
  RS485 wiring between them, and both IO modules stay on the same factory
  Modbus address. They are told apart by IP, not by unit ID.
- The RPi talks to each box's Ethernet module directly over its own IP, not
  to GPIO pins.
- Each box has 8 DI channels for button presses and 8 DO channels for LEDs.

Default mapping:

| Audio layer | Box | Channel |
| --- | --- | --- |
| 1-8 | Box 1 (IP `.200`), unit `0x01` | DI/DO 1-8 |
| 9-16 | Box 2 (IP `.201`), unit `0x01` | DI/DO 1-8 |
| 17-18 | none by default | web-only or future hardware |

## Implementation rollout

- Phase A: remove GPIO from the production startup path and support one
  configured Modbus module (`box_1`) with 8 physical inputs.
- Phase B: add `box_2` to config for inputs 9-16 once the second module is
  wired and passes the same monitor/smoke tests.
- Phase C: enable LED feedback and web remote press on top of the same mapping.

## New config shape

Add a new section to `config.json`. Each module gets its own `host` because
each box has its own Ethernet module and IP - `unit_id` is `1` for every
module since the boxes are distinguished by IP, not by Modbus address:

```json
{
  "inputs": {
    "provider": "modbus_panel",
    "enable_legacy_gpio": false
  },
  "modbus_panel": {
    "enabled": true,
    "port": 4196,
    "poll_interval_ms": 75,
    "debounce_time_ms": 80,
    "min_press_duration_ms": 10,
    "double_press_protection_ms": 250,
    "modules": [
      {
        "name": "box_1",
        "host": "192.168.0.200",
        "unit_id": 1,
        "channels": [
          {"channel": 1, "instrument": 1},
          {"channel": 2, "instrument": 2},
          {"channel": 3, "instrument": 3},
          {"channel": 4, "instrument": 4},
          {"channel": 5, "instrument": 5},
          {"channel": 6, "instrument": 6},
          {"channel": 7, "instrument": 7},
          {"channel": 8, "instrument": 8}
        ]
      },
      {
        "name": "box_2",
        "host": "192.168.0.201",
        "unit_id": 1,
        "channels": [
          {"channel": 1, "instrument": 9},
          {"channel": 2, "instrument": 10},
          {"channel": 3, "instrument": 11},
          {"channel": 4, "instrument": 12},
          {"channel": 5, "instrument": 13},
          {"channel": 6, "instrument": 14},
          {"channel": 7, "instrument": 15},
          {"channel": 8, "instrument": 16}
        ]
      }
    ]
  }
}
```

`port` at the top level is the currently tested Modbus TCP port (`4196`) used
by the working `di_monitor.py` setup. Add an optional `port` field on an
individual module only if a later box is configured differently.

For Phase A, it is valid to keep only the `box_1` entry in `modules`. The code
must not require `box_2` to exist before the first 8-button version works.

Keep old `raspberry_pi.button_pins` only as temporary legacy/dev config until
the refactor is complete. It must not be the production default.

## Polling and debounce policy

Start conservatively on real DIN hardware:

- `poll_interval_ms`: begin at 75 ms, acceptable starting range 50-100 ms.
- Measure each box's Ethernet-to-RS485 module latency before lowering below
  50 ms.
- `double_press_protection_ms` is per physical channel, never global.
- A press on button 1 must not delay or block button 2, even when they live
  on different boxes.
- Because Box 1 and Box 2 are independent TCP connections, polling one box
  must not block polling the other. Poll each module's connection on its own
  schedule (e.g. sequentially within one loop, or one lightweight worker per
  module) so a slow or unreachable box does not delay reads from the other.
- Keep the engine-level cooldown per instrument only, and tune it together
  with the input debounce so the same layer cannot chatter but different layers
  can still be activated quickly.

## Shared Modbus bus policy

Input polling and LED writes should not each create their own unsynchronised
`pymodbus` client against a box's bridge. Use one shared `ModbusBus` or
`ModbusPanelService` that owns **one TCP client per configured module** (one
per box IP), each with its own reconnect logic, and a lock or command queue
per client. The input handler and LED controller call into this shared layer
by module name or instrument number, and the bus service routes the call to
the correct underlying client.

This keeps reads/writes serialized per box, makes reconnect behavior
consistent, and avoids thread-safety bugs when a physical press and a LED
update happen at the same time - while also making sure one box's connection
problems cannot stall the other box's traffic.

## Implementation steps

1. Add dependency
   - Add `pymodbus` to `requirements.txt`.
   - Keep `minimalmodbus` only for one-off module address verification scripts
     (bench-side, before mounting - see `navod.md` Phase 1) if needed.

2. Create shared Modbus bus service
   - New module: `hardware/modbus_bus.py`.
   - Own one `pymodbus.client.ModbusTcpClient` instance per configured module
     (one per box IP) - not a single client shared across boxes.
   - Provide synchronized methods for:
     - reading DI channels for a given module
     - writing LED coils for a given module
     - reconnecting a given module's client with backoff, independently of
       the other module
     - exposing per-module connection health
   - Use a lock (or single worker queue) per client so concurrent reads/writes
     on the same box's connection cannot race. Independent boxes must be able
     to be polled without blocking each other.

3. Create input/output abstraction
   - Add `input/base.py` with a small interface:
     - `start()`
     - `stop()`
     - input source calls `on_press(instrument_num)`
   - Add `output/base.py` or a simple `LedController` interface:
     - `set_layer_active(instrument_num, active)`
     - `set_all(active)`
     - `sync_from_active_layers(active_layers)`

4. Implement Modbus panel client
   - New module: `input/modbus_panel.py`
   - Start from the proven `test/di_monitor.py` behavior: read 8 DI bits,
     remember the previous state, and emit a press only on `False -> True`.
   - Use the shared Modbus bus service, not a raw client.
   - For each configured module, connect to its own `host:port` and read 8
     discrete inputs from its `unit_id` (default `1`).
   - Treat a read as valid only when the result exists, `isError()` is false,
     `bits` exists, and at least 8 bits are present. Catch connection drops,
     `AttributeError`, and Modbus exceptions so a bad read cannot crash the
     polling thread.
   - Translate `(module_name, channel)` into `instrument_num` using the
     `channels` mapping for that module - `unit_id` is not the distinguishing
     key here, since both boxes use the same one.
   - Apply the existing debounce rules from `button_handler.py`.
   - On valid rising edge, call `LooperEngine.handle_button_press`.
   - Keep one debounce/double-press state per configured channel.
   - Add connection state and reconnect support, per module independently:
     - first retry after 2 seconds
     - then 5 seconds
     - after 5 consecutive failures, retry every 30 seconds
     - rate-limit repeated log warnings to roughly once per minute
   - One module being unreachable must not stop polling or pressing through
     the other module.

5. Implement LED control
   - New module: `output/led_panel.py`
   - Use the shared Modbus bus service for all coil writes, addressed to the
     correct module's client.
   - Treat LEDs as real state indicators, not decorative feedback: a lit LED
     means the corresponding audio layer is currently playing/active.
   - Use `test/do_chaser.py` before integration to confirm DO1-DO8 mapping.
   - Write DO coils for LED state:
     - active layer -> LED on
     - inactive layer -> LED off
   - Add safe startup behavior:
     - on startup, turn all configured LEDs off, on every module
     - on shutdown, try to turn all configured LEDs off, on every module
     - on Modbus communication error for one module, log warning and continue
       audio logic and the other module's LED writes

6. Wire LEDs into `LooperEngine`
   - Inject optional `led_controller` into `LooperEngine`.
   - `_activate_instrument(n)` calls `set_layer_active(n, True)`.
   - `_deactivate_instrument(n)` calls `set_layer_active(n, False)`.
   - `_deactivate_system()` calls `sync_from_active_layers([])` or `set_all(False)`.
   - LED errors must never prevent audio state changes.

7. Wire production startup in `main.py`
   - Load config.
   - If `inputs.provider == "modbus_panel"`, create one shared Modbus bus
     service that opens a TCP client per configured module (Box 1 at its IP,
     Box 2 at its IP), then create the Modbus input handler and LED controller
     from that bus.
   - Create `LooperEngine(audio_manager, config, stats_collector,
     led_controller=led_controller)`.
   - Start the Modbus input handler instead of `UniversalButtonHandler`.
   - Do not import `RPi.GPIO` when using Modbus provider.

8. Keep a development fallback
   - Move GPIO handler to `input/gpio_legacy.py`.
   - Enable it only if config explicitly says `provider: "gpio_legacy"`.
   - This keeps old bench testing possible, but production no longer depends
     on direct RPi buttons.

9. Add verification script
   - New script: `scripts/verify_modbus_panel.py`
   - Connects to each configured module's IP independently.
   - Reads DI state per module.
   - Blinks each configured LED once, module by module.
   - Prints mapping: instrument -> module name (IP) / channel.

## Acceptance criteria

- Starting the app with `provider: "modbus_panel"` does not import `RPi.GPIO`,
  so the non-GPIO path can run on Windows and Raspberry Pi.
- Phase A works with only `box_1` configured and only 8 physical inputs.
- Pressing DIN button 1 (Box 1) calls `handle_button_press(1)`.
- Pressing DIN button 9 (Box 2) calls `handle_button_press(9)`.
- Remote or physical activation of layer 3 turns LED 3 on, because that audio
  layer is actually active.
- Timeout or manual deactivation of layer 3 turns LED 3 off.
- Global timeout turns all DIN LEDs off, on both boxes.
- If a Modbus LED write fails on one box, audio still plays, the other box's
  LEDs are unaffected, and the error is logged.
- Input polling and LED writes for each box go through one synchronized
  Modbus bus layer, with its own client per box IP.
- If Box 1 is unreachable, Box 2's buttons and LEDs keep working normally,
  and vice versa.
- A dropped connection or malformed Modbus result is logged and retried; it
  does not crash the input polling thread.
- If web is disabled, physical DIN buttons still control audio.

## Risks and notes

- Confirm the Waveshare register map against the exact module revision before
  final implementation. **Confirmed by `navod.md` (V11):** DI at `0x0000`
  (FC02, `read_discrete_inputs`) and DO coils at `0x0000` (FC01/05/0F,
  `read_coils`/`write_coil`/`write_coils`).
- **Resolved:** each box has its own Ethernet-to-RS485 module and its own IP.
  Both Waveshare IO modules stay on Modbus unit `0x01` (factory default) and
  are distinguished by IP, not by unit ID. There is no shared RS485 bus
  between boxes, so the panel needs two independent Modbus TCP endpoints
  rather than one endpoint addressing two unit IDs.
- Do not share a raw `pymodbus` client across threads, and never share one
  client across both boxes. Use the shared bus layer as the only owner of
  client objects, with one client per box.
- Keep the polling interval conservative at first. Start with 50-100 ms, then
  tune after hardware tests, and measure each box's latency independently.
