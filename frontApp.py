import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading
import time
import pandas as pd

# Параметры
number_of_top_sites = 1_000_000  # Размер списка наиболее посещаемых сайтов
request_qty_per_thread = 10000  # Количество запросов которое должен выполнить каждый поток
other_sites_requests_factor = 1000  # Фактор выборки (%) из списка other_sites


# Подготовка данных из которых затем будут формироваться запросы
print('Reading from file ... ')
web_hosts_data = pd.read_csv('top10milliondomains.csv', delimiter=',')  # Файл с 10млн сайтов
print('Readind file success!')

def top_sites_data_preparing():
    print('Top sites data preparing start....')
    start_preparing_data = time.time()
    top_sites_list = []  # Список наиболее посещаемых сайтов
    for i in range(number_of_top_sites):
        top_sites_list.append((web_hosts_data.iloc[i]['Domain']))
    end_preparing_data = time.time()
    print('Data preparing complete ', end_preparing_data - start_preparing_data, 'sec')
    return top_sites_list

def other_sites_data_preparing():
    print('Other sites data preparing start....')
    start_preparing_data = time.time()
    other_sites_list = []  # Общий список сайтов за исключением наиболее посещаемых
    for i in range(number_of_top_sites, len(web_hosts_data)):
        other_sites_list.append((web_hosts_data.iloc[i]['Domain']))
    end_preparing_data = time.time()
    print('Data preparing complete ', end_preparing_data - start_preparing_data, 'sec')
    return other_sites_list


# Получаем данные
top_sites_list = top_sites_data_preparing()
other_sites_list = other_sites_data_preparing()

def api_requests(num_thread):
    # Функция генерации запросов и ее параметры
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    # Генерация реквестов
    request_start = time.time()
    for i in range(request_qty_per_thread):
        if i % other_sites_requests_factor == 0:
            site = other_sites_list[random.randint(0, len(other_sites_list) - 1)]
            session.get('http://127.0.0.1:8000/api/v1/urls/short', params={"site": site}).json()
        else:
            site = top_sites_list[random.randint(0, len(top_sites_list) - 1)]
            session.get('http://127.0.0.1:8000/api/v1/urls/short', params={"site": site}).json()
    request_end = time.time()

    print('Requests complete: ', request_qty_per_thread, 'for time: ', request_end - request_start, 'sec')


# Запускаем функцию api_requests в N потоках (указано в range)
for i in range(20):
    thread = threading.Thread(target=api_requests, args=(i,))
    thread.start()
