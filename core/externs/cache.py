from pathlib import Path
import json

def get_cache_path(file_path: Path) -> Path:
    cache_dir = file_path.parent / '.cache'
    return cache_dir / f'{file_path.stem}.cache.json'

def load_cached_symbols(file_path: Path) -> dict[str, dict] | None:
    cache_path = get_cache_path(file_path)
    if not cache_path.is_file():
        return None
    try:
        current_mtime = file_path.stat().st_mtime_ns
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('mtime_ns') == current_mtime:
            return data.get('symbols', {})
    except Exception:
        return None
    return None

def save_cached_symbols(file_path: Path, symbols: dict[str, dict]):
    cache_path = get_cache_path(file_path)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        current_mtime = file_path.stat().st_mtime_ns
        payload = {
            'mtime_ns': current_mtime,
            'source': str(file_path.name),
            'symbols': symbols
        }
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass
