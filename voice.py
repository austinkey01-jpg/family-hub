"""Dad's voice: text-to-speech with a custom Piper model, running on the Pi itself.

Piper runs in real time on a Raspberry Pi 5 CPU. Until Dad's model is trained, point
`voice_model` at any stock Piper voice (e.g. en_US-lessac-medium.onnx) and everything
works the same; swapping in dad.onnx later is a one-line config change.

See voice/RECORDING_GUIDE.md for how to record and train his voice.
"""
import hashlib
import shutil
import subprocess
from pathlib import Path


class Voice:
    def __init__(self, cfg, cache_dir):
        self.model = cfg.get("voice_model", "")
        self.length_scale = str(cfg.get("voice_speed", 1.0))
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.piper = shutil.which("piper")

    @property
    def enabled(self):
        return bool(self.model and Path(self.model).exists() and self.piper)

    def synth(self, text):
        """Return path to a WAV of `text`, cached by content."""
        if not self.enabled:
            raise RuntimeError("Voice not set up yet: install piper-tts and set voice_model in config.json")
        key = hashlib.sha1(f"{self.model}|{self.length_scale}|{text}".encode()).hexdigest()[:16]
        out = self.cache / f"{key}.wav"
        if not out.exists():
            subprocess.run([self.piper, "--model", self.model, "--length_scale", self.length_scale,
                            "--output_file", str(out)],
                           input=text.encode(), check=True, timeout=60,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        # keep the cache small
        files = sorted(self.cache.glob("*.wav"), key=lambda p: p.stat().st_mtime)
        for old in files[:-200]:
            old.unlink(missing_ok=True)
        return out
