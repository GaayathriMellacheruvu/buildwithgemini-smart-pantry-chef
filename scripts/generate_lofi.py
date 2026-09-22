import math
import struct
import wave
import numpy as np

SAMPLE_RATE = 44100
DURATION = 35.0  # seconds
BPM = 85
BEAT_DUR = 60.0 / BPM
BAR_DUR = BEAT_DUR * 4

# Frequency table (Hz)
NOTES = {
    'C3': 130.81, 'D3': 146.83, 'E3': 164.81, 'F3': 174.61, 'G3': 196.00, 'A3': 220.00, 'B3': 246.94,
    'C4': 261.63, 'D4': 293.66, 'E4': 329.63, 'F4': 349.23, 'G4': 392.00, 'A4': 440.00, 'B4': 493.88,
    'C5': 523.25, 'E5': 659.25,
}

# Lo-Fi Chord Progression: Fmaj7 -> Em7 -> Dm7 -> Cmaj7
CHORDS = [
    [NOTES['F3'], NOTES['A3'], NOTES['C4'], NOTES['E4']],
    [NOTES['E3'], NOTES['G3'], NOTES['B3'], NOTES['D4']],
    [NOTES['D3'], NOTES['F3'], NOTES['A3'], NOTES['C4']],
    [NOTES['C3'], NOTES['E3'], NOTES['G3'], NOTES['B4']],
]

BASS_NOTES = [NOTES['F3']/2, NOTES['E3']/2, NOTES['D3']/2, NOTES['C3']/2]

num_samples = int(SAMPLE_RATE * DURATION)
audio = np.zeros(num_samples, dtype=np.float32)

t_arr = np.linspace(0, DURATION, num_samples, endpoint=False)

# 1. Vinyl Hiss Background (subtle lo-fi warmth)
noise = np.random.uniform(-0.015, 0.015, num_samples)
# Low-pass filter for soft vinyl noise
for i in range(1, num_samples):
    noise[i] = 0.92 * noise[i-1] + 0.08 * noise[i]
audio += noise * 0.4

# 2. Chord Progression & Rhodes Synth Pads
num_bars = int(math.ceil(DURATION / BAR_DUR))

for bar_idx in range(num_bars):
    chord = CHORDS[bar_idx % len(CHORDS)]
    bass_freq = BASS_NOTES[bar_idx % len(BASS_NOTES)]
    
    start_sec = bar_idx * BAR_DUR
    end_sec = min((bar_idx + 1) * BAR_DUR, DURATION)
    
    start_idx = int(start_sec * SAMPLE_RATE)
    end_idx = int(end_sec * SAMPLE_RATE)
    bar_samples = end_idx - start_idx
    if bar_samples <= 0:
        continue
        
    t = t_arr[start_idx:end_idx] - start_sec
    
    # Soft ADSR Envelope for Rhodes chords
    env = np.ones(bar_samples, dtype=np.float32)
    attack = int(0.1 * SAMPLE_RATE)
    release = int(0.4 * SAMPLE_RATE)
    if attack < bar_samples:
        env[:attack] = np.linspace(0, 1, attack)
    if release < bar_samples:
        env[-release:] = np.linspace(1, 0, release)
        
    # Synthesize electric piano chords
    chord_wave = np.zeros(bar_samples, dtype=np.float32)
    for freq in chord:
        # Sine fundamental + soft 2nd harmonic (warm Rhodes sound)
        wave_freq = np.sin(2 * np.pi * freq * t) * 0.7 + np.sin(2 * np.pi * freq * 2 * t) * 0.2
        chord_wave += wave_freq
    chord_wave *= (0.15 / len(chord)) * env
    audio[start_idx:end_idx] += chord_wave

    # Synthesize warm sub-bass
    bass_wave = np.sin(2 * np.pi * bass_freq * t) * 0.25 * env
    audio[start_idx:end_idx] += bass_wave

# 3. Lo-Fi Drums (Kick, Snare/Snap, Hi-Hat)
num_beats = int(DURATION / BEAT_DUR)

for b in range(num_beats):
    beat_sec = b * BEAT_DUR
    beat_idx = int(beat_sec * SAMPLE_RATE)
    beat_in_bar = b % 4
    
    # Kick drum on beats 1 and 3 (and syncopated 3.5)
    if beat_in_bar in [0, 2] or (b % 8 == 5):
        k_dur = int(0.18 * SAMPLE_RATE)
        k_end = min(beat_idx + k_dur, num_samples)
        k_samples = k_end - beat_idx
        if k_samples > 0:
            k_t = np.linspace(0, 0.18, k_samples)
            # Pitch drop sine for kick
            freq_env = 140 * np.exp(-35 * k_t)
            phase = 2 * np.pi * np.cumsum(freq_env) / SAMPLE_RATE
            amp_env = np.exp(-12 * k_t)
            audio[beat_idx:k_end] += (np.sin(phase) * amp_env * 0.35).astype(np.float32)
            
    # Snare / rimshot on beats 2 and 4
    if beat_in_bar in [1, 3]:
        s_dur = int(0.15 * SAMPLE_RATE)
        s_end = min(beat_idx + s_dur, num_samples)
        s_samples = s_end - beat_idx
        if s_samples > 0:
            s_t = np.linspace(0, 0.15, s_samples)
            snare_noise = np.random.uniform(-1, 1, s_samples) * np.exp(-25 * s_t)
            snare_tone = np.sin(2 * np.pi * 180 * s_t) * np.exp(-30 * s_t)
            audio[beat_idx:s_end] += ((snare_noise * 0.18 + snare_tone * 0.15)).astype(np.float32)

    # Hi-hats on every 8th note
    for h_sub in [0, 0.5]:
        h_sec = (b + h_sub) * BEAT_DUR
        h_idx = int(h_sec * SAMPLE_RATE)
        h_dur = int(0.04 * SAMPLE_RATE)
        h_end = min(h_idx + h_dur, num_samples)
        h_samples = h_end - h_idx
        if h_samples > 0:
            h_t = np.linspace(0, 0.04, h_samples)
            hat_noise = np.random.uniform(-1, 1, h_samples) * np.exp(-60 * h_t)
            audio[h_idx:h_end] += (hat_noise * 0.06).astype(np.float32)

# Normalize and export WAV
max_val = np.max(np.abs(audio))
if max_val > 0:
    audio = audio / max_val * 0.85

out_path = "/config/.gemini/antigravity/scratch/smart-pantry-chef/videos/lofi_beat.wav"
with wave.open(out_path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    pcm_data = (audio * 32767).astype(np.int16).tobytes()
    wf.writeframes(pcm_data)

print(f"Synthesized upbeat lo-fi track: {out_path} ({DURATION}s)")
