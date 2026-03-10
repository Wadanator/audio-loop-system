# TODO: RS485 Modbus Button Bus Migration

## Goal

Replace direct GPIO wiring with an RS485 (Modbus RTU) bus.
15 backlit anti-vandal buttons connected via 2× Waveshare 8DI/8DO modules.

**LED behaviour:**
- 💡 **ON** — while the instrument is actively playing
- ⚫ **OFF** — when nothing is happening (idle, timeout, system inactive)

---

## Hardware (assumed, from wiring document)

| Component | Qty | Notes |
|-----------|-----|-------|
| Backlit anti-vandal button (momentary, IP65, 12/24V LED) | 15 | COM+NO for input, LED+/LED- for output |
| Waveshare 8DI/8DO RS485 Modbus RTU module | 2 | Module ID 1 → buttons 1–8, Module ID 2 → buttons 9–15 |
| USB→RS485 converter (FT232 chip) | 1 | Appears as `/dev/ttyUSB0` on RPi |
| 12V or 24V DIN rail PSU | 1 | Powers LEDs + modules |

---

## Software Changes Required

### 1. `install.sh`
- [ ] Add `pip3 install minimalmodbus` to dependency installation

### 2. `config.json`
- [ ] Remove `raspberry_pi.button_pins` section
- [ ] Add new `rs485` section:
```json
"rs485": {
  "port": "/dev/ttyUSB0",
  "baudrate": 9600,
  "timeout": 0.1,
  "modules": [
    {"id": 1, "buttons": [1, 2, 3, 4, 5, 6, 7, 8]},
    {"id": 2, "buttons": [9, 10, 11, 12, 13, 14, 15]}
  ]
}
```

### 3. `button_handler.py` — full rewrite of polling logic
- [ ] Replace `import RPi.GPIO as GPIO` with `import minimalmodbus`
- [ ] On init: open serial port, create `minimalmodbus.Instrument` for each module ID
- [ ] Polling loop: read all 8 DI registers from each module per tick
- [ ] Apply same non-blocking debounce state machine (unchanged logic)
- [ ] On valid press: call `callback(instrument_num)` — identical to current
- [ ] On `stop()`: close serial port cleanly

### 4. `looper_engine.py` — add LED output control
- [ ] Accept optional `modbus_handler` reference in `__init__`
- [ ] `_activate_instrument(n)` → call `modbus_handler.set_led(n, True)`
- [ ] `_deactivate_instrument(n)` → call `modbus_handler.set_led(n, False)`
- [ ] `_deactivate_system()` → call `modbus_handler.all_leds_off()` (safety clear)

### 5. `main.py` — wiring
- [ ] Instantiate `RS485ButtonHandler` instead of `UniversalButtonHandler`
- [ ] Pass `modbus_handler` reference into `LooperEngine`

---

## LED State Logic (complete specification)

| Event | LED state |
|-------|-----------|
| Button pressed, instrument starts playing | ON |
| Instrument timeout (60 s of no press) | OFF |
| Global timeout → system idle | ALL OFF |
| System reactivated (first press) | Only the pressed button → ON |
| Song rotation (between sessions) | ALL OFF |

---

## What Does NOT Change

- `AudioManager` — untouched
- `StatsCollector` / `StatsServer` — untouched
- `LoggingSetup` — untouched
- `LooperEngine` timeout logic — untouched
- `handle_button_press(instrument_num)` callback signature — untouched
- Debounce algorithm — same logic, different data source

---

## Open Questions (resolve before implementation)

- [ ] Confirmed baud rate of the Waveshare modules? 9600...
- [ ] Confirmed supply voltage for LEDs? 12V
- [ ] DO outputs on module: sinking (GND switch) or sourcing (+V switch)?
      → Determines whether `LED+` goes to PSU+ permanently (sinking) or
        `LED-` goes to PSU- permanently (sourcing)
- [ ] Button count max ? For now 16...