# stats_server.py
"""HTTP server for serving instrument activation statistics."""

import json
import os
import logging
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
from typing import Optional


logger = logging.getLogger(__name__)


class StatsServerHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves statistics as HTML or JSON.

    The class-level ``stats_collector`` attribute must be set before the
    server is started. If it is ``None``, the handler falls back to
    reading ``stats.json`` from disk.
    """

    # Shared StatsCollector instance (set by run_stats_server).
    # Reads in-memory stats instead of hitting the disk on every request.
    stats_collector = None
    stats_file = "stats.json"

    def _get_stats(self) -> Optional[dict]:
        """Retrieve statistics, preferring the in-memory source.

        Returns the current stats dict from the shared ``StatsCollector``
        if available, otherwise falls back to reading ``stats.json`` from
        disk for backward compatibility.

        Returns:
            Dictionary of stat keys and counts, or None on failure.
        """
        if self.stats_collector is not None:
            try:
                return self.stats_collector.get_stats()
            except Exception as e:
                logger.warning(
                    f"Failed to get stats from memory, "
                    f"falling back to file: {e}"
                )

        # Fallback: read from disk if no in-memory source is available.
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Failed to load stats from file: {e}")
            return None

    def do_GET(self):
        """Handle incoming HTTP GET requests.

        Routes ``/stats`` to the JSON endpoint and all other paths to
        the HTML dashboard.
        """
        if self.path == "/stats":
            self._serve_json()
        else:
            self._serve_html()

    def log_message(self, format, *args):
        """Suppress the default per-request access log.

        Overridden to prevent high-frequency HTTP access log entries
        from appearing in journald output.
        """
        pass  # HTTP access logs disabled to reduce journald noise.

    def _serve_html(self):
        """Respond with a styled HTML statistics dashboard."""
        stats = self._get_stats()
        if stats is None:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(
                "Error: Failed to load statistics".encode("utf-8")
            )
            return

        html = """
        <!DOCTYPE html>
        <html lang="sk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Audio Looper Statistics</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <style>
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .fade-in {
                    animation: fadeIn 0.5s ease-out;
                }
                body {
                    background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
                }
                .card {
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                }
            </style>
        </head>
        <body class="min-h-screen flex items-center justify-center p-4 font-sans">
            <div class="bg-white rounded-xl shadow-xl p-8 max-w-md w-full fade-in card">
                <h1 class="text-3xl font-bold text-gray-800 mb-8 text-center tracking-tight">
                    Audio Looper Statistics
                </h1>
                <div class="overflow-x-auto rounded-lg border border-gray-200">
                    <table class="w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">Item</th>
                                <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">Count</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200 bg-white">
        """

        for i in range(1, 19):
            count = stats.get(f"instrument_{i}", 0)
            html += f"""
                            <tr class="hover:bg-gray-50 transition-colors">
                                <td class="px-6 py-4 text-sm text-gray-600">Instrument {i}</td>
                                <td class="px-6 py-4 text-sm text-gray-600 font-medium">{count}</td>
                            </tr>
            """

        commands = {
            "status": "Show status",
            "stop": "Stop",
            "quit": "Quit"
        }
        for cmd, label in commands.items():
            count = stats.get(f"command_{cmd}", 0)
            html += f"""
                            <tr class="hover:bg-gray-50 transition-colors">
                                <td class="px-6 py-4 text-sm text-gray-600">{label}</td>
                                <td class="px-6 py-4 text-sm text-gray-600 font-medium">{count}</td>
                            </tr>
            """

        html += """
                        </tbody>
                    </table>
                </div>
                <div class="mt-8 flex flex-col sm:flex-row justify-between items-center gap-4">
                    <p class="text-gray-500 text-sm text-center sm:text-left">
                        Refresh the page to update statistics.
                    </p>
                    <button onclick="window.location.reload()"
                            class="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 transition duration-200 font-medium w-full sm:w-auto">
                        Refresh
                    </button>
                </div>
            </div>
        </body>
        </html>
        """

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _serve_json(self):
        """Respond with the statistics payload serialized as JSON."""
        stats = self._get_stats()
        if stats is None:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(
                '{"error": "Failed to load statistics"}'.encode("utf-8")
            )
            return

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(stats).encode("utf-8"))


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a dedicated thread.

    Prevents GIL contention with the sounddevice audio callback from
    blocking or delaying HTTP responses when audio is actively playing.
    """
    daemon_threads = True


def run_stats_server(host: str, port: int, stats_collector=None):
    """Start the statistics HTTP server and keep it running.

    Retries up to 5 times with a 10-second delay between attempts if the
    server cannot bind to the requested port. Logs each failure before
    giving up.

    Args:
        host: Host address to bind (e.g. ``'0.0.0.0'``).
        port: TCP port to listen on.
        stats_collector: Shared ``StatsCollector`` instance for in-memory
            stat reads. If ``None``, the handler reads from disk instead.
    """
    # Attach the shared stats source so handlers can read from RAM.
    StatsServerHandler.stats_collector = stats_collector

    server_address = (host, port)

    # Retry loop: handles transient port conflicts without silent failure.
    max_retries = 5
    retry_delay = 10  # seconds between bind attempts

    for attempt in range(1, max_retries + 1):
        try:
            httpd = ThreadingHTTPServer(server_address, StatsServerHandler)
            logger.info(f"Stats server started on http://{host}:{port}")
            try:
                httpd.serve_forever()
            except Exception as e:
                logger.error(f"Stats server runtime error: {e}")
                httpd.server_close()
            break  # Exit retry loop after a normal serve_forever exit.

        except OSError as e:
            if attempt < max_retries:
                logger.error(
                    f"Stats server failed to bind "
                    f"(attempt {attempt}/{max_retries}): {e}. "
                    f"Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                logger.error(
                    f"Stats server could not start after {max_retries} "
                    f"attempts: {e}. Stats server disabled."
                )
        except Exception as e:
            logger.error(f"Stats server unexpected error: {e}")
            break