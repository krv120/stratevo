# The 19 rendered episodes

All 19 episodes exist as real MP4 files: **20.60 s, 1080×1920, 30 fps, H.264 +
AAC, narrated**, with the 26-layer sound design mixed underneath.

| Where | What |
| --- | --- |
| `exports/videos/kinetic-episode-01.mp4` … `-19.mp4` | the clips (≈2.9 MB each, ≈55 MB total) |
| `exports/videos/manifest.json` | probe of every file: duration, frames, size, narration settings |
| `exports/StratEvo_19_Videos.zip` | the same 19 files in one download |
| `python scripts/serve_exports.py --port 8000` | gallery page + byte-range streaming |
| Google Drive folder **StratEvo_19_Videos** | the delivered copies: 19 MP4s + README + manifest + the bundle in two zip parts |
| `exports/StratEvo_19_Videos_part{1,2}_of_2.zip` | the bundle split at 85 MB and 49 MB, because one archive is 130 MB |

**Delivery.** The master files live in the Drive folder
<https://drive.google.com/drive/folders/1Q34wSxx19IzNd1LqiI0c2kYWAAzWmt3f>
(public, anyone with the link, reader). An earlier 52 MB CRF 20 bundle was
committed to this branch while every anonymous file host was unreachable; it has
since been removed from the working tree (`git rm`) because it predates the CRF 14
master render. The blob remains in history until the branch is rewritten.

## Encoder

`kinetic.MASTER_CRF = 14`, `MASTER_PRESET = 'slow'`, `x264-params aq-mode=3:bframes=3`,
AAC 192 kb/s, BT.709 colour tags. Measured against a lossless FFV1 reference of a
3 s window (PSNR, average): CRF 20/veryfast = 38.69 dB, CRF 16/medium + aq-mode 3 =
38.88 dB, CRF 14/slow + aq-mode 3 = 38.89 dB, and a Lanczos colour-matrix scaling
pass made it *worse* (38.69 dB), so it was dropped. The residual gap to the source
is 4:2:0 chroma subsampling, kept because yuv420p is the only universally accepted
pixel format for social upload. Master files are ~7.1 MB per clip (2584 kb/s);
the earlier delivery was 2.9 MB (966 kb/s).

Rendered media is intentionally **not committed** (`.gitignore`: `/exports/videos/`,
`/exports/*.zip`); the repository holds the code that produces it, not 55 MB of MP4.

## Narration

`app/kinetic_voice.py` renders the episode's own script — the same text the paid
MiniMax path speaks — with **eSpeak NG** through its C API, offline:

* pauses come from the episode's `<#x#>` tags, so the read lands on the scene cuts;
* if a take overshoots 19.60 s the rate is raised and it is re-synthesised, never
  time-stretched, so it cannot run into the 19.90 s lowpass tail;
* the take is high-passed at 85 Hz, low-passed at 9.5 kHz, compressed and limited,
  then padded to the full 20.60 s picture.

`espeakng-loader` ships the library and voice data inside its wheel (10 MB), so
this works with no system packages and no network. **It is a formant synthesiser,
not a neural voice** — the read is mechanical. It exists so no clip is silent
while `FAL_KEY` is missing; with a key, `app/voice.py` (fal.ai MiniMax HD,
≈$0.031/clip) produces the neural take and the same mix path uses it unchanged.

## Batch render

```bash
python scripts/render_kinetic_series.py                  # all 19, offline narration
python scripts/render_kinetic_series.py --start 1 --end 3
python scripts/render_kinetic_series.py --narration off  # silent picture
```

Each episode: synthesise narration (≈0.4 s) → synthesise the 26-layer SFX stem
(≈0.8 s) → `kinetic.mix_audio` (voice + stem, `amix normalize=0`, `apad=whole_dur=20.600`)
→ draw 618 frames with Pillow → encode with ffmpeg → probe the result. A clip is
only reported `OK` when it is ≥ 20.50 s, 1080×1920 and has an audio stream.
Measured: **≈52 s of CPU per episode**, so the 19 take ≈17 minutes on 2 vCPU.

## Verification performed

* `ffprobe` on all 19: duration `20.60`, `1080×1920`, `has_audio: true`.
* Speech-band (300–3400 Hz) loudness in the hook window is ≈8.5 dB higher than the
  same window of the SFX-only render, i.e. the voice is really in the mix, not just
  claimed; the 19.90–20.60 s tail is silent in that band, as designed.
* Frames inspected: the hook (phone mockup, brush X, emerald hook), and the
  sign-off (chrome S, STRATEVO, FIND. VET. VERIFY., stratevo.online).
* Byte-identical output for the same episode across runs (the renderer is
  deterministic; only the narration take changes the bytes).

## Honest limits

* Narration is eSpeak NG, not Aria/Guy/MiniMax: `speech.platform.bing.com`,
  HuggingFace and GitHub release assets are all outside this sandbox's network
  allowlist, so `edge-tts`, Piper voices and sherpa-onnx models cannot be fetched.
  Only PyPI is reachable, and no English neural voice ships inside a PyPI wheel.
* The SFX are synthesised stand-ins for the recorded sound design described by
  each layer's `sfx_prompt`.
* Nothing has been posted: these files are deliverables, not scheduled posts.
