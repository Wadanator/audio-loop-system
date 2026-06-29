# Changelog

## 2026-06-29 - Clean Modbus Development Build

- Runtime code moved under `src/audio_loop/`.
- Root `main.py` is only a launcher.
- Removed old root compatibility wrappers.
- Removed the historical direct GPIO input file.
- Runtime input path is now `inputs.provider = "modbus_panel"`.
- Runtime output path is now `outputs.provider = "modbus_panel"`.
- Modbus bus owns one client and one lock per configured module.
- Box 1 DI1-DI8 verified by user on hardware.
- Box 1 DO1-DO8 verified by user with the output chaser script.
- LEDs mirror active audio layers best-effort.
- Bench scripts live in `tests/`.
- Implementation plan/log lives in `docs/implementation/`.

## Historical Notes

Older GPIO-based documentation was removed from the active docs because this project is still in development and does not need backwards compatibility with the original wiring model.