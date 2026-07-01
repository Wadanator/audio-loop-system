"""Small smoke tests for the package refactor and button state behavior.

These tests intentionally avoid real audio hardware and Modbus hardware. They
verify that imports stay clean and the core button-to-layer behavior remains
stable while files move into packages.
"""

import base64
import importlib
import json
import logging
from pathlib import Path
import sys
import tempfile
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


def _import_looper_module():
    return importlib.import_module("audio_loop.core.looper_engine")


def _base_config(*, min_on_seconds=0, rearm_seconds=0, max_instruments=16):
    return {
        "timeouts": {
            "global_timeout": 75,
            "instrument_timeout": 60,
            "fade_duration": 2,
        },
        "inputs": {
            "min_on_seconds": min_on_seconds,
            "rearm_seconds": rearm_seconds,
        },
        "performance": {
            "max_concurrent_sounds": max_instruments,
        },
        "song_rotation": {
            "enable": False,
            "switch_on_global_timeout": False,
        },
    }


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


def _make_engine(*, min_on_seconds=0, rearm_seconds=0, available=None):
    _stub_audio_dependencies()
    module = _import_looper_module()
    audio = FakeAudioManager()
    if available is not None:
        audio.available = available
    stats = FakeStatsCollector()
    leds = FakeLedController()
    engine = module.LooperEngine(
        audio,
        _base_config(
            min_on_seconds=min_on_seconds,
            rearm_seconds=rearm_seconds,
        ),
        stats,
        led_controller=leds,
    )
    return module, engine, audio, stats, leds


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


def test_looper_engine_toggles_layer_after_min_on_window():
    _, engine, audio, stats, leds = _make_engine(
        min_on_seconds=0,
        rearm_seconds=0,
    )

    engine.handle_button_press(1)
    engine.handle_button_press(1)

    assert ("restart",) in audio.events
    assert ("fade_in", 1, 2) in audio.events
    assert ("fade_out", 1, 2) in audio.events
    assert stats.recorded == [1]
    assert ("layer", 1, True) in leds.events
    assert ("layer", 1, False) in leds.events


def test_looper_engine_ignores_repeat_press_while_locked():
    module, engine, audio, stats, leds = _make_engine(
        min_on_seconds=10,
        rearm_seconds=0,
    )

    engine.handle_button_press(1)
    engine.handle_button_press(1)

    assert audio.events.count(("fade_in", 1, 2)) == 1
    assert ("fade_out", 1, 2) not in audio.events
    assert stats.recorded == [1]
    assert engine.instrument_states[1] == module.InstrumentState.ON_LOCKED
    assert ("layer", 1, True) in leds.events
    assert ("layer", 1, False) not in leds.events


def test_looper_engine_rearms_after_off_cooldown():
    module, engine, audio, stats, _ = _make_engine(
        min_on_seconds=0,
        rearm_seconds=10,
    )

    engine.handle_button_press(1)
    engine.handle_button_press(1)
    engine.handle_button_press(1)

    assert audio.events.count(("fade_in", 1, 2)) == 1
    assert audio.events.count(("fade_out", 1, 2)) == 1
    assert engine.instrument_states[1] == module.InstrumentState.OFF_COOLDOWN

    engine.instrument_deactivated_at[1] -= 11
    engine.handle_button_press(1)

    assert audio.events.count(("fade_in", 1, 2)) == 2
    assert stats.recorded == [1, 1]


def test_missing_audio_does_not_start_empty_session():
    _, engine, audio, stats, leds = _make_engine(available=[])

    engine.handle_button_press(1)

    assert audio.events == []
    assert stats.recorded == []
    assert leds.events == []
    assert engine.get_system_status()["system_active"] is False


def test_config_module_loads_current_config():
    config_module = importlib.import_module("audio_loop.config")
    config = config_module.load_config()

    assert config["inputs"]["provider"] == "modbus_panel"
    assert config["inputs"]["min_on_seconds"] == 1.5
    assert config["inputs"]["rearm_seconds"] == 0.2
    assert "button_cooldown_seconds" not in config["inputs"]
    assert "debouncing" not in config
    assert "double_press_protection_ms" not in config["modbus_panel"]
    assert config["modbus_panel"]["poll_interval_ms"] == 50
    assert config["modbus_panel"]["debounce_time_ms"] == 40
    assert config["performance"]["max_concurrent_sounds"] == 16
    assert "raspberry_pi" not in config
    assert config["outputs"]["provider"] == "modbus_panel"


def test_stats_collector_ignores_old_layer_keys():
    stats_module = importlib.import_module("audio_loop.stats.collector")

    with tempfile.TemporaryDirectory() as temp_dir:
        stats_path = Path(temp_dir) / "stats.json"
        stats_path.write_text(
            json.dumps({"instrument_1": 5, "instrument_17": 99}),
            encoding="utf-8",
        )

        collector = stats_module.StatsCollector(
            str(stats_path),
            max_instruments=16,
        )
        stats = collector.get_stats()

    assert stats["instrument_1"] == 5
    assert "instrument_17" not in stats


def test_stats_collector_replaces_existing_stats_file():
    stats_module = importlib.import_module("audio_loop.stats.collector")

    with tempfile.TemporaryDirectory() as temp_dir:
        stats_path = Path(temp_dir) / "stats.json"
        stats_path.write_text(
            json.dumps({"instrument_1": 1}),
            encoding="utf-8",
        )

        collector = stats_module.StatsCollector(
            str(stats_path),
            max_instruments=16,
        )
        collector.record_instrument(1)
        collector.force_save()
        saved = json.loads(stats_path.read_text(encoding="utf-8"))

    assert saved["instrument_1"] == 2


def test_pymodbus_log_filters_protect_disk_and_rate_limit_console():
    logging_setup = importlib.import_module("audio_loop.infra.logging_setup")

    drop_filter = logging_setup.SuppressLoggerBelowLevelFilter(
        ("pymodbus",),
        logging.CRITICAL,
    )
    pymodbus_error = logging.LogRecord(
        "pymodbus.logging",
        logging.ERROR,
        __file__,
        1,
        "Connection to module failed",
        (),
        None,
    )
    pymodbus_critical = logging.LogRecord(
        "pymodbus.logging",
        logging.CRITICAL,
        __file__,
        1,
        "Critical Modbus failure",
        (),
        None,
    )
    app_error = logging.LogRecord(
        "audio_loop.app",
        logging.ERROR,
        __file__,
        1,
        "Application failure",
        (),
        None,
    )

    assert drop_filter.filter(pymodbus_error) is False
    assert drop_filter.filter(pymodbus_critical) is True
    assert drop_filter.filter(app_error) is True

    now = [1000.0]
    rate_filter = logging_setup.RateLimitedLogFilter(
        600,
        ("pymodbus",),
        clock=lambda: now[0],
    )

    assert rate_filter.filter(pymodbus_error) is True
    assert rate_filter.filter(pymodbus_error) is False
    now[0] += 601
    assert rate_filter.filter(pymodbus_error) is True

def test_modbus_button_status_reports_debounced_input_state():
    modbus_panel = importlib.import_module("audio_loop.input.modbus_panel")

    class FakeBus:
        def get_input_mappings(self):
            return {"box_1": {1: 1}}

        def get_status(self):
            return {"box_1": {"connected": True}}

    handler = modbus_panel.ModbusButtonHandler(
        lambda instrument: None,
        {"modbus_panel": {"enabled": True}},
        bus=FakeBus(),
    )
    handler.channel_states[("box_1", 1)] = modbus_panel._ChannelState(
        raw=True,
        stable=True,
        changed_at=123.0,
    )

    status = handler.get_button_status()

    assert status["mappings"]["box_1"][1] == 1
    assert status["states"]["box_1"][1]["stable"] is True
    assert status["states"]["box_1"][1]["raw"] is True


def test_dashboard_layers_payload_uses_live_input_and_led_state():
    server_module = importlib.import_module("audio_loop.web.server")

    class FakeEngine:
        def __init__(self):
            self.pressed = []

        def get_system_status(self):
            return {
                "system_active": True,
                "current_song": {"name": "song1"},
                "active_instruments": [1],
                "available_instruments": [1, 2, 3],
                "session_duration": 0,
                "time_until_timeout": 60,
                "total_sessions": 1,
                "song_rotation_enabled": True,
            }

        def handle_button_press(self, instrument):
            self.pressed.append(instrument)

    class FakeStats:
        def get_stats(self):
            return {"instrument_1": 7, "instrument_2": 0, "instrument_3": 0}

    class FakeInput:
        def get_button_status(self):
            return {
                "mappings": {"box_1": {1: 1, 2: 2}},
                "states": {
                    "box_1": {
                        1: {"stable": True, "raw": True, "changed_at": 123.0},
                        2: {"stable": False, "raw": False, "changed_at": 124.0},
                    }
                },
                "bus": {"box_1": {"connected": True}},
            }

    class FakeLed:
        def get_status(self):
            return {
                "enabled": True,
                "mapped_outputs": {1: ("box_1", 1), 2: ("box_1", 2)},
                "last_output_state": {1: True, 2: False},
                "last_error": None,
                "last_error_at": 0,
            }

    class FakeBus:
        def get_status(self):
            return {
                "box_1": {"connected": True},
                "box_2": {"connected": False},
            }

    engine = FakeEngine()
    context = {
        "looper_engine": engine,
        "stats_collector": FakeStats(),
        "input_handler": FakeInput(),
        "led_controller": FakeLed(),
        "modbus_bus": FakeBus(),
        "config": {
            "performance": {"max_concurrent_sounds": 3},
            "web": {"logs": {"persist_enabled": False, "load_limit": 0}},
        },
    }
    service = server_module.DashboardService(context)
    payload = service.layers_payload()

    layer_1, layer_2, layer_3 = payload["layers"]
    assert layer_1["input_connected"] is True
    assert layer_1["input_state"] is True
    assert layer_1["led_state"] is True
    assert layer_1["stats_count"] == 7
    assert layer_2["input_connected"] is True
    assert layer_2["input_state"] is False
    assert layer_2["led_state"] is False
    assert layer_3["input_connected"] is False
    assert layer_3["physical_input"] is None

    app = server_module.create_dashboard_app(
        looper_engine=engine,
        stats_collector=context["stats_collector"],
        input_handler=context["input_handler"],
        led_controller=context["led_controller"],
        modbus_bus=context["modbus_bus"],
        config=context["config"],
    )
    client = app.test_client()

    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json()["web_backend"] == "flask"

    status = client.get("/api/status")
    assert status.status_code == 200
    status_payload = status.get_json()
    assert status_payload["modbus_degraded"] is True
    assert status_payload["modbus_disconnected_modules"] == ["box_2"]

    response = client.post("/api/layers/2/press")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert engine.pressed == [2]


def _basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def test_dashboard_auth_and_system_actions_are_guarded():
    server_module = importlib.import_module("audio_loop.web.server")

    disabled_app = server_module.create_dashboard_app(
        config={"web": {"auth_enabled": False, "system_actions_enabled": True, "logs": {"persist_enabled": False, "load_limit": 0}}},
    )
    disabled_response = disabled_app.test_client().post("/api/system/reboot")
    assert disabled_response.status_code == 403
    assert disabled_response.get_json()["error"] == "system_actions_require_auth"

    scheduled_commands = []
    original_schedule = server_module._schedule_system_command
    original_linux_check = server_module._running_on_linux
    try:
        def fake_schedule(command, *, delay=server_module.SYSTEM_ACTION_DELAY_SECONDS):
            scheduled_commands.append((list(command), delay))

        server_module._schedule_system_command = fake_schedule
        server_module._running_on_linux = lambda: True

        app = server_module.create_dashboard_app(
            config={
                "performance": {"max_concurrent_sounds": 2},
                "web": {
                    "auth_enabled": True,
                    "username": "admin",
                    "password": "secret",
                    "system_actions_enabled": True,
                    "system_service_name": "audio_looper.service",
                    "logs": {"persist_enabled": False, "load_limit": 0},
                },
            },
        )
        client = app.test_client()

        assert client.get("/api/status").status_code == 401
        assert client.get(
            "/api/status",
            headers={"Authorization": _basic_auth("admin", "wrong")},
        ).status_code == 401

        headers = {"Authorization": _basic_auth("admin", "secret")}
        status_response = client.get("/api/status", headers=headers)
        assert status_response.status_code == 200
        status_payload = status_response.get_json()
        assert status_payload["auth_enabled"] is True
        assert status_payload["system_actions_enabled"] is True

        restart_response = client.post("/api/system/restart_service", headers=headers)
        assert restart_response.status_code == 200
        assert scheduled_commands[-1][0] == [
            "systemctl",
            "--user",
            "restart",
            "audio_looper.service",
        ]

        shutdown_response = client.post("/api/system/shutdown", headers=headers)
        assert shutdown_response.status_code == 200
        assert scheduled_commands[-1][0][-2:] == ["-h", "now"]
    finally:
        server_module._schedule_system_command = original_schedule
        server_module._running_on_linux = original_linux_check


def test_dashboard_logs_capture_warnings_and_manual_audit_events():
    server_module = importlib.import_module("audio_loop.web.server")

    app = server_module.create_dashboard_app(
        config={
            "web": {
                "auth_enabled": False,
                "logs": {
                    "persist_enabled": False,
                    "load_limit": 0,
                    "min_level": "WARNING",
                    "include_info_loggers": ["audio_loop.audit"],
                },
            },
        },
    )
    service = app.config["DASHBOARD_SERVICE"]
    service.clear_logs()

    logging.getLogger("audio_loop.noise").info("Routine physical button event")
    logging.getLogger("audio_loop.audit").info(
        "Dashboard remote sound press: instrument %s from %s",
        3,
        "test-client",
    )
    logging.getLogger("audio_loop.hardware.modbus_bus").warning("Box 2 offline")

    client = app.test_client()
    response = client.get("/api/logs")
    assert response.status_code == 200
    payload = response.get_json()
    messages = [entry["message"] for entry in payload["logs"]]

    assert "Routine physical button event" not in messages
    assert any("Dashboard remote sound press" in message for message in messages)
    assert "Box 2 offline" in messages

    warnings = client.get("/api/logs?level=WARNING").get_json()["logs"]
    assert [entry["message"] for entry in warnings] == ["Box 2 offline"]

    clear_response = client.post("/api/logs/clear")
    assert clear_response.status_code == 200
    assert client.get("/api/logs").get_json()["logs"] == []


if __name__ == "__main__":
    test_import_main_does_not_import_gpio_or_legacy_wrappers()
    test_config_module_loads_current_config()
    test_stats_collector_ignores_old_layer_keys()
    test_stats_collector_replaces_existing_stats_file()
    test_pymodbus_log_filters_protect_disk_and_rate_limit_console()
    test_modbus_button_status_reports_debounced_input_state()
    test_dashboard_layers_payload_uses_live_input_and_led_state()
    test_dashboard_auth_and_system_actions_are_guarded()
    test_dashboard_logs_capture_warnings_and_manual_audit_events()
    test_looper_engine_toggles_layer_after_min_on_window()
    test_looper_engine_ignores_repeat_press_while_locked()
    test_looper_engine_rearms_after_off_cooldown()
    test_missing_audio_does_not_start_empty_session()
    print("smoke_refactor ok")
