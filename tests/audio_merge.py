import tkinter as tk
from tkinter import filedialog
import soundfile as sf
import numpy as np

def mix_audio_files():
    # výber súborov
    file_paths = filedialog.askopenfilenames(
        title="Vyber WAV súbory",
        filetypes=[("WAV súbory", "*.wav")]
    )
    if not file_paths:
        print("Žiadne súbory neboli vybrané.")
        return

    data_list = []
    samplerate = None
    target_channels = 2  # budeme miešať všetko ako stereo

    for path in file_paths:
        data, sr = sf.read(path, dtype='float32')
        if samplerate is None:
            samplerate = sr
        elif sr != samplerate:
            print(f"Chyba: rôzne sample rate v súboroch ({sr} vs {samplerate})")
            return

        # ak je mono, spravíme stereo (duplikujeme kanál)
        if data.ndim == 1:
            data = np.stack([data, data], axis=-1)

        # ak je viac ako 2 kanály, vezmeme len prvé dva
        if data.shape[1] > 2:
            data = data[:, :2]

        data_list.append(data)

    # zabezpečíme rovnakú dĺžku
    min_len = min(d.shape[0] for d in data_list)
    data_list = [d[:min_len] for d in data_list]

    # skombinujeme všetky stopy
    mixed = np.sum(data_list, axis=0)

    # normalizácia
    mixed /= np.max(np.abs(mixed))

    # uloženie
    output_path = filedialog.asksaveasfilename(
        title="Ulož výsledný mix",
        defaultextension=".wav",
        filetypes=[("WAV súbory", "*.wav")]
    )
    if output_path:
        sf.write(output_path, mixed, samplerate)
        print(f"Hotovo! Uložené ako {output_path}")

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    mix_audio_files()
