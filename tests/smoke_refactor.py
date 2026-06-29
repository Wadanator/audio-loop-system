"""Small smoke tests for the package refactor.

These tests intentionally avoid real audio hardware and Modbus hardware. They
only verify that imports stay clean and the core button-to-layer behavior still
works while files move into packages.
"""

import importlib
from pathlib import Path
import sys
import types

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)


def _stub_audio_dependencies():
    for module_name in ("sounddevice", "soundfile", "numpy"):
        sys.modules.setdefault(module_name, types.ModuleType(module_name))
    if not hasattr(sys.modules["numpy"], "ndarray"):
        sys.modules["numpy"].ndarray = object


def _import_looper_engine():
    module = importlib.import_module("audio_loop.core.looper_engine")
    return module.LooperEngine


class FakeAudioManager:
    def __init__(self):
        self.events = []
        self.available = [1, 2]

    def get_available_instruments(self):
        return self.available

    def get_current_song_info(self):
        return {
            "name": "song1",
            "index": 0,
            "total_songs": 1,
        }

    def restart_from_beginning(self):
        self.events.append(("restart",))
        return True

    def start_master_playback(self):
        self.events.append(("start",))
        return True

    def stop_master_playback(self):
        self.events.append(("stop",))

    def fade_in(self, instrument, duration):
        self.events.append(("fade_in", instrument, duration))

    def fade_out(self, instrument, duration):
        self.events.append(("fade_out", instrument, duration))

    def switch_to_next_song(self):
        self.events.append(("switch",))
        return "song1"


class FakeStatsCollector:
    def __init__(self):
        self.recorded = []

    def record_instrument(self, instrument):
        self.recorded.append(instrument)


class FakeLedController:
    def __init__(self):
        self.events = []

    def set_layer_active(self, instrument, active):
        self.events.append(("layer", instrument, active))

    def sync_from_active_layers(self, active_layers):
        self.events.append(("sync", list(active_layers)))


def test_import_main_does_not_import_gpio_or_legacy_wrappers():
    _stub_audio_dependencies()
    sys.modules.pop("button_handler", None)
    sys.modules.pop("RPi", None)
    sys.modules.pop("RPi.GPIO", None)

    importlib.import_module("main")

    assert "button_handler" not in sys.modules
    assert "RPi.GPIO" not in sys.modules

    removed_root_modules = [
        "audio_manager.py",
        "button_handler.py",
        "logging_setup.py",
        "looper_engine.py",
        "modbus_bus.py",
        "modbus_button_handler.py",
        "modbus_led_controller.py",
        "stats_collector.py",
        "stats_server.py",
    ]
    for module_file in removed_root_modules:
        assert not (PROJECT_ROOT / module_file).exists(), module_file


def test_looper_engine_toggles_layer_with_fake_dependencies():
    _stub_audio_dependencies()
    LooperEngine = _import_looper_engine()
    audio = FakeAudioManager()
    stats = FakeStatsCollector()
    leds = FakeLedController()
    config = {
        "timeouts": {
            "global_timeout": 75,
            "instrument_timeout": 60,
            "fade_duration": 2,
        },
        "raspberry_pi": {
            "button_cooldown_seconds": 0,
        },
        "song_rotation": {
            "enable": False,
            "switch_on_global_timeout": False,
        },
    }

    engine = LooperEngine(audio, config, stats, led_controller=leds)
    engine.handle_button_press(1)
    engine.handle_button_press(1)

    assert ("restart",) in audio.events
    assert ("fade_in", 1, 2) in audio.events
    assert ("fade_out", 1, 2) in audio.events
    assert stats.recorded == [1]
    assert ("layer", 1, True) in leds.events
    assert ("layer", 1, False) in leds.events

if __name__ == "__main__":
    test_import_main_does_not_import_gpio_or_legacy_wrappers()
    test_looper_engine_toggles_layer_with_fake_dependencies()
    print("smoke_refactor ok")