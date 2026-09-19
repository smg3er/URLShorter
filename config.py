import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / '.env'


def load_project_env(env_file=ENV_FILE):
    env_path = Path(env_file)
    if not env_path.is_file():
        raise RuntimeError(f'Environment file not found: {env_path}')
    load_dotenv(dotenv_path=env_path, override=False)


def get_required_env(name):
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f'Missing required environment variable: {name}')
    return value.strip()


def get_int_env(name, minimum=None, maximum=None):
    raw_value = get_required_env(name)
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f'Environment variable {name} must be an integer') from error

    if minimum is not None and value < minimum:
        raise RuntimeError(f'Environment variable {name} must be at least {minimum}')
    if maximum is not None and value > maximum:
        raise RuntimeError(f'Environment variable {name} must be at most {maximum}')
    return value


def get_positive_int_env(name, maximum=None):
    return get_int_env(name, minimum=1, maximum=maximum)


def get_float_env(name, minimum=None):
    raw_value = get_required_env(name)
    try:
        value = float(raw_value)
    except ValueError as error:
        raise RuntimeError(f'Environment variable {name} must be a number') from error

    if minimum is not None and value < minimum:
        raise RuntimeError(f'Environment variable {name} must be at least {minimum}')
    return value


def get_positive_float_env(name):
    value = get_float_env(name)
    if value <= 0:
        raise RuntimeError(f'Environment variable {name} must be greater than 0')
    return value


def get_url_env(name):
    value = get_required_env(name)
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise RuntimeError(f'Environment variable {name} must be an HTTP URL')
    return value


def get_project_path_env(name):
    path = Path(get_required_env(name))
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


load_project_env()
