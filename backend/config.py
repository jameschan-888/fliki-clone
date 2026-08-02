"""Fliki 还原后端配置"""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
DATA_DIR = ROOT / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)
# DB 路径可被 FLIKI_DB_PATH 覆盖 (测试/CI/多实例隔离, 避免污染默认开发库)
DB_PATH = os.getenv('FLIKI_DB_PATH') or str(DATA_DIR / 'app.db')

MEDIA_ROOT = DATA_DIR / 'media'
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

STOCK_CACHE_DIR = DATA_DIR / 'stock'
STOCK_CACHE_DIR.mkdir(parents=True, exist_ok=True)

TTS_CACHE_DIR = DATA_DIR / 'tts'
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

AVATAR_CACHE_DIR = DATA_DIR / 'avatar'
AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

MUSIC_CACHE_DIR = DATA_DIR / 'music'
MUSIC_CACHE_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = DATA_DIR / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROVIDER_CONFIG_PATH = DATA_DIR / 'provider_config.json'
DATA_DIR_STR = str(DATA_DIR)

HOST = os.getenv('FLIKI_HOST', '127.0.0.1')
PORT = int(os.getenv('FLIKI_PORT', '5181'))
RENDER_TIMEOUT_SECONDS = max(60, int(os.getenv('RENDER_TIMEOUT_SECONDS', '3600')))

MAX_UPLOAD_BYTES = 512 * 1024 * 1024

DEFAULT_PROVIDERS = {
    'text': [
        {'name': 'mock', 'enabled': True, 'is_default': True, 'priority': 0},
        {'name': 'deepseek', 'enabled': False, 'priority': 10},
        {'name': 'MiniMax', 'enabled': False, 'priority': 20},
        {'name': 'openai', 'enabled': False, 'priority': 30},
        {'name': 'ollama', 'enabled': False, 'priority': 40},
    ],
    'tts': [
        {'name': 'edge_tts', 'enabled': True, 'is_default': True, 'priority': 0},
        {'name': 'gpt_sovits', 'enabled': False, 'priority': 10},
        {'name': 'openai_tts', 'enabled': False, 'priority': 20},
        {'name': 'elevenlabs', 'enabled': False, 'priority': 30},
    ],
    'image': [
        {'name': 'mock', 'enabled': True, 'is_default': True, 'priority': 0},
        {'name': 'pexels', 'enabled': True, 'priority': 10},
        {'name': 'pixabay', 'enabled': False, 'priority': 20},
    ],
    'video': [
        {'name': 'stock_compose', 'enabled': True, 'is_default': True, 'priority': 0},
        {'name': 'kling', 'enabled': False, 'priority': 10},
        {'name': 'veo', 'enabled': False, 'priority': 20},
    ],
    'music': [
        {'name': 'stock_music', 'enabled': True, 'is_default': True, 'priority': 0},
        {'name': 'musicgen', 'enabled': False, 'priority': 10},
    ],
    'avatar': [
        {'name': 'sadtalker', 'enabled': False, 'priority': 0},
        {'name': 'musetalk', 'enabled': False, 'priority': 10},
        {'name': 'heygend_id', 'enabled': False, 'priority': 20},
    ],
    'stock': [
        {'name': 'pexels', 'enabled': True, 'is_default': True, 'priority': 0},
        {'name': 'pixabay', 'enabled': False, 'priority': 10},
        {'name': 'getty', 'enabled': False, 'priority': 20},
    ],
}

config = {
    'DB_PATH': DB_PATH,
    'MEDIA_ROOT': str(MEDIA_ROOT),
    'STOCK_CACHE_DIR': str(STOCK_CACHE_DIR),
    'TTS_CACHE_DIR': str(TTS_CACHE_DIR),
    'AVATAR_CACHE_DIR': str(AVATAR_CACHE_DIR),
    'MUSIC_CACHE_DIR': str(MUSIC_CACHE_DIR),
    'OUTPUT_DIR': str(OUTPUT_DIR),
    'PROVIDER_CONFIG_PATH': str(PROVIDER_CONFIG_PATH),
    'DATA_DIR': DATA_DIR_STR,
    'HOST': HOST,
    'PORT': PORT,
    'RENDER_TIMEOUT_SECONDS': RENDER_TIMEOUT_SECONDS,
    'MAX_UPLOAD_BYTES': MAX_UPLOAD_BYTES,
}
