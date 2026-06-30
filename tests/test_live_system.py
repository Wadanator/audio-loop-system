#!/usr/bin/env python3
"""
=============================================================================
Audio Looper System – Live System Test
=============================================================================

Spustenie (z project rootu alebo z tests/ priečinka):
    python3 tests/test_live_system.py

Požiadavky:
    - Systém beží ako systemd service: audio_looper.service
    - Flask dashboard server dostupný na http://localhost:8000
    - Tento skript sa spúšťa na tom istom RPi kde beží service
    - Spúšťa sa ako rovnaký user (nie root)

Čo testuje:
    1.  Service je aktívna a beží
    2.  Service nie je v stave failed
    3.  Service nepadá (restart counter)
    4.  Systemd watchdog je nakonfigurovaný
    5.  User linger je zapnutý
    6.  Flask dashboard server odpovedá na HTTP
    7.  Stats HTML dashboard je dostupný
    8.  Stats JSON má správnu štruktúru
    9.  Stats JSON hodnoty sú validné
    10. Flask dashboard server zvládne súčasné požiadavky
    11. critical_errors.log neobsahuje ERROR záznamy
    12. Journald neobsahuje ERROR záznamy za posl. 60 min
    13. Log súbor nie je príliš veľký
    14. stats.json existuje a je validný
    15. config.json je validný a má povinné kľúče
    16. Song foldery existujú a obsahujú WAV súbory
    17. RAM použitie service je v norme
    18. CPU použitie v idle stave je v norme
    19. Dostatok miesta na SD karte
    20. Service sa zotaví po reštarte (voliteľný, pýta sa)

POZOR: Test č.20 (restart) krátkodobo preruší audio playback (~10s).
       Spúšťaj ho keď múzeum nie je otvorené, alebo odpovedz 'n'.
=============================================================================
"""

import subprocess
import sys
import os
import json
import time
import urllib.request
import urllib.error
import threading

# ── Konfigurácia ──────────────────────────────────────────────────────────────

# Súbor je v tests/ priečinku → project root je o úroveň vyššie
PROJECT_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SERVICE_NAME     = "audio_looper.service"
STATS_URL        = "http://localhost:8000/api/stats"
STATS_HTML_URL   = "http://localhost:8000"
CONFIG_PATH      = os.path.join(PROJECT_ROOT, "config.json")
STATS_FILE       = os.path.join(PROJECT_ROOT, "stats.json")
LOGS_DIR         = os.path.join(PROJECT_ROOT, "logs")
CRITICAL_LOG     = os.path.join(LOGS_DIR, "critical_errors.log")

MAX_RAM_MB       = 300    # Maximálna povolená RAM pre service proces
MAX_CPU_PERCENT  = 15.0   # Maximálne CPU v idle stave (%)
MAX_LOG_SIZE_MB  = 4.5    # Varovanie ak log sa blíži k rotačnému limitu (5MB)
MIN_FREE_DISK_MB = 200    # Minimálne voľné miesto na SD karte
HTTP_TIMEOUT_S   = 5      # Timeout pre HTTP požiadavky na stats server

# ── Pomocné funkcie ───────────────────────────────────────────────────────────

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"
INFO = "ℹ️  INFO"

results = []  # (status, test_name, detail)


def record(status, name, detail=""):
    results.append((status, name, detail))
    icon = status.split()[0]
    line = f"  {icon}  {name}"
    if detail:
        line += f"\n         → {detail}"
    print(line)


def run(cmd, timeout=10):
    """Spusti shell príkaz, vráť (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


def section(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ── Testy ─────────────────────────────────────────────────────────────────────

def test_service_active():
    """Service musí byť v stave 'active (running)'."""
    rc, out, _ = run(f"systemctl --user is-active {SERVICE_NAME}")
    if rc == 0 and out == "active":
        record(PASS, "Service je active")
    else:
        record(FAIL, "Service nie je active", f"Stav: '{out}' (rc={rc})")


def test_service_not_failed():
    """Service nesmie byť v stave 'failed'."""
    rc, out, _ = run(
        f"systemctl --user show {SERVICE_NAME} --property=ActiveState"
    )
    if rc != 0:
        record(WARN, "Nedá sa zistiť ActiveState service", out)
        return
    if "ActiveState=failed" not in out:
        record(PASS, "Service nie je v stave failed")
    else:
        record(FAIL, "Service je v stave FAILED",
               "Skontroluj: journalctl --user -u audio_looper.service --no-pager -n 50")


def test_service_restart_count():
    """Service by nemala mať viac ako 2 reštarty od posledného bootu."""
    rc, out, _ = run(
        f"systemctl --user show {SERVICE_NAME} --property=NRestarts"
    )
    if rc != 0:
        record(WARN, "Nedá sa zistiť počet restartov", out)
        return
    try:
        n = int(out.split("=")[1])
        if n == 0:
            record(PASS, f"Počet restartov: {n}")
        elif n <= 2:
            record(WARN, f"Počet restartov: {n}",
                   "Niekoľko restartov – skontroluj logy")
        else:
            record(FAIL, f"Počet restartov: {n}",
                   "Príliš veľa restartov – service pravdepodobne crashuje")
    except Exception:
        record(WARN, "Nedá sa parsovať počet restartov", out)


def test_service_watchdog_configured():
    """Service musí mať nakonfigurovaný WatchdogSec v unit súbore."""
    rc, out, _ = run(
        f"systemctl --user show {SERVICE_NAME} --property=WatchdogUSec"
    )
    if rc != 0:
        record(WARN, "Watchdog test – nedá sa overiť", out)
        return
    try:
        val = out.split("=")[1].strip()
        if val not in ("0", "0s"):
            record(PASS, f"Systemd watchdog je aktívny (WatchdogUSec={val})")
        else:
            record(WARN, "Systemd watchdog nie je nakonfigurovaný",
                   "Pridaj WatchdogSec=60 do unit súboru a sdnotify do kódu")
    except Exception:
        record(WARN, "Watchdog test – nedá sa parsovať hodnota", out)


def test_linger_enabled():
    """User linger musí byť zapnutý aby service bežala bez prihlásenia."""
    user = os.environ.get("USER", "")
    if not user:
        record(WARN, "Linger test – nedá sa zistiť username")
        return
    rc, out, _ = run(f"loginctl show-user {user} --property=Linger")
    if rc != 0:
        record(WARN, "Linger test – nedá sa overiť", out)
        return
    if "Linger=yes" in out:
        record(PASS, f"User linger je zapnutý pre {user}")
    else:
        record(FAIL, f"User linger je VYPNUTÝ pre {user}",
               f"Spusti: loginctl enable-linger {user}")


def test_stats_server_responds():
    """Flask dashboard server musí odpovedať na HTTP GET /api/stats do 5 sekúnd."""
    try:
        with urllib.request.urlopen(STATS_URL, timeout=HTTP_TIMEOUT_S) as resp:
            if resp.status == 200:
                record(PASS, f"Flask dashboard server odpovedá (HTTP {resp.status})")
            else:
                record(FAIL, f"Flask dashboard server vrátil HTTP {resp.status}")
    except urllib.error.URLError as e:
        record(FAIL, "Flask dashboard server neodpovedá", str(e))
    except Exception as e:
        record(FAIL, "Flask dashboard server – neočakávaná chyba", str(e))


def test_stats_server_html():
    """HTML dashboard musí byť dostupný na /."""
    try:
        with urllib.request.urlopen(STATS_HTML_URL, timeout=HTTP_TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8")
            if resp.status == 200 and "Audio Loop Dashboard" in body:
                record(PASS, "Stats HTML dashboard je dostupný")
            else:
                record(WARN,
                       "Stats HTML dashboard odpovedá ale obsah je neočakávaný")
    except Exception as e:
        record(FAIL, "Stats HTML dashboard neodpovedá", str(e))


def test_stats_json_valid():
    """JSON z /api/stats musi byt parsovatelny a obsahovat stats strukturu."""
    try:
        with urllib.request.urlopen(STATS_URL, timeout=HTTP_TIMEOUT_S) as resp:
            raw = resp.read().decode("utf-8")
        payload = json.loads(raw)
        data = payload.get("stats", payload)

        missing = []
        for i in range(1, 17):
            key = f"instrument_{i}"
            if key not in data:
                missing.append(key)
        for cmd in ["command_status", "command_stop", "command_quit"]:
            if cmd not in data:
                missing.append(cmd)

        if not missing:
            record(PASS, "Stats JSON ma spravnu strukturu")
        else:
            record(FAIL, "Stats JSON chybaju kluce", ", ".join(missing))

    except json.JSONDecodeError as e:
        record(FAIL, "Stats JSON nie je validny", str(e))
    except Exception as e:
        record(FAIL, "Stats JSON test zlyhal", str(e))


def test_stats_json_values_sane():
    """Hodnoty v stats musia byt nezaporne cele cisla."""
    try:
        with urllib.request.urlopen(STATS_URL, timeout=HTTP_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        data = payload.get("stats", payload)
        bad = {k: v for k, v in data.items()
               if not isinstance(v, int) or v < 0}
        if not bad:
            record(PASS, "Stats hodnoty su validne")
        else:
            record(FAIL, "Stats obsahuju nevalidne hodnoty", str(bad))
    except Exception as e:
        record(WARN, "Stats hodnoty sa nedaju overit", str(e))


def test_stats_server_concurrent():
    """Flask dashboard server musí zvládnuť 5 súčasných požiadaviek."""
    errors = []

    def fetch():
        try:
            with urllib.request.urlopen(STATS_URL, timeout=HTTP_TIMEOUT_S):
                pass
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=fetch) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=HTTP_TIMEOUT_S + 2)

    if not errors:
        record(PASS, "Flask dashboard server zvládol 5 súčasných požiadaviek")
    else:
        record(FAIL,
               f"Flask dashboard server zlyhal pri súčasných požiadavkách ({len(errors)}/5)",
               errors[0])


def test_no_critical_errors_in_log():
    """Critical errors log nesmie obsahovať ERROR záznamy."""
    if not os.path.exists(CRITICAL_LOG):
        record(INFO,
               "critical_errors.log neexistuje (žiadne chyby zapísané na disk – správne)")
        return
    try:
        with open(CRITICAL_LOG, "r") as f:
            lines = f.readlines()
        error_lines = [l for l in lines
                       if " - ERROR - " in l or " - CRITICAL - " in l]
        if not error_lines:
            record(PASS, "critical_errors.log neobsahuje žiadne ERROR záznamy")
        elif len(error_lines) <= 3:
            record(WARN,
                   f"critical_errors.log obsahuje {len(error_lines)} ERROR záznam(ov)",
                   error_lines[-1].strip())
        else:
            record(FAIL,
                   f"critical_errors.log obsahuje {len(error_lines)} ERROR záznamov",
                   error_lines[-1].strip())
    except Exception as e:
        record(WARN, "Nedá sa prečítať critical_errors.log", str(e))


def test_no_errors_in_journald():
    """Journald nesmie obsahovať ERROR záznamy za posledných 60 minút."""
    rc, out, _ = run(
        f'journalctl --user -u {SERVICE_NAME} --no-pager -p err '
        f'--since "1 hour ago" --output=short'
    )
    if rc != 0:
        record(WARN, "Nedá sa prečítať journald", out)
        return
    lines = [l for l in out.splitlines() if l.strip()]
    if not lines:
        record(PASS, "Journald: žiadne ERROR záznamy za posledných 60 minút")
    elif len(lines) <= 3:
        record(WARN,
               f"Journald: {len(lines)} ERROR záznam(ov) za posl. 60 min",
               lines[-1])
    else:
        record(FAIL,
               f"Journald: {len(lines)} ERROR záznamov za posl. 60 min",
               lines[-1])


def test_log_file_size():
    """Log súbor nesmie byť príliš veľký (blízko rotačného limitu 5MB)."""
    if not os.path.exists(CRITICAL_LOG):
        record(INFO, "critical_errors.log neexistuje – žiadne chyby na disku")
        return
    size_mb = os.path.getsize(CRITICAL_LOG) / (1024 * 1024)
    if size_mb < MAX_LOG_SIZE_MB:
        record(PASS, f"Log súbor: {size_mb:.2f} MB (limit: 5 MB)")
    else:
        record(WARN,
               f"Log súbor: {size_mb:.2f} MB – blíži sa k rotačnému limitu",
               "Zvýšený počet chýb – skontroluj obsah logu")


def test_stats_file_valid():
    """stats.json musí existovať a byť validný JSON."""
    if not os.path.exists(STATS_FILE):
        record(WARN, "stats.json neexistuje",
               "Zatiaľ žiadna aktivita alebo ešte nebol uložený (prvých 5 minút)")
        return
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
        record(PASS, f"stats.json je validný JSON ({len(data)} kľúčov)")
    except json.JSONDecodeError as e:
        record(FAIL, "stats.json je poškodený (nevalidný JSON)", str(e))
    except Exception as e:
        record(FAIL, "stats.json – chyba pri čítaní", str(e))


def test_config_valid():
    """config.json musí existovať, byť validný a obsahovať povinné kľúče."""
    if not os.path.exists(CONFIG_PATH):
        record(FAIL, "config.json neexistuje", f"Očakávaná cesta: {CONFIG_PATH}")
        return
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        record(FAIL, "config.json je nevalidný JSON", str(e))
        return

    required_keys = ["inputs", "outputs", "modbus_panel", "timeouts", "jack", "web", "song_rotation"]
    missing = [k for k in required_keys if k not in cfg]
    if missing:
        record(FAIL, "config.json chýbajú povinné kľúče", ", ".join(missing))
        return

    t = cfg.get("timeouts", {})
    warnings = []
    if t.get("global_timeout", 0) <= t.get("instrument_timeout", 0):
        warnings.append("global_timeout by mal byť väčší ako instrument_timeout")
    if t.get("fade_duration", 0) <= 0:
        warnings.append("fade_duration musí byť > 0")

    if warnings:
        record(WARN, "config.json – logické varovania", " | ".join(warnings))
    else:
        record(PASS, "config.json je validný a obsahuje všetky povinné kľúče")


def test_audio_files_exist():
    """Song foldery musia existovať a obsahovať WAV súbory."""
    if not os.path.exists(CONFIG_PATH):
        record(WARN, "Audio files test preskočený – config.json chýba")
        return

    with open(CONFIG_PATH) as f:
        cfg = json.load(f)

    song_cfg = cfg.get("song_rotation", {})
    base_dir = song_cfg.get("base_directory", "audio_files")
    song_folders = song_cfg.get("song_folders", [])

    if not song_folders:
        record(WARN, "Žiadne song_folders v config.json")
        return

    all_ok = True
    details = []

    for song in song_folders:
        path = os.path.join(PROJECT_ROOT, base_dir, song)
        if not os.path.exists(path):
            details.append(f"❌ {song}: adresár neexistuje")
            all_ok = False
            continue
        wavs = [f for f in os.listdir(path) if f.endswith(".wav")]
        if not wavs:
            details.append(f"❌ {song}: žiadne WAV súbory")
            all_ok = False
        else:
            numbered = sorted(
                [f for f in wavs if f.replace(".wav", "").isdigit()]
            )
            details.append(f"✅ {song}: {len(numbered)} WAV súborov")

    if all_ok:
        record(PASS, "Všetky song foldery existujú a obsahujú WAV súbory",
               " | ".join(details))
    else:
        record(FAIL,
               "Niektoré song foldery chýbajú alebo nemajú WAV súbory",
               " | ".join(details))


def test_ram_usage():
    """Service proces nesmie zaberať viac ako MAX_RAM_MB MB RAM."""
    rc, out, _ = run(
        f"systemctl --user show {SERVICE_NAME} --property=MainPID"
    )
    if rc != 0 or "=" not in out:
        record(WARN, "RAM test – nedá sa zistiť PID service")
        return
    pid = out.split("=")[1].strip()
    if not pid or pid == "0":
        record(WARN, "RAM test – service PID je 0 (service možno nebeží)")
        return

    rc2, mem_out, _ = run(f"cat /proc/{pid}/status")
    if rc2 != 0:
        record(WARN, f"RAM test – nedá sa prečítať /proc/{pid}/status")
        return

    try:
        for line in mem_out.splitlines():
            if line.startswith("VmRSS:"):
                kb = int(line.split()[1])
                mb = kb / 1024
                if mb <= MAX_RAM_MB:
                    record(PASS,
                           f"RAM použitie: {mb:.1f} MB (limit: {MAX_RAM_MB} MB)")
                else:
                    record(FAIL,
                           f"RAM použitie: {mb:.1f} MB – prekročený limit {MAX_RAM_MB} MB")
                return
        record(WARN, "RAM test – VmRSS nenájdené v /proc/status")
    except Exception as e:
        record(WARN, "RAM test – chyba pri parsovaní", str(e))


def test_cpu_usage():
    """Service nesmie zaťažovať CPU viac ako MAX_CPU_PERCENT % v idle stave.
    Meria sa 3 sekundy."""
    rc, out, _ = run(
        f"systemctl --user show {SERVICE_NAME} --property=MainPID"
    )
    if rc != 0 or "=" not in out:
        record(WARN, "CPU test – nedá sa zistiť PID service")
        return
    pid = out.split("=")[1].strip()
    if not pid or pid == "0":
        record(WARN, "CPU test – service PID je 0")
        return

    def get_cpu_time(p):
        try:
            with open(f"/proc/{p}/stat") as f:
                fields = f.read().split()
            return int(fields[13]) + int(fields[14])  # utime + stime
        except Exception:
            return None

    def get_total_cpu():
        try:
            with open("/proc/stat") as f:
                line = f.readline()
            vals = list(map(int, line.split()[1:]))
            return sum(vals)
        except Exception:
            return None

    t1_proc  = get_cpu_time(pid)
    t1_total = get_total_cpu()
    time.sleep(3)
    t2_proc  = get_cpu_time(pid)
    t2_total = get_total_cpu()

    if None in (t1_proc, t1_total, t2_proc, t2_total):
        record(WARN, "CPU test – nedá sa vypočítať CPU usage")
        return

    try:
        delta_total = t2_total - t1_total
        if delta_total == 0:
            record(WARN, "CPU test – žiadna zmena v celkovom CPU čase")
            return
        cpu_pct = 100.0 * (t2_proc - t1_proc) / delta_total
        rc2, nproc, _ = run("nproc")
        cores = int(nproc) if rc2 == 0 and nproc.isdigit() else 4
        cpu_pct_single = cpu_pct * cores

        if cpu_pct_single <= MAX_CPU_PERCENT:
            record(PASS,
                   f"CPU idle usage: {cpu_pct_single:.1f}% (limit: {MAX_CPU_PERCENT}%)")
        else:
            record(WARN,
                   f"CPU idle usage: {cpu_pct_single:.1f}% – vyššie ako očakávané",
                   "Skontroluj či nie je aktívny playback alebo iný proces")
    except Exception as e:
        record(WARN, "CPU test – chyba pri výpočte", str(e))


def test_disk_space():
    """Na SD karte musí byť aspoň MIN_FREE_DISK_MB MB voľného miesta."""
    rc, out, _ = run("df / --output=avail -k | tail -1")
    if rc != 0:
        record(WARN, "Disk test – nedá sa zistiť voľné miesto")
        return
    try:
        free_mb = int(out.strip()) / 1024
        if free_mb >= MIN_FREE_DISK_MB:
            record(PASS,
                   f"Voľné miesto na SD: {free_mb:.0f} MB (minimum: {MIN_FREE_DISK_MB} MB)")
        else:
            record(FAIL,
                   f"Voľné miesto na SD: {free_mb:.0f} MB – KRITICKY MÁLO",
                   "Hrozí poškodenie stats.json alebo logov pri zápise")
    except Exception as e:
        record(WARN, "Disk test – chyba pri parsovaní", str(e))


def test_service_restart_recovery():
    """Otestuje či sa service zotaví po manuálnom reštarte.
    POZOR: Krátkodobo preruší audio playback (~10 sekúnd)."""
    print()
    answer = input(
        "  ⚠️  Test restartu service (preruší audio ~10s). Pokračovať? [y/N]: "
    ).strip().lower()
    if answer != "y":
        record(INFO, "Restart test preskočený používateľom")
        return

    print("     Reštartujem service...")
    rc, _, err = run(f"systemctl --user restart {SERVICE_NAME}", timeout=30)
    if rc != 0:
        record(FAIL, "Restart service zlyhal", err)
        return

    for attempt in range(15):
        time.sleep(1)
        rc2, out2, _ = run(f"systemctl --user is-active {SERVICE_NAME}")
        if rc2 == 0 and out2 == "active":
            record(PASS, f"Service sa zotavila po reštarte ({attempt + 1}s)")
            time.sleep(2)
            try:
                with urllib.request.urlopen(STATS_URL, timeout=HTTP_TIMEOUT_S):
                    record(PASS, "Flask dashboard server odpovedá po reštarte")
            except Exception as e:
                record(FAIL, "Flask dashboard server neodpovedá po reštarte", str(e))
            return

    record(FAIL, "Service sa nezotavila do 15 sekúnd po reštarte",
           "Skontroluj: journalctl --user -u audio_looper.service --no-pager -n 30")


# ── Hlavná funkcia ────────────────────────────────────────────────────────────

def main():
    print()
    print("═" * 60)
    print("  Audio Looper System – Live System Test")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Project root: {PROJECT_ROOT}")
    print("═" * 60)

    # Overenie že service existuje (rc=4 = unit nenájdený)
    rc, _, _ = run(f"systemctl --user status {SERVICE_NAME} --no-pager")
    if rc == 4:
        print(f"\n❌  Service '{SERVICE_NAME}' neexistuje. Skontroluj inštaláciu.")
        sys.exit(1)

    section("1 / SERVICE STAV")
    test_service_active()
    test_service_not_failed()
    test_service_restart_count()
    test_service_watchdog_configured()
    test_linger_enabled()

    section("2 / STATS SERVER")
    test_stats_server_responds()
    test_stats_server_html()
    test_stats_json_valid()
    test_stats_json_values_sane()
    test_stats_server_concurrent()

    section("3 / LOGY A CHYBY")
    test_no_critical_errors_in_log()
    test_no_errors_in_journald()
    test_log_file_size()

    section("4 / SÚBORY A KONFIGURÁCIA")
    test_stats_file_valid()
    test_config_valid()
    test_audio_files_exist()

    section("5 / SYSTÉMOVÉ ZDROJE")
    test_ram_usage()
    print("     (CPU meranie trvá 3 sekundy...)")
    test_cpu_usage()
    test_disk_space()

    section("6 / RECOVERY TEST")
    test_service_restart_recovery()

    # ── Súhrn ────────────────────────────────────────────────────────────────
    print()
    print("═" * 60)
    print("  SÚHRN VÝSLEDKOV")
    print("═" * 60)

    passed = [r for r in results if r[0] == PASS]
    failed = [r for r in results if r[0] == FAIL]
    warned = [r for r in results if r[0] == WARN]
    infos  = [r for r in results if r[0] == INFO]

    print(f"  ✅  PASS : {len(passed)}")
    print(f"  ❌  FAIL : {len(failed)}")
    print(f"  ⚠️   WARN : {len(warned)}")
    print(f"  ℹ️   INFO : {len(infos)}")

    if failed:
        print()
        print("  Zlyhané testy:")
        for _, name, detail in failed:
            print(f"    ❌  {name}")
            if detail:
                print(f"         → {detail}")

    if warned:
        print()
        print("  Varovania:")
        for _, name, detail in warned:
            print(f"    ⚠️   {name}")
            if detail:
                print(f"         → {detail}")

    print()
    if not failed:
        print("  🎉  Systém je v PORIADKU a pripravený na prevádzku.")
    else:
        print("  🔴  Systém má KRITICKÉ PROBLÉMY. Neinštaluj do múzea bez opravy.")
    print("═" * 60)
    print()

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()