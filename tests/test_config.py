import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import config


def expect_runtime_error(action, key):
    try:
        action()
    except RuntimeError as error:
        message = str(error)
        assert key in message
        return message
    raise AssertionError(f'RuntimeError expected for {key}')


def test_required_value():
    with patch.dict(os.environ, {'TEST_REQUIRED': ' value '}, clear=True):
        assert config.get_required_env('TEST_REQUIRED') == 'value'

    secret = 'must-not-appear'
    with patch.dict(os.environ, {'TEST_REQUIRED': secret}, clear=True):
        del os.environ['TEST_REQUIRED']
        message = expect_runtime_error(lambda: config.get_required_env('TEST_REQUIRED'), 'TEST_REQUIRED')
        assert secret not in message


def test_numeric_validation():
    with patch.dict(os.environ, {'TEST_INT': '12', 'TEST_FLOAT': '0.5'}, clear=True):
        assert config.get_positive_int_env('TEST_INT', maximum=20) == 12
        assert config.get_positive_float_env('TEST_FLOAT') == 0.5

    with patch.dict(os.environ, {'TEST_INT': 'secret-number'}, clear=True):
        message = expect_runtime_error(lambda: config.get_int_env('TEST_INT', minimum=1), 'TEST_INT')
        assert 'secret-number' not in message

    with patch.dict(os.environ, {'TEST_INT': '0', 'TEST_FLOAT': '0'}, clear=True):
        expect_runtime_error(lambda: config.get_positive_int_env('TEST_INT'), 'TEST_INT')
        expect_runtime_error(lambda: config.get_positive_float_env('TEST_FLOAT'), 'TEST_FLOAT')


def test_url_validation():
    with patch.dict(os.environ, {'TEST_URL': 'https://example.test/path'}, clear=True):
        assert config.get_url_env('TEST_URL') == 'https://example.test/path'

    with patch.dict(os.environ, {'TEST_URL': 'not-a-url'}, clear=True):
        expect_runtime_error(lambda: config.get_url_env('TEST_URL'), 'TEST_URL')


def test_external_environment_has_priority():
    with tempfile.TemporaryDirectory() as temp_dir:
        env_file = Path(temp_dir) / '.env'
        env_file.write_text('TEST_PRIORITY=from-file\n', encoding='utf-8')
        with patch.dict(os.environ, {'TEST_PRIORITY': 'from-process'}, clear=True):
            config.load_project_env(env_file)
            assert os.environ['TEST_PRIORITY'] == 'from-process'


def main():
    test_required_value()
    test_numeric_validation()
    test_url_validation()
    test_external_environment_has_priority()
    print('config tests: OK')


if __name__ == '__main__':
    main()
