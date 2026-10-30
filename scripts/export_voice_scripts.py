"""Write the exact narration text for all 19 episodes, ready for any TTS.

The renderer needs one audio file per episode. When the machine that renders has
no route to a neural TTS API (this sandbox blocks `api.openai.com`,
`api.elevenlabs.io` and `fal.run`), the honest workflow is:

    1. run this script
    2. speak each ``exports/voice/episode-NN.txt`` with any neural voice
       (fal MiniMax, OpenAI, ElevenLabs, or a hosted studio)
    3. save the takes as ``exports/voice/voice-01.mp3`` … ``voice-19.mp3``
    4. python scripts/render_kinetic_series.py --voice-dir exports/voice

The text here is post-processed exactly as `kinetic_voice.synthesize` would send
it: pause tags become punctuation, so what you hear is what the pipeline expects.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import kinetic_series, kinetic_voice

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'exports' / 'voice'

# fal MiniMax HD list price, the cheapest of the three neural options.
USD_PER_1K_CHARS = 0.10


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=len(kinetic_series.EPISODES))
    arguments = parser.parse_args(argv)

    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for number in range(arguments.start, arguments.end + 1):
        data = kinetic_series.episode(number)
        text = kinetic_voice._speech_text(data)          # the same string sent to a provider
        target = out / ('episode-%02d.txt' % number)
        target.write_text(text + '\n', encoding='utf-8')
        estimate = kinetic_series.voice_seconds(data)
        rows.append({'episode': number,
                     'layout': data['layout'],
                     'hook': data['hook'],
                     'characters': len(text),
                     'estimated_seconds': round(estimate, 2),
                     'file': 'voice-%02d.mp3' % number,
                     'text': target.name})
        print('[%02d] %s %4d chars ≈%.1f s  %s'
              % (number, data['layout'], len(text), estimate, target.name), flush=True)

    with (out / 'scripts.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    total_chars = sum(row['characters'] for row in rows)
    (out / 'README.md').write_text(
        '# Narration takes\n\n'
        'One file per episode, named `voice-NN.mp3` (or `.wav` / `.m4a`), in this\n'
        'folder. Rules the renderer enforces:\n\n'
        '* length **≤ 19.60 s** — longer runs into the 19.90 s lowpass tail and the\n'
        '  batch reports the episode as failed rather than time-stretching it;\n'
        '* one continuous take, no music and no silence padding: the mix adds the\n'
        '  deep-house bed and the foley under it;\n'
        '* mono or stereo, any sample rate ≥ 22 kHz.\n\n'
        'Suggested voice: a warm, low, unhurried male read — MiniMax `Deep_Voice_Man`,\n'
        'OpenAI `onyx`, or ElevenLabs `Daniel`. No upspeak, no shouting.\n\n'
        '```bash\n'
        'python scripts/render_kinetic_series.py --voice-dir exports/voice --episodes 1\n'
        'python scripts/verify_renders.py --dir exports/videos\n'
        '```\n\n'
        '## Cost\n\n'
        '%d characters in total. At fal MiniMax HD ($0.10/1k chars) that is about\n'
        '**$%.2f** for the set; OpenAI `gpt-4o-mini-tts` is roughly half that.\n'
        % (total_chars, total_chars / 1000.0 * USD_PER_1K_CHARS), encoding='utf-8')
    print('Wrote %d scripts, %d characters, ≈$%.2f at MiniMax HD.'
          % (len(rows), total_chars, total_chars / 1000.0 * USD_PER_1K_CHARS))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
