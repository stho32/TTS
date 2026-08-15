#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "openai>=1.40.0",
#   "pygame>=2.6.0",
# ]
# ///

"""
TTS-Player fuer Linux mit Tkinter-GUI: wandelt Text ueber die OpenAI-TTS-API in
Sprache um, spielt sie abschnittsweise ab und kann das Ergebnis als WAV exportieren.
Audio-Backend: ausschliesslich pygame.

Anforderungen: siehe ../Anforderungen/R00002-tts-player-linux.md
"""

import argparse
import logging
import os
import sys
import threading
import queue
import tempfile
import shutil
import wave
import re
import time
import uuid
import random
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from typing import List, Tuple

# pygame for audio playback on Linux
PYGAME_IMPORT_ERROR = None
try:
    import pygame  # type: ignore
except Exception as _e:
    PYGAME_IMPORT_ERROR = _e
    pygame = None  # type: ignore

# OpenAI SDK
OPENAI_IMPORT_ERROR = None
try:
    # Prefer the modern SDK import
    from openai import OpenAI
except Exception as e:
    OPENAI_IMPORT_ERROR = e
    OpenAI = None  # type: ignore

APP_TITLE = "TTS Player (OpenAI) - Linux"
DEFAULT_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "alloy"
SUPPORTED_VOICES = [
    # Voices supported by OpenAI TTS as per API error message
    "alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral", "verse", "ballad", "ash", "sage"
]
CHARS_PER_CHUNK = 800  # kleinere Standardgröße für feinere Abschnitte; in der UI anpassbar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="TTS-Player fuer Linux mit OpenAI-TTS-API und Tkinter-GUI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug-Logging aktivieren")
    return parser.parse_args()


def safe_showerror(title: str, message: str):
    try:
        messagebox.showerror(title, message)
    except Exception:
        print(f"ERROR - {title}: {message}")


def split_text_to_chunks(text: str, max_chars: int) -> list:
    """
    Splittet in kleinere, sinnvolle Abschnitte:
    - Trennt an 1..n Leerzeilen (auch mit Spaces/Tabs)
    - Trennt an Markdown-Überschriften (Zeilen beginnend mit 1..6 # + Space)
    - Innerhalb eines Blocks werden Sätze gepackt bis max_chars
    """
    text = text.strip()
    if not text:
        return []

    # Normalize newlines
    text = re.sub(r"\r\n?", "\n", text)

    lines = text.split("\n")
    heading_re = re.compile(r"^\s{0,3}#{1,6}\s+")

    blocks = []
    cur = []

    def flush_block():
        nonlocal cur
        content = "\n".join(cur).strip()
        if content:
            blocks.append(content)
        cur = []

    for line in lines:
        if heading_re.match(line):
            # New block at heading
            flush_block()
            blocks.append(line.strip())
        elif line.strip() == "":
            # Blank line => end of current block
            flush_block()
        else:
            cur.append(line)
    flush_block()

    # Sentence splitter
    sentence_sep = re.compile(r"""(?<=[.!?])[\)\]"'»“”’]*\s+""")

    def pack_sentences(text_block: str) -> list[str]:
        parts = sentence_sep.split(text_block.strip())
        parts = [p.strip() for p in parts if p.strip()]
        chunks = []
        buf = ""
        for s in parts:
            candidate = (buf + " " + s).strip() if buf else s
            if len(candidate) <= max_chars:
                buf = candidate
            else:
                if buf:
                    chunks.append(buf)
                if len(s) > max_chars:
                    start = 0
                    while start < len(s):
                        end = min(start + max_chars, len(s))
                        chunks.append(s[start:end])
                        start = end
                    buf = ""
                else:
                    buf = s
        if buf:
            chunks.append(buf)
        return chunks

    all_chunks = []
    for b in blocks:
        all_chunks.extend(pack_sentences(b))

    return all_chunks


class TTSWorker(threading.Thread):
    def __init__(self, ui_ref, client, model: str, voice: str, max_chars: int, randomize_voices: bool = True, voices: list[str] | None = None):
        super().__init__(daemon=True)
        self.ui = ui_ref
        self.client = client
        self.model = model
        self.voice = voice
        self.max_chars = max_chars
        self.randomize_voices = randomize_voices
        self.voices = voices or SUPPORTED_VOICES
        self.stop_event = threading.Event()
        self.skip_event = threading.Event()
        self.prev_event = threading.Event()
        self.pause_event = threading.Event()  # when set, playback is paused
        self.tasks = queue.Queue()  # holds text jobs
        self.temp_dir = tempfile.mkdtemp(prefix="tts_openai_")
        self.generated_wavs: List[str | None] = []  # parallel to chunks
        self.current_chunks: List[str] = []
        self.current_spans: List[Tuple[int, int]] = []  # (start,end) offsets in original text

    def log(self, msg: str):
        self.ui.log(msg)

    def run(self):
        try:
            self.log("Bereit.")
            while True:
                job = self.tasks.get()
                if job is None:
                    break
                text = job.get("text", "").strip()
                if not text:
                    self.log("Kein Text zum Vorlesen.")
                    continue
                # Prepare chunks and spans for highlighting and seeking
                self.current_chunks = split_text_to_chunks(text, self.max_chars)
                total = len(self.current_chunks)
                if total == 0:
                    self.log("Kein Inhalt nach Aufteilung gefunden.")
                    continue
                self.current_spans = self._compute_chunk_spans(text, self.current_chunks)
                self.generated_wavs = [None] * total
                self.ui.set_progress_max(total)
                self.ui.set_progress(0)
                self.log(f"Starte Synthese und Wiedergabe ({total} Abschnitte)...")

                i = 0
                while i < total:
                    if self.stop_event.is_set():
                        self.log("Abgebrochen.")
                        break

                    # Choose voice per chunk
                    voice_to_use = self.voice
                    if self.randomize_voices and self.voices:
                        try:
                            voice_to_use = random.choice(self.voices)
                        except Exception:
                            pass
                    self.log(f"Stimme für Abschnitt {i+1}: {voice_to_use}")

                    # Synthesize if needed
                    wav_path = self.generated_wavs[i]
                    if not wav_path or not os.path.exists(wav_path):
                        try:
                            wav_path = self._synthesize_chunk_to_wav(self.current_chunks[i], i+1, voice_to_use)
                            self.generated_wavs[i] = wav_path
                        except Exception as e:
                            self.log(f"Fehler bei Synthese von Abschnitt {i+1}: {e}")
                            self.log(traceback.format_exc())
                            break

                    # Highlight current span in UI
                    try:
                        s, e = self.current_spans[i]
                        self.ui.highlight_span(s, e)
                    except Exception:
                        pass

                    # Play with pause/seek handling
                    if self.stop_event.is_set():
                        break
                    try:
                        self._play_wav_blocking(wav_path)
                    except Exception as e:
                        self.log(f"Fehler bei Wiedergabe von Abschnitt {i+1}: {e}")
                        self.log(traceback.format_exc())
                        break

                    # Decide next index based on events
                    if self.stop_event.is_set():
                        break
                    if self.prev_event.is_set():
                        self.prev_event.clear()
                        i = max(0, i - 1)
                        self.ui.set_progress(i)
                        self.ui.set_status(f"Zurück zu Abschnitt {i+1}/{total}")
                        continue
                    # default progress forward; skip_event just accelerates move to next
                    self.ui.set_progress(i + 1)
                    self.ui.set_status(f"Abgespielt: {i+1}/{total}")
                    i += 1
                    if self.skip_event.is_set():
                        self.skip_event.clear()
                        # i already advanced; nothing else to do
                        continue

                self.ui.on_job_finished(not self.stop_event.is_set())
                self.stop_event.clear()
                self.skip_event.clear()
                self.prev_event.clear()
                self.pause_event.clear()

        except Exception as e:
            self.log(f"Unerwarteter Fehler im Worker: {e}")
            self.log(traceback.format_exc())
        finally:
            self.log("Worker beendet.")

    @staticmethod
    def _compute_chunk_spans(full_text: str, chunks: List[str]) -> List[Tuple[int, int]]:
        spans: List[Tuple[int, int]] = []
        # Normalize same as in split to ensure matching
        norm_text = re.sub(r"\r\n?", "\n", full_text)
        cursor = 0
        for ch in chunks:
            ch_norm = ch
            idx = norm_text.find(ch_norm, cursor)
            if idx == -1:
                # Fallback: search from start if not found forward
                idx = norm_text.find(ch_norm)
            if idx == -1:
                # If still not found, approximate by taking next slice of length
                idx = cursor
                end = min(len(norm_text), cursor + len(ch_norm))
            else:
                end = idx + len(ch_norm)
            spans.append((idx, end))
            cursor = end
        return spans

    def submit_text(self, text: str):
        self.tasks.put({"text": text})

    def request_stop(self):
        self.stop_event.set()
        # Stop any ongoing playback
        try:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def request_skip(self):
        self.skip_event.set()
        try:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def request_prev(self):
        self.prev_event.set()
        try:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def toggle_pause(self):
        # Toggle pause state with pygame backend
        if not self.pause_event.is_set():
            self.pause_event.set()
            try:
                if pygame is not None and pygame.mixer.get_init():
                    pygame.mixer.music.pause()
            except Exception:
                pass
        else:
            self.pause_event.clear()
            try:
                if pygame is not None and pygame.mixer.get_init():
                    pygame.mixer.music.unpause()
            except Exception:
                pass

    def shutdown(self):
        # Signal thread to stop loop
        self.tasks.put(None)
        self.request_stop()

    def cleanup(self):
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass
        try:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.quit()
        except Exception:
            pass

    def _synthesize_chunk_to_wav(self, text: str, index: int, voice: str) -> str:
        # Prefer streaming response to write directly to file for SDK compatibility
        self.ui.set_status(f"Synthese Abschnitt {index}...")
        self.log(f"Synthese Abschnitt {index} (Zeichen: {len(text)})")
        unique = uuid.uuid4().hex[:8]
        file_path = os.path.join(self.temp_dir, f"part_{index:04d}_{unique}.wav")

        # Try streaming API first
        try:
            with self.client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=voice,
                input=text,
                response_format="wav",
            ) as response:
                response.stream_to_file(file_path)
        except Exception as stream_err:
            # Fallback to non-streaming and attempt to extract bytes
            self.log(f"Hinweis: Fallback ohne Streaming (Grund: {stream_err})")
            resp = self.client.audio.speech.create(
                model=self.model,
                voice=voice,
                input=text,
                response_format="wav",
            )

            audio_bytes = None

            if isinstance(resp, (bytes, bytearray)):
                audio_bytes = bytes(resp)
            else:
                for attr in ("read", "content", "audio"):
                    try:
                        val = getattr(resp, attr)
                        if callable(val):
                            val = val()
                        if isinstance(val, (bytes, bytearray)):
                            audio_bytes = bytes(val)
                            break
                    except Exception:
                        continue

            if audio_bytes is None:
                try:
                    audio_bytes = resp.to_bytes()
                except Exception:
                    pass

            if audio_bytes is None:
                raise RuntimeError("Konnte Audiodaten aus API-Antwort nicht extrahieren.")

            with open(file_path, "wb") as f:
                f.write(audio_bytes)

        # Sanity check
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            raise RuntimeError("Erzeugte WAV-Datei ist leer oder fehlt.")

        return file_path

    def _play_wav_blocking(self, wav_path: str):
        if self.stop_event.is_set():
            return
        # Log and play; ensure file exists and has content
        try:
            size = os.path.getsize(wav_path)
        except Exception:
            size = 0
        if size <= 44:
            raise RuntimeError("WAV-Datei ist zu klein oder beschädigt.")
        self.log(f"Wiedergabe: {os.path.basename(wav_path)} ({size} Bytes)")

        # Use pygame for audio playback on Linux
        if pygame is None:
            raise RuntimeError("pygame ist nicht verfügbar. Installieren Sie pygame für Audio-Wiedergabe.")

        try:
            if not pygame.mixer.get_init():
                # Initialize pygame mixer with default settings
                pygame.mixer.init()
            pygame.mixer.music.load(wav_path)
            pygame.mixer.music.play()
            # Wait until it's done or a stop/skip is requested; honor pause_event
            while pygame.mixer.music.get_busy():
                if self.stop_event.is_set() or self.skip_event.is_set() or self.prev_event.is_set():
                    pygame.mixer.music.stop()
                    break
                if self.pause_event.is_set():
                    try:
                        pygame.mixer.music.pause()
                    except Exception:
                        pass
                    # Wait in paused state until unpaused or a control event arrives
                    while self.pause_event.is_set() and not (self.stop_event.is_set() or self.skip_event.is_set() or self.prev_event.is_set()):
                        time.sleep(0.05)
                    try:
                        if not (self.stop_event.is_set() or self.skip_event.is_set() or self.prev_event.is_set()):
                            pygame.mixer.music.unpause()
                    except Exception:
                        pass
                time.sleep(0.05)
            # Attempt to release file handle explicitly
            try:
                if hasattr(pygame.mixer.music, "unload"):
                    pygame.mixer.music.unload()
            except Exception:
                pass
        except Exception as e:
            raise RuntimeError(f"Fehler bei pygame-Wiedergabe: {e}")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x650")
        self.minsize(760, 520)
        self._is_paused = False

        self._ensure_env()
        self.client = self._init_client()
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        self.voice_var = tk.StringVar(value=DEFAULT_VOICE)
        self.random_voice_var = tk.BooleanVar(value=True)
        self.max_chars_var = tk.IntVar(value=CHARS_PER_CHUNK)

        self._build_ui()

        self.worker = TTSWorker(self, self.client, self.model_var.get(), self.voice_var.get(), self.max_chars_var.get(), self.random_voice_var.get(), SUPPORTED_VOICES)
        self.worker.start()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _ensure_env(self):
        # Check for pygame availability
        if pygame is None:
            safe_showerror("Audio-Backend fehlt", f"pygame konnte nicht importiert werden: {PYGAME_IMPORT_ERROR}\nInstallieren Sie pygame für Audio-Wiedergabe: pip install pygame")

        # Check for OpenAI API key
        if not os.environ.get("OPENAI_API_KEY"):
            safe_showerror("API-Schlüssel fehlt", "Bitte setzen Sie die Environment-Variable OPENAI_API_KEY.")

    def _init_client(self):
        if OpenAI is None:
            raise RuntimeError(
                f"OpenAI SDK konnte nicht importiert werden: {OPENAI_IMPORT_ERROR}\nInstallieren Sie es zuerst: pip install openai"
            )
        try:
            client = OpenAI()
            return client
        except Exception as e:
            raise RuntimeError(f"Fehler bei Initialisierung des OpenAI-Clients: {e}")

    def _build_ui(self):
        # Top controls
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=8, pady=6)

        ttk.Label(ctrl, text="Modell:").pack(side=tk.LEFT)
        self.model_entry = ttk.Entry(ctrl, textvariable=self.model_var, width=24)
        self.model_entry.pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(ctrl, text="Stimme:").pack(side=tk.LEFT)
        self.voice_combo = ttk.Combobox(ctrl, textvariable=self.voice_var, values=SUPPORTED_VOICES, width=16)
        self.voice_combo.pack(side=tk.LEFT, padx=(4, 12))

        self.random_voice_chk = ttk.Checkbutton(ctrl, text="Zufällige Stimme je Abschnitt", variable=self.random_voice_var)
        self.random_voice_chk.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(ctrl, text="Max. Zeichen/Abschnitt:").pack(side=tk.LEFT)
        self.max_chars_spin = ttk.Spinbox(ctrl, from_=200, to=4000, increment=100, textvariable=self.max_chars_var, width=8)
        self.max_chars_spin.pack(side=tk.LEFT, padx=(4, 12))

        self.update_btn = ttk.Button(ctrl, text="Einstellungen übernehmen", command=self.apply_settings)
        self.update_btn.pack(side=tk.LEFT)

        # Text area
        self.text = ScrolledText(self, wrap=tk.WORD, undo=True)
        self.text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        # Playback controls
        play = ttk.Frame(self)
        play.pack(fill=tk.X, padx=8, pady=4)

        self.start_btn = ttk.Button(play, text="Vorlesen", command=self.on_start)
        self.start_btn.pack(side=tk.LEFT)

        self.pause_btn = ttk.Button(play, text="Pause", command=self.on_pause_resume)
        self.pause_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.prev_btn = ttk.Button(play, text="Zurück", command=self.on_prev)
        self.prev_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.next_btn = ttk.Button(play, text="Weiter", command=self.on_skip)
        self.next_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.stop_btn = ttk.Button(play, text="Stopp", command=self.on_stop)
        self.stop_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.clear_btn = ttk.Button(play, text="Text leeren", command=self.on_clear)
        self.clear_btn.pack(side=tk.LEFT, padx=(12, 0))

        self.save_btn = ttk.Button(play, text="Als WAV speichern...", command=self.on_save)
        self.save_btn.pack(side=tk.LEFT, padx=(12, 0))

        # Progress and status
        status = ttk.Frame(self)
        status.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.progress = ttk.Progressbar(status, mode='determinate')
        self.progress.pack(fill=tk.X, side=tk.LEFT, expand=True)

        self.status_var = tk.StringVar(value="Bereit.")
        self.status_lbl = ttk.Label(status, textvariable=self.status_var, width=40, anchor=tk.W)
        self.status_lbl.pack(side=tk.RIGHT, padx=(8, 0))

        # Log
        self.log_txt = ScrolledText(self, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.log_txt.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))

    def apply_settings(self):
        # Update worker parameters
        try:
            self.worker.model = self.model_var.get().strip()
            self.worker.voice = self.voice_var.get().strip()
            self.worker.max_chars = int(self.max_chars_var.get())
            self.worker.randomize_voices = bool(self.random_voice_var.get())
            self.worker.voices = SUPPORTED_VOICES
            self.set_status("Einstellungen übernommen.")
        except Exception as e:
            safe_showerror("Einstellungen", f"Fehler beim Übernehmen der Einstellungen: {e}")

    def on_start(self):
        text = self.text.get("1.0", tk.END)
        if not text.strip():
            safe_showerror("Eingabe", "Bitte geben Sie Text zum Vorlesen ein.")
            return
        self.disable_controls_during_playback()
        self.pause_btn.configure(state=tk.NORMAL, text="Pause")
        self._is_paused = False
        self.set_status("Starte...")
        self.worker.submit_text(text)

    def on_stop(self):
        self.worker.request_stop()
        self._is_paused = False
        self.pause_btn.configure(text="Pause")
        self.set_status("Stopp angefordert...")

    def on_skip(self):
        # also acts as "Weiter"
        self.worker.request_skip()
        self.set_status("Weiter/Überspringen angefordert...")

    def on_clear(self):
        self.text.delete("1.0", tk.END)

    def on_save(self):
        if not self.worker.generated_wavs:
            safe_showerror("Speichern", "Es gibt keine generierten Audioabschnitte zum Speichern.")
            return
        path = filedialog.asksaveasfilename(
            title="Zieldatei wählen",
            defaultextension=".wav",
            filetypes=[("WAV Audio", "*.wav")],
        )
        if not path:
            return
        try:
            self.combine_wavs(self.worker.generated_wavs, path)
            messagebox.showinfo("Speichern", f"Audio gespeichert unter:\n{path}")
        except Exception as e:
            safe_showerror("Speichern", f"Fehler beim Speichern: {e}")

    def set_progress_max(self, maximum: int):
        self.progress.configure(maximum=maximum)

    def set_progress(self, value: int):
        self.progress.configure(value=value)
        self.progress.update_idletasks()

    def set_status(self, text: str):
        self.status_var.set(text)
        self.status_lbl.update_idletasks()

    def log(self, msg: str):
        logger.info(msg)
        self.log_txt.configure(state=tk.NORMAL)
        self.log_txt.insert(tk.END, msg + "\n")
        self.log_txt.see(tk.END)
        self.log_txt.configure(state=tk.DISABLED)

    def disable_controls_during_playback(self):
        self.start_btn.configure(state=tk.DISABLED)
        self.update_btn.configure(state=tk.DISABLED)
        self.model_entry.configure(state=tk.DISABLED)
        self.voice_combo.configure(state=tk.DISABLED)
        self.max_chars_spin.configure(state=tk.DISABLED)
        self.prev_btn.configure(state=tk.NORMAL)
        self.next_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.NORMAL)

    def enable_controls(self):
        self.start_btn.configure(state=tk.NORMAL)
        self.update_btn.configure(state=tk.NORMAL)
        self.model_entry.configure(state=tk.NORMAL)
        self.voice_combo.configure(state=tk.NORMAL)
        self.max_chars_spin.configure(state=tk.NORMAL)
        self.prev_btn.configure(state=tk.DISABLED)
        self.next_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.DISABLED)
        self.pause_btn.configure(state=tk.DISABLED, text="Pause")

    def on_job_finished(self, completed: bool):
        if completed:
            self.set_status("Fertig.")
        else:
            self.set_status("Beendet.")
        self.enable_controls()

    def on_close(self):
        try:
            self.worker.shutdown()
        except Exception:
            pass
        # Give the worker a short moment to finish
        t0 = time.time()
        while self.worker.is_alive() and time.time() - t0 < 1.5:
            time.sleep(0.05)
        try:
            self.worker.cleanup()
        except Exception:
            pass
        self.destroy()

    def on_prev(self):
        self.worker.request_prev()
        self.set_status("Zurück angefordert...")

    def on_pause_resume(self):
        # Toggle pause state in worker and adjust button text
        self.worker.toggle_pause()
        self._is_paused = not self._is_paused
        self.pause_btn.configure(text=("Fortsetzen" if self._is_paused else "Pause"))

    def highlight_span(self, start_char: int, end_char: int):
        # Safely schedule UI update on main thread
        def _do():
            try:
                self.text.tag_delete("current")
            except Exception:
                pass
            try:
                self.text.tag_configure("current", background="#cde6ff")
            except Exception:
                pass
            # Convert char offsets to Tk indices
            start_index = f"1.0+{start_char}c"
            end_index = f"1.0+{end_char}c"
            self.text.tag_add("current", start_index, end_index)
            # Also select in the widget selection for clarity
            try:
                self.text.tag_remove(tk.SEL, "1.0", tk.END)
                self.text.tag_add(tk.SEL, start_index, end_index)
            except Exception:
                pass
            self.text.see(start_index)
        # Use after to run in UI thread
        try:
            self.after(0, _do)
        except Exception:
            _do()

    @staticmethod
    def combine_wavs(wav_paths, out_path):
        if not wav_paths:
            raise ValueError("Keine WAV-Dateien angegeben.")
        # Verify all wavs have same params; if not, re-write headers as needed.
        params = None
        frames = []
        for p in wav_paths:
            with wave.open(p, 'rb') as w:
                if params is None:
                    params = (w.getnchannels(), w.getsampwidth(), w.getframerate())
                else:
                    if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != params:
                        raise ValueError("Inkonsistente WAV-Parameter zwischen Abschnitten.")
                frames.append(w.readframes(w.getnframes()))
        nch, sampw, rate = params
        with wave.open(out_path, 'wb') as out:
            out.setnchannels(nch)
            out.setsampwidth(sampw)
            out.setframerate(rate)
            for data in frames:
                out.writeframes(data)


def main():
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    try:
        logger.info("App gestartet")
        # Early checks and guidance for Linux
        if pygame is None:
            logger.error(f"pygame konnte nicht importiert werden: {PYGAME_IMPORT_ERROR}")
            logger.error("Installieren Sie pygame: pip install pygame")
            sys.exit(1)

        if not os.environ.get("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY ist nicht gesetzt — Synthese wird fehlschlagen.")
            logger.warning("Beispiel: export OPENAI_API_KEY='your-api-key-here'")

        app = App()
        # Initialize control states
        app.enable_controls()
        app.mainloop()
        logger.info("App beendet")
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Unerwarteter Fehler: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
