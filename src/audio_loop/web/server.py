"""Flask dashboard server and API routes for the audio loop room."""

import json
import logging
import mimetypes
import time
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, Response, jsonify, send_file
from werkzeug.serving import make_server

from audio_loop.infra.paths import runtime_path


logger = logging.getLogger(__name__)


class DashboardService:
    """Build dashboard API payloads from the running audio loop context."""

    def __init__(self, context: Optional[Dict[str, Any]] = None):
        self.context = context or {}

    def health_payload(self) -> Dict[str, Any]:
        uptime_start = self.context.get("started_at", time.time())
        return {
            "ok": True,
            "service": "audio-loop-system",
            "web": "running",
            "web_backend": "flask",
            "dashboard_built": (self.static_root() / "index.html").exists(),
            "uptime_seconds": max(0, time.time() - uptime_start),
        }

    def status_payload(self) -> Dict[str, Any]:
        config = self.context.get("config", {})
        engine_status = self.engine_status()
        modbus_status = self.modbus_status()
        module_count = len(modbus_status)
        connected_modules = sum(
            1 for module in modbus_status.values() if module.get("connected")
        )
        disconnected_modules = sorted(
            name for name, module in modbus_status.items()
            if not module.get("connected")
        )

        return {
            "ok": True,
            "system_active": engine_status.get("system_active", False),
            "current_song": engine_status.get("current_song"),
            "active_instruments": engine_status.get("active_instruments", []),
            "available_instruments": engine_status.get("available_instruments", []),
            "session_duration": engine_status.get("session_duration", 0),
            "time_until_timeout": engine_status.get("time_until_timeout", 0),
            "total_sessions": engine_status.get("total_sessions", 0),
            "song_rotation_enabled": engine_status.get("song_rotation_enabled", False),
            "web_enabled": bool(config.get("web", {}).get("enabled", True)),
            "input_provider": config.get("inputs", {}).get("provider"),
            "output_provider": config.get("outputs", {}).get("provider"),
            "modbus_connected": module_count > 0 and connected_modules == module_count,
            "modbus_degraded": module_count > 0 and bool(disconnected_modules),
            "modbus_connected_modules": connected_modules,
            "modbus_module_count": module_count,
            "modbus_disconnected_modules": disconnected_modules,
            "modbus": modbus_status,
            "leds": self.led_status(),
            "updated_at": time.time(),
        }

    def layers_payload(self) -> Dict[str, Any]:
        config = self.context.get("config", {})
        status = self.engine_status()
        stats = self.stats_payload().get("stats", {})
        active = set(status.get("active_instruments", []))
        available = set(status.get("available_instruments", []))
        led_status = self.led_status()
        led_states = led_status.get("last_output_state", {}) or {}
        input_mapping = self.input_instrument_mapping()
        output_mapping = self.output_instrument_mapping()
        label_config = config.get("layer_labels", {})

        layers = []
        for instrument in range(1, self.max_instruments() + 1):
            input_info = input_mapping.get(instrument)
            output_info = output_mapping.get(instrument)
            input_connected = bool(input_info and input_info.get("connected"))
            layers.append(
                {
                    "instrument": instrument,
                    "label": label_config.get(str(instrument), f"Zvuk {instrument}"),
                    "available": instrument in available,
                    "active": instrument in active,
                    "physical_input": input_info,
                    "input_connected": input_connected,
                    "input_state": bool(input_info and input_info.get("state")),
                    "input_raw_state": bool(input_info and input_info.get("raw_state")),
                    "led_output": output_info,
                    "led_state": bool(
                        led_states.get(
                            instrument,
                            led_states.get(str(instrument), False),
                        )
                    ),
                    "stats_count": int(stats.get(f"instrument_{instrument}", 0)),
                }
            )

        return {"ok": True, "layers": layers, "updated_at": time.time()}

    def stats_payload(self) -> Dict[str, Any]:
        stats = self.get_stats()
        return {"ok": stats is not None, "stats": stats or {}}

    def engine_status(self) -> Dict[str, Any]:
        engine = self.context.get("looper_engine")
        if engine is not None and hasattr(engine, "get_system_status"):
            try:
                return engine.get_system_status()
            except Exception as exc:
                logger.warning("Failed to read looper engine status: %s", exc)
        return {
            "system_active": False,
            "current_song": None,
            "active_instruments": [],
            "available_instruments": [],
            "session_duration": 0,
            "time_until_timeout": 0,
            "total_sessions": 0,
            "song_rotation_enabled": False,
        }

    def modbus_status(self) -> Dict[str, Any]:
        bus = self.context.get("modbus_bus")
        if bus is not None and hasattr(bus, "get_status"):
            try:
                return bus.get_status()
            except Exception as exc:
                logger.warning("Failed to read Modbus status: %s", exc)
        return {}

    def led_status(self) -> Dict[str, Any]:
        controller = self.context.get("led_controller")
        if controller is not None and hasattr(controller, "get_status"):
            try:
                return controller.get_status()
            except Exception as exc:
                logger.warning("Failed to read LED status: %s", exc)
        return {
            "enabled": False,
            "mapped_outputs": {},
            "last_output_state": {},
            "last_error": None,
            "last_error_at": 0,
        }

    def get_stats(self) -> Optional[Dict[str, int]]:
        collector = self.context.get("stats_collector")
        if collector is not None and hasattr(collector, "get_stats"):
            try:
                return collector.get_stats()
            except Exception as exc:
                logger.warning("Failed to read in-memory stats: %s", exc)

        stats_path = runtime_path("stats.json")
        try:
            if stats_path.exists():
                with stats_path.open("r", encoding="utf-8-sig") as handle:
                    return json.load(handle)
        except Exception as exc:
            logger.error("Failed to load stats from %s: %s", stats_path, exc)
        return None

    def input_instrument_mapping(self) -> Dict[int, Dict[str, Any]]:
        input_handler = self.context.get("input_handler")
        status = {}
        if input_handler is not None and hasattr(input_handler, "get_button_status"):
            try:
                status = input_handler.get_button_status()
            except Exception as exc:
                logger.warning("Failed to read input status: %s", exc)

        mapping = {}
        states = status.get("states", {}) or {}
        bus_status = status.get("bus", {}) or {}
        for module_name, channels in status.get("mappings", {}).items():
            module_states = states.get(module_name, {}) or {}
            module_status = bus_status.get(module_name, {}) or {}
            for channel, instrument in channels.items():
                channel_number = int(channel)
                channel_state = (
                    module_states.get(channel_number)
                    or module_states.get(str(channel_number))
                    or {}
                )
                mapping[int(instrument)] = {
                    "module": module_name,
                    "channel": channel_number,
                    "connected": bool(module_status.get("connected", False)),
                    "state": bool(channel_state.get("stable", False)),
                    "raw_state": bool(channel_state.get("raw", False)),
                    "changed_at": channel_state.get("changed_at", 0),
                }
        return mapping

    def output_instrument_mapping(self) -> Dict[int, Dict[str, int]]:
        led_status = self.led_status()
        mapping = {}
        for instrument, target in led_status.get("mapped_outputs", {}).items():
            module_name, channel = target
            mapping[int(instrument)] = {
                "module": module_name,
                "channel": int(channel),
            }
        return mapping

    def max_instruments(self) -> int:
        config = self.context.get("config", {})
        return int(config.get("performance", {}).get("max_concurrent_sounds", 16))

    def static_root(self) -> Path:
        return runtime_path("src", "audio_loop", "web", "static")

    def static_file_path(self, request_path: str) -> Optional[Path]:
        relative = request_path.lstrip("/")
        candidate = (self.static_root() / relative).resolve()
        root = self.static_root().resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        return candidate


def _json_response(payload: Any, status: int = 200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def create_dashboard_app(
    *,
    stats_collector=None,
    looper_engine=None,
    input_handler=None,
    led_controller=None,
    modbus_bus=None,
    config: Optional[dict] = None,
) -> Flask:
    """Create the Flask app used by the dashboard/API server."""
    flask_app = Flask(__name__, static_folder=None)
    flask_app.config["JSON_AS_ASCII"] = False
    flask_app.config["DASHBOARD_SERVICE"] = DashboardService(
        {
            "stats_collector": stats_collector,
            "looper_engine": looper_engine,
            "input_handler": input_handler,
            "led_controller": led_controller,
            "modbus_bus": modbus_bus,
            "config": config or {},
            "started_at": time.time(),
        }
    )

    @flask_app.get("/health")
    def health():
        service = flask_app.config["DASHBOARD_SERVICE"]
        return _json_response(service.health_payload())

    @flask_app.get("/api/status")
    def status():
        service = flask_app.config["DASHBOARD_SERVICE"]
        return _json_response(service.status_payload())

    @flask_app.get("/api/layers")
    def layers():
        service = flask_app.config["DASHBOARD_SERVICE"]
        return _json_response(service.layers_payload())

    @flask_app.get("/api/stats")
    def stats():
        service = flask_app.config["DASHBOARD_SERVICE"]
        return _json_response(service.stats_payload())

    @flask_app.post("/api/layers/<int:instrument>/press")
    def press_layer(instrument: int):
        service = flask_app.config["DASHBOARD_SERVICE"]
        max_instruments = service.max_instruments()
        if not 1 <= instrument <= max_instruments:
            return _json_response({"ok": False, "error": "invalid_instrument"}, 400)

        engine = service.context.get("looper_engine")
        if engine is None or not hasattr(engine, "handle_button_press"):
            return _json_response(
                {"ok": False, "error": "looper_engine_unavailable"},
                503,
            )

        try:
            engine.handle_button_press(instrument)
        except Exception as exc:
            logger.error("Remote press failed for instrument %s: %s", instrument, exc)
            return _json_response(
                {"ok": False, "error": "remote_press_failed", "detail": str(exc)},
                500,
            )

        return _json_response(
            {
                "ok": True,
                "instrument": instrument,
                "status": service.status_payload(),
            }
        )

    @flask_app.get("/")
    @flask_app.get("/<path:request_path>")
    def dashboard_static(request_path: str = ""):
        service = flask_app.config["DASHBOARD_SERVICE"]
        static_root = service.static_root()
        index_path = static_root / "index.html"
        if not index_path.exists():
            return Response(
                "Dashboard build missing. Run `npm run build` in dashboard/.",
                status=503,
                content_type="text/plain; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )

        target = index_path if request_path in ("", "/") else service.static_file_path(
            request_path
        )
        if target is None or not target.exists() or not target.is_file():
            target = index_path

        mimetype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        response = send_file(target, mimetype=mimetype)
        response.headers["Cache-Control"] = (
            "no-store" if target == index_path else "public, max-age=3600"
        )
        return response

    return flask_app


def run_dashboard_server(
    host: str,
    port: int,
    *,
    stats_collector=None,
    looper_engine=None,
    input_handler=None,
    led_controller=None,
    modbus_bus=None,
    config: Optional[dict] = None,
):
    """Start the optional Flask dashboard/API server."""
    flask_app = create_dashboard_app(
        stats_collector=stats_collector,
        looper_engine=looper_engine,
        input_handler=input_handler,
        led_controller=led_controller,
        modbus_bus=modbus_bus,
        config=config,
    )

    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    max_retries = 5
    retry_delay = 10

    for attempt in range(1, max_retries + 1):
        httpd = None
        try:
            httpd = make_server(host, int(port), flask_app, threaded=True)
            logger.info("Flask dashboard server started on http://%s:%s", host, port)
            httpd.serve_forever()
            break
        except OSError as exc:
            if httpd is not None:
                httpd.server_close()
            if attempt < max_retries:
                logger.error(
                    "Flask dashboard server failed to bind (attempt %s/%s): %s. "
                    "Retrying in %ss...",
                    attempt,
                    max_retries,
                    exc,
                    retry_delay,
                )
                time.sleep(retry_delay)
            else:
                logger.error(
                    "Flask dashboard server disabled after %s failed bind attempts: %s",
                    max_retries,
                    exc,
                )
        except Exception as exc:
            if httpd is not None:
                httpd.server_close()
            logger.error("Flask dashboard server unexpected error: %s", exc)
            break