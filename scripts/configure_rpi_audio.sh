#!/bin/bash
set -uo pipefail

VOLUME_PERCENT="${AUDIO_LOOP_VOLUME_PERCENT:-95}"
CONFIGURE_OUTPUT=1
CONFIGURE_VOLUME=1
REQUIRE_RPI=1
USE_SUDO=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install)
            CONFIGURE_OUTPUT=1
            CONFIGURE_VOLUME=1
            REQUIRE_RPI=1
            USE_SUDO=1
            ;;
        --volume-only)
            CONFIGURE_OUTPUT=0
            CONFIGURE_VOLUME=1
            REQUIRE_RPI=0
            USE_SUDO=0
            ;;
        --volume)
            if [[ $# -gt 1 ]]; then
                shift
                VOLUME_PERCENT="$1"
            else
                VOLUME_PERCENT=95
            fi
            ;;
        *)
            echo "Unknown audio setup option: $1"
            exit 0
            ;;
    esac
    shift
done

normalise_volume_percent() {
    if ! [[ "$VOLUME_PERCENT" =~ ^[0-9]+$ ]]; then
        echo "Invalid AUDIO_LOOP_VOLUME_PERCENT='$VOLUME_PERCENT', using 95."
        VOLUME_PERCENT=95
    fi

    if (( VOLUME_PERCENT > 100 )); then
        VOLUME_PERCENT=100
    elif (( VOLUME_PERCENT < 0 )); then
        VOLUME_PERCENT=0
    fi
}

is_raspberry_pi() {
    [[ -r /proc/device-tree/model ]] \
        && tr -d '\0' < /proc/device-tree/model | grep -qi "Raspberry Pi"
}

run_privileged() {
    if [[ "$USE_SUDO" != "1" || "$(id -u)" -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        return 1
    fi
}

run_amixer() {
    if [[ "$USE_SUDO" == "1" ]]; then
        run_privileged amixer -q "$@" >/dev/null 2>&1
    else
        amixer -q "$@" >/dev/null 2>&1
    fi
}

configure_headphone_output() {
    local changed=1

    echo "Configuring Raspberry Pi audio output for the 3.5mm headphones jack..."

    if command -v raspi-config >/dev/null 2>&1; then
        if run_privileged raspi-config nonint do_audio 1 >/dev/null 2>&1; then
            echo "Audio route set to headphones/jack via raspi-config."
            changed=0
        else
            echo "Warning: raspi-config could not force headphones/jack output."
        fi
    fi

    if command -v amixer >/dev/null 2>&1; then
        if run_privileged amixer -q cset numid=3 1 >/dev/null 2>&1; then
            echo "Audio route set to headphones/jack via ALSA fallback."
            changed=0
        fi
    fi

    if [[ "$changed" -ne 0 ]]; then
        echo "Warning: could not confirm forced headphones/jack output on this OS."
    fi
}

set_alsa_volume() {
    local changed=1
    local control

    if ! command -v amixer >/dev/null 2>&1; then
        return 1
    fi

    for control in Master PCM Headphone Speaker; do
        if run_amixer sset "$control" "${VOLUME_PERCENT}%" unmute \
            || run_amixer sset "$control" "${VOLUME_PERCENT}%"; then
            changed=0
        fi

        if run_amixer -c 0 sset "$control" "${VOLUME_PERCENT}%" unmute \
            || run_amixer -c 0 sset "$control" "${VOLUME_PERCENT}%"; then
            changed=0
        fi
    done

    return "$changed"
}

set_user_audio_server_volume() {
    local changed=1
    local wp_volume="0.95"

    if (( VOLUME_PERCENT >= 100 )); then
        wp_volume="1.0"
    else
        printf -v wp_volume "0.%02d" "$VOLUME_PERCENT"
    fi

    if command -v pactl >/dev/null 2>&1; then
        if pactl set-sink-volume @DEFAULT_SINK@ "${VOLUME_PERCENT}%" >/dev/null 2>&1; then
            changed=0
        fi
        pactl set-sink-mute @DEFAULT_SINK@ 0 >/dev/null 2>&1 || true
    fi

    if command -v wpctl >/dev/null 2>&1; then
        if wpctl set-volume @DEFAULT_AUDIO_SINK@ "${VOLUME_PERCENT}%" >/dev/null 2>&1 \
            || wpctl set-volume @DEFAULT_AUDIO_SINK@ "$wp_volume" >/dev/null 2>&1; then
            changed=0
        fi
        wpctl set-mute @DEFAULT_AUDIO_SINK@ 0 >/dev/null 2>&1 || true
    fi

    return "$changed"
}

set_audio_volume() {
    local changed=1

    echo "Setting system audio output volume to ${VOLUME_PERCENT}%..."

    if set_alsa_volume; then
        changed=0
    fi

    if set_user_audio_server_volume; then
        changed=0
    fi

    if [[ "$changed" -eq 0 ]]; then
        if [[ "$USE_SUDO" == "1" ]] && command -v alsactl >/dev/null 2>&1; then
            run_privileged alsactl store >/dev/null 2>&1 || true
        fi
        echo "Audio output volume set to ${VOLUME_PERCENT}% where supported."
    else
        echo "Warning: no supported mixer accepted the ${VOLUME_PERCENT}% volume setting."
    fi
}

normalise_volume_percent

if [[ "$REQUIRE_RPI" == "1" ]] && ! is_raspberry_pi; then
    echo "Not running on a Raspberry Pi; skipping Raspberry Pi audio routing."
    exit 0
fi

if [[ "$CONFIGURE_OUTPUT" == "1" ]]; then
    configure_headphone_output
fi

if [[ "$CONFIGURE_VOLUME" == "1" ]]; then
    set_audio_volume
fi

exit 0
