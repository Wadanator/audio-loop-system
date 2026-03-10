# Changelog

Tento súbor zaznamenáva všetky zmeny vykonané v projekte **Audio Loop System**.

---

## [1.2.1] – 2026-03-10 – Hotfix: Stats Dashboard GIL Starvation

### `stats_server.py`
- **[FIX]** Replaced `HTTPServer` with `ThreadingHTTPServer`
  (`socketserver.ThreadingMixIn` + `HTTPServer`) so each HTTP request is
  handled in its own thread — dashboard now loads correctly while audio is
  actively playing
- **Root cause:** `sounddevice` audio callback acquires the Python GIL ~23×/s;
  single-threaded `HTTPServer` was starved and browser connections timed out

---

## [1.2.0] – 2026-03-10 – Code Normalization and Documentation


### All Python files (`main.py`, `audio_manager.py`, `looper_engine.py`, `button_handler.py`, `stats_collector.py`, `stats_server.py`, `logging_setup.py`)

- **[NORM]** Applied PEP 8 formatting across all files: 4-space indentation, blank
  lines between top-level definitions, spacing around operators and commas,
  trailing whitespace removed, long lines broken where safe
- **[NORM]** Translated all Slovak comments, docstrings, log strings, and inline
  notes to clear professional English
- **[NORM]** Added PEP 257-compliant docstrings to every class, method, and
  function that was missing one — including `Args:` and `Returns:` sections
  where applicable
- **[NORM]** Added brief inline English comments to non-obvious or
  hardware-specific logic blocks (audio callback wrap-around, debounce state
  machine, atomic lock strategy, SD card write throttling)
- **[NORM]** No identifiers renamed, no imports reordered, no logic altered —
  the refactored code is behaviorally identical to the pre-normalization version

---

## [1.1.0] – 2026-03-10 – 24/7 Museum Reliability Fixes


### Opravené chyby (Bugfixes)

#### `looper_engine.py`
- **[FIX P1]** Odstránená vlastná inštancia `StatsCollector()` z `LooperEngine.__init__`
- Konštruktor teraz prijíma zdieľaný `stats_collector` ako parameter (dependency injection)
- Predtým mal `LooperEngine` vlastnú kópiu štatistík → záznamy sa nikdy neukladali cez `main.py`

#### `main.py`
- **[FIX P1]** `StatsCollector` sa vytvára ako jeden zdieľaný objekt a predáva sa do `LooperEngine`
- **[FIX P4]** Startup správy (`logger.error "Starting..."`) opravené na `logger.warning`
- **[FIX P4]** Shutdown správy (`logger.error "Shutting down..."`) opravené na `logger.warning`
- **[FIX P4]** Status log správy opravené na `logger.warning`
- **[FIX P5]** Pridaná funkcia `_send_watchdog()` – posiela `WATCHDOG=1` systemd signál každých 25 sekúnd
- **[FIX P5]** Pridaný `READY=1` systemd notify pri spustení (vyžaduje `sdnotify`)
- **[FIX P8]** Volanie `audio_manager.check_stream_health()` každých 60 sekúnd v hlavnej slučke

#### `audio_manager.py`
- **[FIX P2]** Pridaný `self.audio_data_lock = threading.Lock()` pre ochranu audio dát
- **[FIX P2]** `_audio_callback` používa `audio_data_lock.acquire(blocking=False)` – non-blocking ochrana pred race condition pri prepínaní skladieb
- **[FIX P2]** `_load_current_song` vykonáva atomickú výmenu audio dát pod `audio_data_lock`
- **[FIX P2]** `shutdown()` čistí `audio_tracks` pod `audio_data_lock`
- **[FIX P8]** Pridaná metóda `check_stream_health()` – detekuje zamrznutý/mŕtvy audio stream a automaticky ho reštartuje

#### `button_handler.py`
- **[FIX P3]** Odstránené `time.sleep(self.min_press_duration)` z `_debounce_button()` – blokovalo celé polling vlákno
- **[FIX P3]** Pridaný dictionary `self.press_start_times` – zaznamenáva čas prvého detekcie stlačenia
- **[FIX P3]** `_debounce_button` prepísaný na non-blocking state machine: `min_press_duration` sa overuje naprieč polling cyklami bez akéhokoľvek `sleep`
- **[FIX P3]** Pridaná inicializácia `self.press_start_times[pin] = 0` v `_setup_gpio()`

#### `logging_setup.py`
- **[FIX P4]** Pridaný `StreamHandler(sys.stdout)` s úrovňou `INFO` – INFO správy idú do journald bez zápisu na SD kartu
- **[FIX P4]** Opravený komentár (predtým: `memory_handler` sa nepridával; teraz sa `stdout_handler` pridáva)
- Zmenená log správa pri inicializácii na `logging.info` (nie `logging.error`)
- Úroveň logu pre `stats_collector` zmenená z `ERROR` na `INFO`

#### `stats_collector.py`
- **[FIX P4]** `logger.error("Loaded statistics from ...")` → `logger.info(...)` 
- **[FIX P4]** `logger.warning("No existing stats file found...")` → `logger.info(...)`
- **[FIX P4]** `logger.error("Stats saved to disk...")` → `logger.info(...)`
- **[FIX P4]** `logger.error("Stats force-saved to disk")` → `logger.info(...)`
- **[FIX P4]** `logger.error("Statistics reset to zero")` → `logger.warning(...)`
- Zachované: `logger.error(...)` pri skutočných chybách (Failed to load/save)

#### `stats_server.py`
- **[FIX P6]** Pridaná retry slučka (5 pokusov, 10s oneskorenie) okolo `HTTPServer` inicializácie – predtým tiché zlyhanie
- **[FIX P6]** Každý pokus o obnovu je zalogovaný na `ERROR` úrovni
- **[FIX P7]** Pridaná metóda `_get_stats()` namiesto `_load_stats()` – číta štatistiky primárne z pamäte cez `stats_collector.get_stats()`
- **[FIX P7]** Záložné načítanie zo súboru (backward compatibility) ak `stats_collector` nie je dostupný
- **[FIX P7]** Signatura `run_stats_server(host, port, stats_collector=None)` rozšírená o `stats_collector` parameter
- **[FIX P7]** Potlačené per-request HTTP access logy (override `log_message`) – menej šumu v journald

#### `install.sh`
- **[FIX P5]** Pridaná inštalácia `sdnotify` knižnice do pip príkazu
- **[FIX P5]** Zmenený `Type=simple` → `Type=notify` v systemd unit súbore
- **[FIX P5]** Pridaný `After=network.target` (stats server potrebuje sieť)
- **[FIX P5]** Pridaný `StartLimitIntervalSec=120` – ochrana pred nekonečnou reštart slučkou
- **[FIX P5]** Pridaný `StartLimitBurst=5` – max 5 reštartov za 120 sekúnd
- **[FIX P5]** Zmenený `RestartSec=5` → `RestartSec=10`
- **[FIX P5]** Pridaný `WatchdogSec=60` – systemd reštartuje service ak nezíska ping 60s

---

## [1.0.0] – Pôvodná verzia

- Základná implementácia audio looper systému pre Raspberry Pi
- Podpora až 18 WAV track-ov s fade-in/out efektmi
- GPIO polling-based button handler s debouncing logikou
- Globálny a per-instrument timeout systém
- Song rotation po globálnom timeoutt
- SD karta optimalizovaný logging (RotatingFileHandler, 5MB, 2 backup)
- Stats server (HTTP dashboard + JSON API)
- StatsCollector s periodic save (každých 5 minút) a atomic write
- systemd user service pre autoštart
