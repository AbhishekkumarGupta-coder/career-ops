"""
voice.py — Sarvam AI voice integration for Career-Ops.

Speech-to-Text : Saaras v3  (mic → text command)
Text-to-Speech : Bulbul v3  (result text → spoken audio)

Install : pip install sarvamai pyaudio
API key : https://dashboard.sarvam.ai/  →  add SARVAM_API_KEY to .env
"""

import os
import io
import wave
import tempfile
import threading
from pathlib import Path
from rich.console import Console

console = Console()


# ─────────────────────────────────────────
# Key helper
# ─────────────────────────────────────────

def _get_api_key() -> str:
    key = os.environ.get("SARVAM_API_KEY", "")
    if not key:
        env = Path(".env")
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("SARVAM_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return key


def _client():
    """Return a SarvamAI client or raise with a clear message."""
    try:
        from sarvamai import SarvamAI
    except ImportError:
        raise ImportError("sarvamai not installed. Run: pip install sarvamai")

    key = _get_api_key()
    if not key:
        raise ValueError(
            "SARVAM_API_KEY not set.\n"
            "  1. Sign up free at https://dashboard.sarvam.ai/\n"
            "  2. Add SARVAM_API_KEY=your_key to your .env file"
        )
    from sarvamai import SarvamAI
    return SarvamAI(api_subscription_key=key)


# ─────────────────────────────────────────
# Speech-to-Text  (mic → command text)
# ─────────────────────────────────────────

def listen(language: str = "en-IN", duration: int = 5) -> str:
    """
    Record from microphone for `duration` seconds,
    then transcribe with Saaras v3.

    language : BCP-47 code
        "en-IN"  English (India)
        "hi-IN"  Hindi
        "ta-IN"  Tamil
        "te-IN"  Telugu
        "bn-IN"  Bengali
    Returns : transcribed string, or "" on any failure.
    """
    try:
        import pyaudio
    except ImportError:
        console.print("[yellow]pyaudio not installed. Run: pip install pyaudio[/yellow]")
        return ""

    RATE, CHUNK, CHANNELS = 16000, 1024, 1
    FORMAT = pyaudio.paInt16

    console.print(f"[bold cyan]Listening for {duration}s — speak now...[/bold cyan]")

    p      = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    input=True, frames_per_buffer=CHUNK)
    frames = [stream.read(CHUNK, exception_on_overflow=False)
              for _ in range(int(RATE / CHUNK * duration))]
    stream.stop_stream()
    stream.close()
    p.terminate()

    # Save to a temp WAV file
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()

    with wave.open(tmp_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    try:
        sarvam   = _client()
        response = sarvam.speech_to_text.transcribe(
            file_path=tmp_path,
            language=language,          # correct param name in sarvamai SDK
            model="saaras:v3",
        )
        text = (response.transcript or "").strip()
        console.print(f"[dim]You said:[/dim] [bold]{text}[/bold]")
        return text
    except Exception as e:
        console.print(f"[red]Sarvam STT error: {e}[/red]")
        return ""
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ─────────────────────────────────────────
# Text-to-Speech  (text → spoken audio)
# ─────────────────────────────────────────

def speak(
    text: str,
    language: str = "en-IN",
    speaker: str  = "priya",
    play: bool    = True,
    save_to: str  = None,
) -> bytes | None:
    """
    Convert text to speech with Bulbul v3 and optionally play it.

    language : BCP-47 code (same list as listen())
    speaker  : valid values for bulbul:v3 — "priya", "neha", "rahul", "pooja", "rohan",
               "aditya", "ritu", "ashutosh", "simran", "kavya", "amit", "dev", "ishita"
    play     : play audio immediately through speakers
    save_to  : optional file path to save the WAV  (e.g. "output.wav")
    Returns  : raw WAV bytes
    """
    if not text or not text.strip():
        return None

    all_audio = b""
    try:
        from sarvamai import SarvamAI
        from sarvamai.play import save as sarvam_save

        sarvam = _client()

        for chunk in _split_text(text):
            response = sarvam.text_to_speech.convert(
                text=chunk,
                target_language_code=language,
                model="bulbul:v3",
                speaker=speaker,
            )

            # Save to a temp WAV via Sarvam's helper, then read bytes
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                out_path = tmp.name
            sarvam_save(response, out_path)
            chunk_bytes = Path(out_path).read_bytes()
            Path(out_path).unlink(missing_ok=True)

            if chunk_bytes:
                all_audio += chunk_bytes

    except Exception as e:
        console.print(f"[red]Sarvam TTS error: {e}[/red]")
        return None

    if save_to and all_audio:
        Path(save_to).write_bytes(all_audio)
        console.print(f"[dim]Audio saved → {save_to}[/dim]")

    if play and all_audio:
        _play_wav(all_audio)

    return all_audio


def speak_summary(score: float, grade: str, company: str, role: str,
                  language: str = "en-IN"):
    """Read the evaluation verdict aloud after scoring."""
    grade_msg = {
        "A": "Strong match. Highly recommend applying.",
        "B": "Good opportunity. Go ahead and apply.",
        "C": "Conditional match. Review carefully before applying.",
        "D": "Weak match. Reconsider this one.",
        "F": "Not a good fit. Skip this role.",
    }.get(grade, "Evaluation complete.")

    msg = (
        f"{company}. {role}. "
        f"Score {score} out of 5. Grade {grade}. "
        f"{grade_msg}"
    )
    speak(msg, language=language)


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _split_text(text: str, max_len: int = 500) -> list:
    """Split long text at sentence boundaries for the TTS API."""
    sentences = text.replace("\n", " ").split(". ")
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) < max_len:
            current += s + ". "
        else:
            if current:
                chunks.append(current.strip())
            current = s + ". "
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:max_len]]


def _play_wav(wav_bytes: bytes):
    """Play raw WAV bytes through speakers using pyaudio."""
    def _play():
        try:
            import pyaudio
            buf = io.BytesIO(wav_bytes)
            with wave.open(buf, "rb") as wf:
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                )
                data = wf.readframes(1024)
                while data:
                    stream.write(data)
                    data = wf.readframes(1024)
                stream.stop_stream()
                stream.close()
                p.terminate()
        except Exception as e:
            console.print(f"[yellow]Audio playback error: {e}[/yellow]")

    t = threading.Thread(target=_play, daemon=True)
    t.start()
    t.join()


# ─────────────────────────────────────────
# Quick self-test
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # TTS test
    console.print("[bold cyan]--- TTS Test ---[/bold cyan]")
    speak(
        "Hello! Career Ops is now voice enabled. Ready to evaluate your next job.",
        language="en-IN",
        speaker="priya",
        save_to="tts_test.wav",
    )
    console.print("[green]TTS done. Check tts_test.wav if no audio.[/green]")

    # STT test (skip if --no-mic passed)
    if "--no-mic" not in sys.argv:
        console.print("\n[bold cyan]--- STT Test ---[/bold cyan]")
        console.print("Speak a command after the prompt...")
        cmd = listen(language="en-IN", duration=5)
        if cmd:
            console.print(f"[green]Transcribed:[/green] {cmd}")
        else:
            console.print("[yellow]Nothing transcribed. Check your mic or SARVAM_API_KEY.[/yellow]")