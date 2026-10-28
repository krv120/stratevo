"""Export the 19 kinetic episodes as the Arena_AI_Queue publishing sheet.

One row per episode, every row ``pending``: nothing is uploaded, scheduled or
posted by this script. It writes CSV (for a Sheets/Excel import) and JSON (for
the API or a scripted sheet push), and refuses to overwrite a queue that already
has non-pending work unless ``--force`` is passed.

    python scripts/export_kinetic_queue.py --out exports/Arena_AI_Queue.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import kinetic_series

FIELDS = (
    'episode', 'status', 'series', 'hook', 'equation', 'illusion_1', 'illusion_2',
    'illusion_3', 'question_1', 'question_2', 'question_3', 'caption', 'hashtags',
    'platforms', 'duration_seconds', 'fps', 'resolution', 'sfx_layers',
    'sfx_tail_start', 'sfx_tail_duration', 'voice_seconds', 'renderer', 'runtime_usd',
    'video_file', 'cta',
)


def rows():
    """One dict per episode, in publishing order, all with status ``pending``."""
    queue = []
    for data in kinetic_series.EPISODES:
        metadata = data['metadata']
        blueprint = data['audio_blueprint']
        queue.append({
            'episode': data['index'],
            'status': 'pending',
            'series': kinetic_series.SERIES_NAME,
            'hook': data['hook'],
            'equation': metadata['equation'],
            'illusion_1': data['illusions'][0],
            'illusion_2': data['illusions'][1],
            'illusion_3': data['illusions'][2],
            'question_1': data['questions'][0],
            'question_2': data['questions'][1],
            'question_3': data['questions'][2],
            'caption': metadata['caption'].replace('\n', ' | '),
            'hashtags': metadata['hashtags'],
            'platforms': ', '.join(metadata['platforms']),
            'duration_seconds': '%.2f' % metadata['duration_seconds'],
            'fps': metadata['fps'],
            'resolution': metadata['resolution'],
            'sfx_layers': blueprint['layer_count'],
            'sfx_tail_start': '%.2f' % blueprint['tail']['start_time'],
            'sfx_tail_duration': '%.2f' % blueprint['tail']['duration'],
            'voice_seconds': '%.2f' % data['episode_data']['estimated_seconds'],
            'renderer': 'kinetic (in code, $0)',
            'runtime_usd': '0.00',
            'video_file': 'kinetic-episode-%02d.mp4' % data['index'],
            'cta': metadata['cta'],
        })
    return queue


def write_csv(destination, queue=None):
    queue = queue if queue is not None else rows()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_statuses(destination)
    blocking = {value for value in existing if value and value != 'pending'}
    if blocking:
        raise SystemExit('Refusing to overwrite %s: it holds %s rows.' %
                         (destination, ', '.join(sorted(blocking))))
    with destination.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(queue)
    return destination


def write_json(destination, queue=None):
    queue = queue if queue is not None else rows()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({'name': 'Arena_AI_Queue', 'status': 'pending',
                                       'episodes': queue}, indent=2), encoding='utf-8')
    return destination


def _existing_statuses(destination):
    if not destination.exists():
        return []
    try:
        with destination.open(newline='', encoding='utf-8') as handle:
            return [row.get('status', '') for row in csv.DictReader(handle)]
    except (OSError, csv.Error):
        return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='exports/Arena_AI_Queue.csv')
    parser.add_argument('--json', default='exports/Arena_AI_Queue.json')
    arguments = parser.parse_args(argv)
    queue = rows()
    write_csv(arguments.out, queue)
    write_json(arguments.json, queue)
    print('Wrote %d pending episodes to %s and %s' % (len(queue), arguments.out, arguments.json))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
