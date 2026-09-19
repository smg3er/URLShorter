import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import frontApp
import initSQL
import metricsPush


def expect_runtime_error(action, key):
    try:
        action()
    except RuntimeError as error:
        assert key in str(error)
        return
    raise AssertionError(f'RuntimeError expected for {key}')


def metrics_environment(interval='3'):
    return {
        'POSTGRES_USER': 'test-user',
        'POSTGRES_PASSWORD': 'test-password',
        'POSTGRES_HOST': '127.0.0.1',
        'POSTGRES_PORT': '6432',
        'POSTGRES_DB': 'test-database',
        'REDIS_HOST': '127.0.0.1',
        'REDIS_PORT': '6379',
        'METRICS_PUSHGATEWAY': '127.0.0.1:9091',
        'METRICS_PUSH_INTERVAL': interval,
    }


def front_environment():
    return {
        'FRONT_APP_API_URL': 'http://127.0.0.1:8000/api/v1/urls/short',
        'FRONT_APP_DOMAINS_FILE': 'small.csv',
        'FRONT_APP_TOP_SITES_COUNT': '2',
        'FRONT_APP_THREADS': '1',
        'FRONT_APP_REQUESTS_PER_THREAD': '1',
        'FRONT_APP_OTHER_SITE_EVERY_N_REQUESTS': '2',
        'FRONT_APP_REQUEST_TIMEOUT_SECONDS': '0.5',
    }


def test_metrics_validation_happens_before_thread_start():
    thread_factory = MagicMock()
    with patch.dict(os.environ, metrics_environment(interval='0'), clear=True):
        expect_runtime_error(lambda: metricsPush.start_metrics_push(thread_factory), 'METRICS_PUSH_INTERVAL')
    thread_factory.assert_not_called()


def test_metrics_thread_receives_configured_interval():
    thread = MagicMock()
    thread_factory = MagicMock(return_value=thread)
    with patch.dict(os.environ, metrics_environment(interval='7'), clear=True):
        result = metricsPush.start_metrics_push(thread_factory)

    assert result is thread
    thread.start.assert_called_once_with()
    thread_arguments = thread_factory.call_args.kwargs['args']
    assert thread_arguments[2] == '127.0.0.1:9091'
    assert thread_arguments[3] == 7


def test_initializer_uses_admin_port_and_target_database():
    connections = []

    def fake_connect(**kwargs):
        connection = MagicMock()
        connections.append((kwargs, connection))
        return connection

    environment = {
        'POSTGRES_USER': 'test-user',
        'POSTGRES_PASSWORD': 'test-password',
        'POSTGRES_HOST': '127.0.0.1',
        'POSTGRES_ADMIN_PORT': '5544',
        'POSTGRES_ADMIN_DB': 'postgres',
        'POSTGRES_DB': 'urls-test',
    }
    with patch.dict(os.environ, environment, clear=True):
        initSQL.main(fake_connect)

    assert connections[0][0]['port'] == 5544
    assert connections[0][0]['database'] == 'postgres'
    assert connections[1][0]['port'] == 5544
    assert connections[1][0]['database'] == 'urls-test'


def test_front_profile_and_timeout_are_used():
    with patch.dict(os.environ, front_environment(), clear=True):
        settings = frontApp.load_front_config()

    assert settings['threads'] == 1
    assert settings['requests_per_thread'] == 1
    assert settings['request_timeout'] == 0.5

    response = MagicMock(status_code=200)
    response.json.return_value = {'redis': 'miss'}
    session = MagicMock()
    session.get.return_value = response
    results = []
    with patch.object(frontApp.requests, 'Session', return_value=session):
        frontApp.api_requests(settings, ['top.test'], ['other.test'], results)

    assert session.get.call_args.kwargs['timeout'] == 0.5
    assert results[0][2] == 1


def test_front_config_fails_before_reading_csv():
    invalid_cases = [
        ({key: value for key, value in front_environment().items() if key != 'FRONT_APP_THREADS'},
         'FRONT_APP_THREADS'),
        ({**front_environment(), 'FRONT_APP_THREADS': 'not-a-number'}, 'FRONT_APP_THREADS'),
        ({**front_environment(), 'FRONT_APP_THREADS': '0'}, 'FRONT_APP_THREADS'),
    ]

    for environment, key in invalid_cases:
        with patch.dict(os.environ, environment, clear=True), patch.object(frontApp.pd, 'read_csv') as read_csv:
            expect_runtime_error(frontApp.run_load, key)
            read_csv.assert_not_called()


def main():
    test_metrics_validation_happens_before_thread_start()
    test_metrics_thread_receives_configured_interval()
    test_initializer_uses_admin_port_and_target_database()
    test_front_profile_and_timeout_are_used()
    test_front_config_fails_before_reading_csv()
    print('runtime configuration tests: OK')


if __name__ == '__main__':
    main()
