#!/usr/bin/env python3
"""
mix_audio.py

Zmixuje (overlay - na seba, nie za sebou) všetky .wav súbory v priečinku,
kde je tento skript spustený, a uloží výsledok do podpriečinka 'merged/'
ako Merged1.wav, Merged2.wav, atď. (číslo sa vždy automaticky zvýši,
takže nič neprepíše predošlé výsledky).

Použitie:
    1. Skopíruj tento skript do priečinka so .wav súbormi
       (alebo ho spusti odkiaľkoľvek a zadaj cestu ako argument)
    2. Spusti: python mix_audio.py
       alebo:  python mix_audio.py /cesta/k/priecinku

Vyžaduje iba: numpy (pip install numpy)
Nepotrebuje pydub ani ffmpeg - funguje aj na Python 3.13.
"""

import sys
import wave
from pathlib import Path
import numpy as np


def read_wav(path: Path):
    """Načíta WAV súbor a vráti (samples ako float64 numpy array [n_frames, n_channels], sample_rate, sampwidth)."""
    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sampwidth == 3:
        # 24-bit WAV nemá priamy numpy dtype - každá vzorka sú 3 bajty (little-endian, signed)
        raw_bytes = np.frombuffer(raw, dtype=np.uint8)
        n_samples = len(raw_bytes) // 3
        raw_bytes = raw_bytes[: n_samples * 3].reshape(-1, 3)
        # doplníme štvrtý bajt (sign extension) a interpretujeme ako int32
        padded = np.zeros((n_samples, 4), dtype=np.uint8)
        padded[:, :3] = raw_bytes
        # ak je najvyšší bit (znamienko) nastavený, horný bajt musí byť 0xFF (sign extend)
        sign_bit = (raw_bytes[:, 2] & 0x80) != 0
        padded[sign_bit, 3] = 0xFF
        data = padded.view(np.int32).flatten().astype(np.float64)
    else:
        dtype_map = {1: np.uint8, 2: np.int16, 4: np.int32}
        if sampwidth not in dtype_map:
            raise ValueError(f"Nepodporovaná bitová hĺbka ({sampwidth*8}-bit) v súbore {path.name}")

        dtype = dtype_map[sampwidth]
        data = np.frombuffer(raw, dtype=dtype).astype(np.float64)

        if sampwidth == 1:
            # 8-bit WAV je unsigned, stred je 128
            data = data - 128.0

    if n_channels > 1:
        data = data.reshape(-1, n_channels)
    else:
        data = data.reshape(-1, 1)

    return data, framerate, sampwidth, n_channels


def write_wav(path: Path, data: np.ndarray, framerate: int, sampwidth: int, n_channels: int):
    if sampwidth == 3:
        min_val, max_val = -8388608, 8388607
        out = np.clip(data, min_val, max_val).astype(np.int32)
        # zoberieme spodné 3 bajty z každého int32 vzorky (little-endian)
        as_bytes = out.view(np.uint8).reshape(-1, 4)[:, :3]
        frames_bytes = as_bytes.tobytes()
    else:
        dtype_map = {
            1: (np.uint8, 0, 255),
            2: (np.int16, -32768, 32767),
            4: (np.int32, -2147483648, 2147483647),
        }
        dtype, min_val, max_val = dtype_map[sampwidth]

        if sampwidth == 1:
            data = data + 128.0

        out = np.clip(data, min_val, max_val).astype(dtype)
        frames_bytes = out.tobytes()

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        wf.writeframes(frames_bytes)


def find_next_merged_number(output_dir: Path) -> int:
    """Nájde najvyššie číslo MergedN.wav v priečinku a vráti N+1."""
    existing = list(output_dir.glob("Merged*.wav"))
    max_num = 0
    for f in existing:
        name = f.stem.replace("Merged", "")
        if name.isdigit():
            max_num = max(max_num, int(name))
    return max_num + 1


def mix_wav_files(input_dir: Path) -> Path:
    wav_files = sorted(input_dir.glob("*.wav"))

    if not wav_files:
        print(f"V priečinku '{input_dir}' som nenašiel žiadne .wav súbory.")
        sys.exit(1)

    print(f"Našiel som {len(wav_files)} .wav súborov:")
    for f in wav_files:
        print(f"  - {f.name}")

    print("\nNačítavam a mixujem (overlay)...")

    loaded = []
    ref_rate = None
    ref_width = None
    ref_channels = None
    bit_depth_max = {1: 127.0, 2: 32767.0, 3: 8388607.0, 4: 2147483647.0}

    for f in wav_files:
        data, rate, width, channels = read_wav(f)

        if ref_rate is None:
            ref_rate, ref_width, ref_channels = rate, width, channels
        else:
            if rate != ref_rate:
                print(f"  UPOZORNENIE: '{f.name}' má inú vzorkovaciu frekvenciu "
                      f"({rate} Hz vs. {ref_rate} Hz). Môže to spôsobiť rozladenie rýchlosti/výšky.")
            if channels != ref_channels:
                # zjednotíme počet kanálov - mono sa zduplikuje na stereo, stereo sa zmixuje na mono
                if channels == 1 and ref_channels == 2:
                    data = np.repeat(data, 2, axis=1)
                elif channels == 2 and ref_channels == 1:
                    data = data.mean(axis=1, keepdims=True)
            if width != ref_width:
                # preškálujeme na rovnakú bitovú hĺbku ako referenčný (prvý) súbor
                print(f"  UPOZORNENIE: '{f.name}' má inú bitovú hĺbku ({width*8}-bit vs. {ref_width*8}-bit). "
                      f"Preškálovávam, aby hlasitosti sedeli.")
                data = data * (bit_depth_max[ref_width] / bit_depth_max[width])

        loaded.append(data)

    max_len = max(d.shape[0] for d in loaded)
    n_channels = ref_channels

    mix = np.zeros((max_len, n_channels), dtype=np.float64)
    for data in loaded:
        padded = np.zeros((max_len, n_channels), dtype=np.float64)
        padded[: data.shape[0], :] = data
        mix += padded

    # Normalizácia, aby výsledok neklipoval pri skladaní viacerých stôp naraz
    dtype_max = {1: 127.0, 2: 32767.0, 3: 8388607.0, 4: 2147483647.0}[ref_width]
    peak = np.max(np.abs(mix))
    if peak > dtype_max:
        mix = mix * (dtype_max / peak)
        print(f"  (Hlasitosť bola automaticky znížená, aby výsledok neklipoval - bol by {peak/dtype_max:.1f}x hlasnejší ako max.)")

    output_dir = input_dir / "merged"
    output_dir.mkdir(exist_ok=True)

    next_num = find_next_merged_number(output_dir)
    output_path = output_dir / f"Merged{next_num}.wav"

    write_wav(output_path, mix, ref_rate, ref_width, n_channels)
    print(f"\nHotovo! Uložené ako: {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1]).expanduser().resolve()
    else:
        target_dir = Path(__file__).parent.resolve()

    if not target_dir.is_dir():
        print(f"Priečinok '{target_dir}' neexistuje.")
        sys.exit(1)

    mix_wav_files(target_dir)