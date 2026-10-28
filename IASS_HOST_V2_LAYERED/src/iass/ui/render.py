from pathlib import Path

ROOT = Path(__file__).resolve().parent


def render(name):
    return (ROOT / 'templates' / name).read_text(encoding='utf-8')
