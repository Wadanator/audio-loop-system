"""Dashboard HTTP server and API routes for the audio loop room."""

import json
import logging
import mimetypes
import re
import socketserver
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse

from audio_loop.infra.paths import runtime_path


logger = logging.getLogger(__name__)


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Serve dashboard static files, JSON API, and remote layer commands."""

    context: Dict[str, Any] = {}

    def do_GET(self):
        """Route read-only dashboard and API requests."""
        path = urlparse(self.path).path

        if path == "/health":
            self._serve_json(self._health_payload())
            return
        if path == "/api/status":
            self._serve_json(self._status_payload())
            return
        if path == "/api/layers":
            self._serve_json(self._layers_payload())
            return
        if path == "/api/stats":
            self._serve_json(self._stats_payload())
            return

        self._serve_static(path)

    def do_POST(self):
        """Route remote control commands."""
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/layers/(\d+)/press", path)
        if not match:
            self._serve_json({"ok": False, "error": "not_found"}, status=404)
            return

        instrument = int(match.group(1))
        max_instruments = self._max_instruments()
        if not 1 <= instrument <= max_instruments:
            self._serve_json(
                {"ok": False, "error": "invalid_instrument"},
                status=400,
            )
            return

        engine = self.context.get("looper_engine")
        if engine is None or not hasattr(engine, "handle_button_press"):
            self._serve_json(
                {"ok": False, "error": "looper_engine_unavailable"},
                status=503,
            )
            return

        try:
            engine.handle_button_press(instrument)
        except Exception as exc:
            logger.error("Remote press failed for instrument %s: %s", instrument, exc)
            self._serve_json(
                {"ok": False, "error": "remote_press_failed", "detail": str(exc)},
                status=500,
            )
            return

        self._serve_json(
            {
                "ok": True,
                "instrument": instrument,
                "status": self._status_payload(),
            }
        )

    def log_message(self, format, *args):
        """Suppress default access logs to keep journald readable."""
        pass

    def _serve_json(self, payload: Any, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_text(self, message: str, status: int = 200):
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, request_path: str):
        static_root = self._static_root()
        index_path = static_root / "index.html"
        if not index_path.exists():
            self._serve_text(
                "Dashboard build missing. Run `npm run build` in dashboard/.",
                status=503,
            )
            return

        target = index_path if request_path in ("/", "") else self._static_file_path(
            static_root,
            request_path,
        )
        if target is None or not target.exists() or not target.is_file():
            target = index_path

        try:
            body = target.read_bytes()
        except Exception as exc:
            logger.warning("Failed to serve static dashboard file %s: %s", target, exc)
            self._serve_text("Dashboard file read failed", status=500)
            return

        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store" if target == index_path else "public, max-age=3600")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _static_root(self) -> Path:
        return runtime_path("src", "audio_loop", "web", "static")

    def _static_file_path(self, static_root: Path, request_path: str) -> Optional[Path]:
        relative = unquote(request_path).lstrip("/")
        candidate = (static_root / relative).resolve()
        root = static_root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        return candidate

    def _health_payload(self) -> Dict[str, Any]:
        uptime_start = self.context.get("started_at", time.time())
        return {
            "ok": True,
            "service": "audio-loop-system",
            "web": "running",
            "dashboard_built": (self._static_root() / "index.html").exists(),
            "uptime_seconds": max(0, time.time() - uptime_start),
        }

    def _status_payload(self) -> Dict[str, Any]:
        config = self.context.get("config", {})
        engine_status = self._engine_status()
        modbus_status = self._modbus_status()
        module_count = len(modbus_status)
        connected_modules = sum(
            1 for module in modbus_status.values() if module.get("connected")
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
            "modbus_connected_modules": connected_modules,
            "modbus_module_count": module_count,
            "modbus": modbus_status,
            "leds": self._led_status(),
            "updated_at": time.time(),
        }

    def _layers_payload(self) -> Dict[str, Any]:
        config = self.context.get("config", {})
        status = self._engine_status()
        stats = self._stats_payload().get("stats", {})
        active = set(status.get("active_instruments", []))
        available = set(status.get("available_instruments", []))
        led_status = self._led_status()
        led_states = led_status.get("last_output_state", {}) or {}
        input_mapping = self._input_instrument_mapping()
        output_mapping = self._output_instrument_mapping()
        label_config = config.get("layer_labels", {})

        layers = []
        for instrument in range(1, self._max_instruments() + 1):
            input_info = input_mapping.get(instrument)
            output_info = output_mapping.get(instrument)
            layers.append(
                {
                    "instrument": instrument,
                    "label": label_config.get(str(instrument), f"Zvuk {instrument}"),
                    "available": instrument in available,
                    "active": instrument in active,
                    "physical_input": input_info,
                    "input_state": bool(input_info and input_info.get("state")),
                    "input_raw_state": bool(input_info and input_info.get("raw_state")),
                    "led_output": output_info,
                    "led_state": bool(led_states.get(instrument, led_states.get(str(instrument), False))),
                    "stats_count": int(stats.get(f"instrument_{instrument}", 0)),
                }
            )

        return {"ok": True, "layers": layers, "updated_at": time.time()}

    def _stats_payload(self) -> Dict[str, Any]:
        stats = self._get_stats()
        return {"ok": stats is not None, "stats": stats or {}}

    def _engine_status(self) -> Dict[str, Any]:
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

    def _modbus_status(self) -> Dict[str, Any]:
        bus = self.context.get("modbus_bus")
        if bus is not None and hasattr(bus, "get_status"):
            try:
                return bus.get_status()
            except Exception as exc:
                logger.warning("Failed to read Modbus status: %s", exc)
        return {}

    def _led_status(self) -> Dict[str, Any]:
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

    def _get_stats(self) -> Optional[Dict[str, int]]:
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

    def _input_instrument_mapping(self) -> Dict[int, Dict[str, int]]:
        input_handler = self.context.get("input_handler")
        status = {}
        if input_handler is not None and hasattr(input_handler, "get_button_status"):
            try:
                status = input_handler.get_button_status()
            except Exception as exc:
                logger.warning("Failed to read input status: %s", exc)

        mapping = {}
        states = status.get("states", {}) or {}
        for module_name, channels in status.get("mappings", {}).items():
            module_states = states.get(module_name, {}) or {}
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
                    "state": bool(channel_state.get("stable", False)),
                    "raw_state": bool(channel_state.get("raw", False)),
                    "changed_at": channel_state.get("changed_at", 0),
                }
        return mapping

    def _output_instrument_mapping(self) -> Dict[int, Dict[str, int]]:
        led_status = self._led_status()
        mapping = {}
        for instrument, target in led_status.get("mapped_outputs", {}).items():
            module_name, channel = target
            mapping[int(instrument)] = {
                "module": module_name,
                "channel": int(channel),
            }
        return mapping

    def _max_instruments(self) -> int:
        config = self.context.get("config", {})
        return int(config.get("performance", {}).get("max_concurrent_sounds", 16))


class ThreadingDashboardServer(socketserver.ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a dedicated thread."""

    daemon_threads = True


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
    """Start the optional dashboard/API server."""
    DashboardRequestHandler.context = {
        "stats_collector": stats_collector,
        "looper_engine": looper_engine,
        "input_handler": input_handler,
        "led_controller": led_controller,
        "modbus_bus": modbus_bus,
        "config": config or {},
        "started_at": time.time(),
    }

    server_address = (host, int(port))
    max_retries = 5
    retry_delay = 10

    for attempt in range(1, max_retries + 1):
        try:
            httpd = ThreadingDashboardServer(server_address, DashboardRequestHandler)
            logger.info("Dashboard server started on http://%s:%s", host, port)
            try:
                httpd.serve_forever()
            except Exception as exc:
                logger.error("Dashboard server runtime error: %s", exc)
                httpd.server_close()
            break
        except OSError as exc:
            if attempt < max_retries:
                logger.error(
                    "Dashboard server failed to bind (attempt %s/%s): %s. "
                    "Retrying in %ss...",
                    attempt,
                    max_retries,
                    exc,
                    retry_delay,
                )
                time.sleep(retry_delay)
            else:
                logger.error(
                    "Dashboard server disabled after %s failed bind attempts: %s",
                    max_retries,
                    exc,
                )
        except Exception as exc:
            logger.error("Dashboard server unexpected error: %s", exc)
            break
