import random
import threading
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    get_positive_float_env,
    get_positive_int_env,
    get_project_path_env,
    get_url_env,
)


def load_front_config():
    return {
        'api_url': get_url_env('FRONT_APP_API_URL'),
        'domains_file': get_project_path_env('FRONT_APP_DOMAINS_FILE'),
        'top_sites_count': get_positive_int_env('FRONT_APP_TOP_SITES_COUNT'),
        'threads': get_positive_int_env('FRONT_APP_THREADS'),
        'requests_per_thread': get_positive_int_env('FRONT_APP_REQUESTS_PER_THREAD'),
        'other_site_every': get_positive_int_env('FRONT_APP_OTHER_SITE_EVERY_N_REQUESTS'),
        'request_timeout': get_positive_float_env('FRONT_APP_REQUEST_TIMEOUT_SECONDS'),
    }


def prepare_domains(settings):
    domains_file = settings['domains_file']
    if not domains_file.is_file():
        raise RuntimeError('Environment variable FRONT_APP_DOMAINS_FILE must point to an existing file')

    print('Reading from file ...')
    web_hosts_data = pd.read_csv(domains_file, delimiter=',', usecols=['Domain'])
    print('Reading file success!')

    print('Data preparing start...')
    start_preparing_data = time.time()
    domains = web_hosts_data['Domain'].to_list()
    top_sites_count = settings['top_sites_count']
    if top_sites_count >= len(domains):
        raise RuntimeError(
            'Environment variable FRONT_APP_TOP_SITES_COUNT must be smaller than the domains list'
        )

    top_sites = domains[:top_sites_count]
    other_sites = domains[top_sites_count:]
    print('Data preparing complete', time.time() - start_preparing_data, 'sec')
    return top_sites, other_sites


def api_requests(settings, top_sites, other_sites, thread_results):
    session = requests.Session()
    retry = Retry(connect=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    request_start = time.perf_counter()
    request_quantity = 0
    cache_hits = 0
    cache_misses = 0
    for request_number in range(settings['requests_per_thread']):
        request_quantity += 1
        if request_number % settings['other_site_every'] == 0:
            site = random.choice(other_sites)
        else:
            site = random.choice(top_sites)

        try:
            response = session.get(
                settings['api_url'],
                params={'site': site},
                timeout=settings['request_timeout'],
            )
            response_json = response.json()
        except Exception as error:
            print('REQUEST_ERROR', error)
            continue

        if response.status_code != 200:
            print('ERROR found', response_json)
        elif response_json.get('error') == 'DB_INTERACTION_ERROR':
            print('POSTGRES_ERROR', response_json)
        elif response_json.get('redis') == 'miss':
            cache_misses += 1
        else:
            cache_hits += 1

    request_end = time.perf_counter()
    elapsed = request_end - request_start
    print(f'Requests complete for time: {elapsed:0.2f} sec')
    print(f'Performance per thread: {(request_quantity / elapsed):0.0f} rps')
    print(f'Redis stats: hits: {cache_hits}, misses: {cache_misses}')
    thread_results.append([request_quantity / elapsed, cache_hits, cache_misses])
    session.close()


def run_load():
    settings = load_front_config()
    top_sites, other_sites = prepare_domains(settings)
    thread_results = []

    running_threads = []
    for _ in range(settings['threads']):
        thread = threading.Thread(
            target=api_requests,
            args=(settings, top_sites, other_sites, thread_results),
        )
        running_threads.append(thread)
        thread.start()
        time.sleep(0.03)

    for thread in running_threads:
        thread.join()

    total_rps = 0
    total_hits = 0
    total_misses = 0
    for thread_result in thread_results:
        total_rps += thread_result[0]
        total_hits += thread_result[1]
        total_misses += thread_result[2]
    print(f'TOTAL: {total_rps:0.0f} rps, redis hits: {total_hits}, misses: {total_misses}')


if __name__ == '__main__':
    run_load()
