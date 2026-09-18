import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
import time
import pandas as pd

# Параметры
number_of_top_sites = 500_000  # Размер списка наиболее посещаемых сайтов
threads = 8  # Кол-во потоков, которые будут делать HTTP запросы
request_qty_per_thread = 1000  # Количество запросов которое должен выполнить каждый поток
other_sites_requests_factor = 25 # Фактор выборки (%) из списка other_sites

# Подготовка данных из которых затем будут формироваться запросы
print('Reading from file ... ')
web_hosts_data = pd.read_csv('top10milliondomains.csv', delimiter=',', usecols=['Domain'])
print('Reading file success!')

print('Data preparing start....')
start_preparing_data = time.time()
domains = web_hosts_data['Domain'].to_list()
top_sites_list = domains[:number_of_top_sites]  # Список наиболее посещаемых сайтов
other_sites_list = domains[number_of_top_sites:]  # Общий список сайтов за исключением наиболее посещаемых
print('Data preparing complete ', time.time() - start_preparing_data, 'sec')

# Результаты каждого потока для общего итога: [rps потока, cache_hits, cache_misses]
thread_results = []

def api_requests(num_thread):
    # Функция генерации запросов и ее параметры
    session = requests.Session()
    retry = Retry(connect=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)

    # Генерация реквестов
    request_start = time.time()
    rq_qty = 0
    cache_hits = 0
    cache_misses = 0
    for i in range(request_qty_per_thread):
        rq_qty += 1
        if i % other_sites_requests_factor == 0:
            site = other_sites_list[random.randint(0, len(other_sites_list) - 1)]
        else:
            site = top_sites_list[random.randint(0, len(top_sites_list) - 1)]

        try:
            rs = session.get('http://localhost:8000/api/v1/urls/short', params={"site": site})
            rs_json = rs.json()
        except Exception as error:
            print('REQUEST_ERROR', error)
            continue

        if rs.status_code != 200:
            print('ERROR found', rs_json)
        elif rs_json.get('error') == 'DB_INTERACTION_ERROR':
            print('POSTGRES_ERROR', rs_json)
        else:
            redis_status = rs_json.get('redis')
            if redis_status == 'miss':
                cache_misses += 1
            else:
                cache_hits += 1
    request_end = time.time()

    print(f'Requests complete for time: {(request_end - request_start):0.2f} sec')
    print(f'Performance per thread: {(rq_qty/(request_end-request_start)):0.0f} rps')
    print(f'Redis stats: hits: {cache_hits}, misses: {cache_misses}')
    thread_results.append([rq_qty / (request_end - request_start), cache_hits, cache_misses])

# Запускаем функцию api_requests в N потоках (указано в range)
runned_threads = []
for i in range(threads):
    thread = threading.Thread(target=api_requests, args=(i,))
    runned_threads.append(thread)
    thread.start()
    time.sleep(0.33)

# Ждем завершения всех потоков и печатаем общий итог
for thread in runned_threads:
    thread.join()

total_rps = 0
total_hits = 0
total_misses = 0
for thread_result in thread_results:
    total_rps += thread_result[0]
    total_hits += thread_result[1]
    total_misses += thread_result[2]
print(f'TOTAL: {total_rps:0.0f} rps, redis hits: {total_hits}, misses: {total_misses}')
