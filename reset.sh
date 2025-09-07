#!/bin/bash

# ==============================================================
# Robustný Reset služby Audio Looper
# ==============================================================

# Nechaj skript pokračovať aj pri chybe, aby bolo možné proces "killnúť"
set +e

SERVICE_NAME="audio_looper.service"

echo "Spúšťam robustný reset služby: $SERVICE_NAME"

# Krok 1: Pokus o zastavenie služby
if systemctl --user is-active --quiet $SERVICE_NAME; then
    echo "Služba je aktívna. Pokúšam sa ju zastaviť..."
    systemctl --user stop $SERVICE_NAME
    sleep 1 # Pauza na korektné ukončenie
fi

# Krok 2: Overenie, či sa proces zastavil, a prípadné násilné ukončenie
if systemctl --user is-active --quiet $SERVICE_NAME; then
    echo "UPOZORNENIE: Služba stále beží po pokuse o zastavenie. Násilne ukončujem proces."
    # Nájdenie PID a jeho násilné ukončenie
    PID=$(pgrep -f "python3 /home/admin/Documents/audio-loop-system/main.py")
    if [ ! -z "$PID" ]; then
        echo "Nájdený PID: $PID. Posielam príkaz SIGKILL."
        kill -9 "$PID"
    else
        echo "Nenašiel som bežiaci proces, pokračujem ďalej."
    fi
fi

# Krátka pauza na uvoľnenie zdrojov
sleep 2

# Krok 3: Kontrola, či je služba naozaj neaktívna
if systemctl --user is-active --quiet $SERVICE_NAME; then
    echo "CHYBA: Službu sa nepodarilo ukončiť. Prosím, skontrolujte logy ručne."
    exit 1
fi

echo "Služba bola úspešne ukončená."

# Krok 4: Spustenie služby
echo "Spúšťam službu znovu..."
set -e
systemctl --user start $SERVICE_NAME

# Krok 5: Krátka pauza a overenie stavu
sleep 1
echo ""
echo "=== STATUS SLUŽBY PO REŠTARTE ==="
if systemctl --user is-active --quiet $SERVICE_NAME; then
    echo "ÚSPECH: Služba je aktívna."
else
    echo "CHYBA: Služba nie je aktívna!"
    echo "Prosím, skontrolujte logy pre viac informácií."
fi

echo ""
echo "=== POSLEDNÉ LOGY === (pre diagnostiku)"
journalctl --user -u $SERVICE_NAME --no-pager --lines=20