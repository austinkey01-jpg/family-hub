# Giving FamilyHub Dad's voice

The display speaks with a **Piper** voice model trained on recordings of your dad. Piper
runs in real time on the Pi 5's CPU, so once trained, nothing he says ever leaves the
house and it works offline.

Piper can't clone from a 10-second sample. Instead you **fine-tune** an existing
high-quality voice on his recordings. More (clean) audio means a closer match:

| Recorded audio | What to expect |
|---|---|
| 15–20 min (~200 lines) | Clearly his voice, a little robotic on long sentences |
| 30–45 min (~400 lines) | Good. This is the target. |
| 60+ min | Very natural |

## 1. Record (one or two evenings)

**Setup**
- A USB mic or a phone in a quiet room. A closet full of clothes is a great booth.
- Same mic, same spot, same distance (about a hand-width) every session.
- Turn off fans, fridge hum and the dishwasher. Phones on silent.
- 22,050 Hz or higher, mono, WAV. No compression, no noise reduction.

**How he should read**
- His normal speaking voice, the way he'd talk to the family at breakfast. Not a "radio voice."
- One line per clip. Re-record any line with a stumble, cough or laugh.
- Take a break every 20 minutes; voices drift when tired.

**Tooling** (pick one)
- [piper-recording-studio](https://github.com/rhasspy/piper-recording-studio): a web page that shows one prompt at a time and saves clips with matching transcripts.
- [TextyMcSpeechy](https://github.com/domesticatedviking/TextyMcSpeechy): dataset recorder + training environment in one, built around family voice clones.

Use `prompts.txt` in this folder. It starts with the phrases FamilyHub actually says (so
those come out best), then general sentences for coverage. Add 200+ more lines from
any public-domain text (old novels from Project Gutenberg work well) to reach the target.

## 2. Train (a few hours, needs an NVIDIA GPU)

The Pi can't train; it only runs the finished model. Options:
- A gaming PC with an NVIDIA card (8 GB+ VRAM), or
- A rented cloud GPU for a few hours (RunPod, Vast.ai, Lambda, or Google Colab).

Steps (TextyMcSpeechy automates most of this):
1. Put clips in `dataset/wav/` and a `metadata.csv` of `filename|transcript` lines.
2. Download the **en_US-lessac-medium** (or **high**) Piper checkpoint as the starting point.
3. Preprocess the dataset, then fine-tune ~1,000–2,000 additional epochs.
   Listen to test samples as it trains; stop when it sounds like him.
4. Export to `dad.onnx` + `dad.onnx.json`.

Full reference: the Piper repo's TRAINING docs.

## 3. Install on the Pi

```bash
mkdir -p ~/familyhub/voice/models
scp dad.onnx dad.onnx.json pi@familyhub.local:~/familyhub/voice/models/
```
In `config.json`:
```json
"voice_model": "voice/models/dad.onnx",
"voice_speed": 1.0
```
Restart (`sudo systemctl restart familyhub`). A ▶ button appears on the morning message.
`voice_speed` above 1.0 slows him down; 1.1 often sounds more natural.

Until his model is ready, drop in any stock Piper voice (e.g. `en_US-lessac-medium.onnx`)
to test the whole pipeline.

## Keep it his

A voice model is as personal as a fingerprint. Keep `dad.onnx` and the raw recordings
off public GitHub and shared drives, and let him hear it before the family does. He gets
to veto anything he doesn't like.
