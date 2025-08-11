# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "openai>=1.40.0",
#   "pygame>=2.6.0",
# ]
# ///

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
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

# On Windows, winsound is available in the standard library; we'll prefer pygame if available
try:
    import winsound  # type: ignore
except Exception:
    winsound = None

# Optional pygame for robust playback
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

APP_TITLE = "TTS Player (OpenAI)"
DEFAULT_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "alloy"
SUPPORTED_VOICES = [
    # Common example voices; adjust to what your account supports
    "alloy", "verse", "aria", "blaze", "coral", "ember", "sage"
]
CHARS_PER_CHUNK = 1800  # conservative size to avoid model limits; adjustable in UI


def safe_showerror(title: str, message: str):
    try:
        messagebox.showerror(title, message)
    except Exception:
        print(f"ERROR - {title}: {message}")


def split_text_to_chunks(text: str, max_chars: int) -> list:
    """
    Split text into chunks with preference for sentence/paragraph boundaries.
    Conservative and robust: split by double newlines into paragraphs, then sentences.
    """
    text = text.strip()
    if not text:
        return []

    # Normalize newlines
    text = re.sub(r"\r\n?", "\n", text)

    # First split by blank lines (paragraphs)
    paragraphs = re.split(r"\n\s*\n", text)
    sentences = []
    sentence_sep = re.compile(r"(?<=[.!?])[\)\]\"']*\s+")  # split on sentence end, keep punctuation

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Further split into sentences
        parts = sentence_sep.split(p)
        # sentence_sep.split loses the separator, so we re-attach spaces appropriately
        # We'll just keep parts as-is; they typically still end with punctuation
        for s in parts:
            s = s.strip()
            if s:
                sentences.append(s)

    # Now pack sentences into chunks up to max_chars
    chunks = []
    buf = ""
    for s in sentences:
        # Ensure a space between sentences when concatenating
        candidate = (buf + " " + s).strip() if buf else s
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                chunks.append(buf)
            # If single sentence is too long, hard-wrap it
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


class TTSWorker(threading.Thread):
    def __init__(self, ui_ref, client, model: str, voice: str, max_chars: int):
        super().__init__(daemon=True)
        self.ui = ui_ref
        self.client = client
        self.model = model
        self.voice = voice
        self.max_chars = max_chars
        self.stop_event = threading.Event()
        self.skip_event = threading.Event()
        self.tasks = queue.Queue()  # holds text jobs
        self.temp_dir = tempfile.mkdtemp(prefix="tts_openai_")
        self.generated_wavs = []  # list of wav file paths in order

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
                self.generated_wavs.clear()
                chunks = split_text_to_chunks(text, self.max_chars)
                total = len(chunks)
                if total == 0:
                    self.log("Kein Inhalt nach Aufteilung gefunden.")
                    continue
                self.ui.set_progress_max(total)
                self.ui.set_progress(0)
                self.log(f"Starte Synthese und Wiedergabe ({total} Abschnitte)...")

                for idx, chunk in enumerate(chunks, start=1):
                    if self.stop_event.is_set():
                        self.log("Abgebrochen.")
                        break

                    # Synthesize
                    try:
                        wav_path = self._synthesize_chunk_to_wav(chunk, idx)
                        self.generated_wavs.append(wav_path)
                    except Exception as e:
                        self.log(f"Fehler bei Synthese von Abschnitt {idx}: {e}")
                        self.log(traceback.format_exc())
                        # On serious failure, stop further processing
                        break

                    # Play
                    if self.stop_event.is_set():
                        break
                    try:
                        self._play_wav_blocking(wav_path)
                    except Exception as e:
                        self.log(f"Fehler bei Wiedergabe von Abschnitt {idx}: {e}")
                        self.log(traceback.format_exc())
                        break

                    self.ui.set_progress(idx)
                    self.ui.set_status(f"Abgespielt: {idx}/{total}")

                    if self.skip_event.is_set():
                        # Reset skip flag after effect
                        self.skip_event.clear()

                self.ui.on_job_finished(not self.stop_event.is_set())
                self.stop_event.clear()
                self.skip_event.clear()
        except Exception as e:
            self.log(f"Unerwarteter Fehler im Worker: {e}")
            self.log(traceback.format_exc())
        finally:
            self.log("Worker beendet.")

    def submit_text(self, text: str):
        self.tasks.put({"text": text})

    def request_stop(self):
        self.stop_event.set()
        # Stop any ongoing playback in both backends
        try:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        try:
            if winsound is not None:
                winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def request_skip(self):
        self.skip_event.set()
        try:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        try:
            if winsound is not None:
                winsound.PlaySound(None, winsound.SND_PURGE)
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

    def _synthesize_chunk_to_wav(self, text: str, index: int) -> str:
        # Prefer streaming response to write directly to file for SDK compatibility
        self.ui.set_status(f"Synthese Abschnitt {index}...")
        self.log(f"Synthese Abschnitt {index} (Zeichen: {len(text)})")
        unique = uuid.uuid4().hex[:8]
        file_path = os.path.join(self.temp_dir, f"part_{index:04d}_{unique}.wav")

        # Try streaming API first
        try:
            with self.client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format="wav",
            ) as response:
                response.stream_to_file(file_path)
        except Exception as stream_err:
            # Fallback to non-streaming and attempt to extract bytes
            self.log(f"Hinweis: Fallback ohne Streaming (Grund: {stream_err})")
            resp = self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
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
        if self.stop_event.is_set() or self.skip_event.is_set():
            return
        # Log and play; ensure file exists and has content
        try:
            size = os.path.getsize(wav_path)
        except Exception:
            size = 0
        if size <= 44:
            raise RuntimeError("WAV-Datei ist zu klein oder beschädigt.")
        self.log(f"Wiedergabe: {os.path.basename(wav_path)} ({size} Bytes)")

        # Prefer pygame if available; fallback to winsound
        if pygame is not None:
            try:
                if not pygame.mixer.get_init():
                    # Let pygame choose format from file; default init is OK
                    pygame.mixer.init()
                pygame.mixer.music.load(wav_path)
                pygame.mixer.music.play()
                # Wait until it's done or a stop/skip is requested
                while pygame.mixer.music.get_busy():
                    if self.stop_event.is_set() or self.skip_event.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.05)
                # Attempt to release file handle explicitly
                try:
                    if hasattr(pygame.mixer.music, "unload"):
                        pygame.mixer.music.unload()
                except Exception:
                    pass
                return
            except Exception as e:
                self.log(f"Hinweis: pygame-Wiedergabe fehlgeschlagen, Fallback auf winsound: {e}")
                # fall through to winsound

        if winsound is None:
            raise RuntimeError("Kein Wiedergabe-Backend verfügbar (pygame/winsound).")
        winsound.PlaySound(wav_path, winsound.SND_FILENAME | getattr(winsound, 'SND_NODEFAULT', 0))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x650")
        self.minsize(760, 520)

        self._ensure_env()
        self.client = self._init_client()
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        self.voice_var = tk.StringVar(value=DEFAULT_VOICE)
        self.max_chars_var = tk.IntVar(value=CHARS_PER_CHUNK)

        self._build_ui()

        self.worker = TTSWorker(self, self.client, self.model_var.get(), self.voice_var.get(), self.max_chars_var.get())
        self.worker.start()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _ensure_env(self):
        if os.name != "nt":
            safe_showerror("Plattform", "Diese Anwendung ist für Windows optimiert (winsound).")
        if not os.environ.get("OPENAI_API_KEY"):
            safe_showerror("API-Schlüssel fehlt", "Bitte setzen Sie die Environment-Variable OPENAI_API_KEY.")

    def _init_client(self):
        if OpenAI is None:
            raise RuntimeError(
                f"OpenAI SDK konnte nicht importiert werden: {OPENAI_IMPORT_ERROR}\nInstallieren Sie es zuerst."
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

        ttk.Label(ctrl, text="Max. Zeichen/Abschnitt:").pack(side=tk.LEFT)
        self.max_chars_spin = ttk.Spinbox(ctrl, from_=400, to=8000, increment=100, textvariable=self.max_chars_var, width=8)
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

        self.stop_btn = ttk.Button(play, text="Stopp", command=self.on_stop)
        self.stop_btn.pack(side=tk.LEFT, padx=(6, 0))

        self.skip_btn = ttk.Button(play, text="Überspringen", command=self.on_skip)
        self.skip_btn.pack(side=tk.LEFT, padx=(6, 0))

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
            self.set_status("Einstellungen übernommen.")
        except Exception as e:
            safe_showerror("Einstellungen", f"Fehler beim Übernehmen der Einstellungen: {e}")

    def on_start(self):
        text = self.text.get("1.0", tk.END)
        if not text.strip():
            safe_showerror("Eingabe", "Bitte geben Sie Text zum Vorlesen ein.")
            return
        self.disable_controls_during_playback()
        self.set_status("Starte...")
        self.worker.submit_text(text)

    def on_stop(self):
        self.worker.request_stop()
        self.set_status("Stopp angefordert...")

    def on_skip(self):
        self.worker.request_skip()
        self.set_status("Überspringen angefordert...")

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

    def enable_controls(self):
        self.start_btn.configure(state=tk.NORMAL)
        self.update_btn.configure(state=tk.NORMAL)
        self.model_entry.configure(state=tk.NORMAL)
        self.voice_combo.configure(state=tk.NORMAL)
        self.max_chars_spin.configure(state=tk.NORMAL)

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
    # Early checks and guidance
    if winsound is None and os.name == "nt":
        safe_showerror("winsound", "winsound konnte nicht geladen werden. Stellen Sie sicher, dass Sie auf Windows ausführen.")
    if not os.environ.get("OPENAI_API_KEY"):
        print("Hinweis: Setzen Sie OPENAI_API_KEY vor dem Start der Anwendung.")
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

