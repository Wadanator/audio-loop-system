# stats_server.py
import json
import os
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

logger = logging.getLogger(__name__)

class StatsServerHandler(BaseHTTPRequestHandler):
    """Handler for serving statistics over HTTP."""
    
    stats_file = "stats.json"
    
    def _load_stats(self) -> Optional[dict]:
        """Loads statistics from the JSON file."""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Failed to load stats: {e}")
            return None
    
    def do_GET(self):
        """Handles GET requests."""
        if self.path == "/stats":
            self._serve_json()
        else:
            self._serve_html()
    
    def _serve_html(self):
        """Serves statistics as an HTML page."""
        stats = self._load_stats()
        if stats is None:
            self.send_response(500)
            self.end_headers()
            self.wfile.write("Chyba: Nepodarilo sa načítať štatistiky".encode("utf-8"))
            return
        
        html = """
        <!DOCTYPE html>
        <html lang="sk">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Štatistiky Audio Looper</title>
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
                    Štatistiky Audio Looper
                </h1>
                <div class="overflow-x-auto rounded-lg border border-gray-200">
                    <table class="w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">Položka</th>
                                <th class="px-6 py-3 text-left text-sm font-semibold text-gray-700">Počet</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200 bg-white">
        """
        
        for i in range(1, 19):
            count = stats.get(f"instrument_{i}", 0)
            html += f"""
                            <tr class="hover:bg-gray-50 transition-colors">
                                <td class="px-6 py-4 text-sm text-gray-600">Nástroj {i}</td>
                                <td class="px-6 py-4 text-sm text-gray-600 font-medium">{count}</td>
                            </tr>
            """
        
        commands = {
            "status": "Zobraziť stav",
            "stop": "Zastaviť",
            "quit": "Ukončiť"
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
                        Obnovte stránku na aktualizáciu štatistík.
                    </p>
                    <button onclick="window.location.reload()" 
                            class="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 transition duration-200 font-medium w-full sm:w-auto">
                        Obnoviť
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
        """Serves statistics as JSON."""
        stats = self._load_stats()
        if stats is None:
            self.send_response(500)
            self.end_headers()
            self.wfile.write('{"error": "Nepodarilo sa načítať štatistiky"}'.encode("utf-8"))
            return
        
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(stats).encode("utf-8"))

def run_stats_server(host: str, port: int):
    """
    Runs the statistics web server.

    Args:
        host (str): The host address to bind the server to.
        port (int): The port number to listen on.
    """
    server_address = (host, port)
    httpd = HTTPServer(server_address, StatsServerHandler)
    logger.info(f"Starting stats server on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping stats server")
        httpd.server_close()