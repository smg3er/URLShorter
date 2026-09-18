import os
import threading
import time

import psycopg2
import prometheus_client
import redis

# Метрики состояния PostgreSQL и Redis, которые демон собирает и отправляет в Pushgateway.
# HTTP-метрики (http_requests, http_requests_seconds) объявлены в apiServer.py и
# уходят в тот же Pushgateway из общего реестра автоматически.
db_connections = prometheus_client.Gauge('db_connections', 'Connections to PostgreSQL database')
db_xacts = prometheus_client.Gauge('db_xacts', 'Total committed transactions in PostgreSQL (cumulative)')
db_rows = prometheus_client.Gauge('db_rows', 'Live rows count in PostgreSQL table', ['table'])
redis_clients = prometheus_client.Gauge('redis_clients', 'Connected clients in Redis')
redis_commands = prometheus_client.Gauge('redis_commands', 'Total processed commands in Redis (cumulative)')
redis_keys = prometheus_client.Gauge('redis_keys', 'Number of keys in Redis')
redis_hits = prometheus_client.Gauge('redis_hits', 'Total cache hits in Redis (cumulative)')
redis_misses = prometheus_client.Gauge('redis_misses', 'Total cache misses in Redis (cumulative)')


# Сбор метрик PostgreSQL: новое подключение на каждый цикл (те же env, что у приложения),
# простые запросы к системным view. Считаем и себя: подключение демона на пару секунд видно как +1.
def collect_postgres():
    connection = psycopg2.connect(user=os.getenv('POSTGRES_USER', 'postgres'),
                                  password=os.getenv('POSTGRES_PASSWORD', '123'),
                                  host=os.getenv('POSTGRES_HOST', '150.241.76.47'),
                                  port=os.getenv('POSTGRES_PORT', '5432'),  # 6432 - pgbouncer, 5432 - postgres
                                  database=os.getenv('POSTGRES_DB', 'urls'))
    cursor = connection.cursor()
    cursor.execute('SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()')
    db_connections.set(cursor.fetchall()[0][0])
    cursor.execute('SELECT xact_commit FROM pg_stat_database WHERE datname = current_database()')
    db_xacts.set(cursor.fetchall()[0][0])
    cursor.execute('SELECT relname, n_live_tup FROM pg_stat_user_tables')
    for table_name, live_rows in cursor.fetchall():
        db_rows.labels(table=table_name).set(live_rows)
    cursor.close()
    connection.close()


# Сбор метрик Redis из INFO и DBSIZE
def collect_redis():
    r = redis.Redis(host=os.getenv('REDIS_HOST', '192.168.68.110'),
                    port=int(os.getenv('REDIS_PORT', '6379')))
    info = r.info()
    redis_clients.set(info['connected_clients'])
    redis_commands.set(info['total_commands_processed'])
    redis_hits.set(info['keyspace_hits'])
    redis_misses.set(info['keyspace_misses'])
    redis_keys.set(r.dbsize())


# Цикл демона: собрать метрики, отправить всё в Pushgateway, подождать интервал.
# Сбор PG, сбор Redis и отправка независимы: падение одного не мешает остальным,
# и HTTP-метрики доходят в Pushgateway даже если БД или Redis недоступны.
def push_loop():
    gateway = os.getenv('METRICS_PUSHGATEWAY', 'localhost:9091')
    interval = int(os.getenv('METRICS_PUSH_INTERVAL', '15'))
    print('Metrics push daemon started, gateway =', gateway, ', interval =', interval, 'sec')
    while True:
        try:
            collect_postgres()
        except (Exception, psycopg2.Error) as error:
            print('ERROR with PostgreSQL metrics', error)
        try:
            collect_redis()
        except Exception as error:
            print('ERROR with Redis metrics', error)
        try:
            prometheus_client.push_to_gateway(gateway, job='urlshorter', registry=prometheus_client.REGISTRY)
        except Exception as error:
            print('ERROR with metrics push', error)
        time.sleep(interval)


# Запуск демона в фоновом потоке (вызывается из apiServer.py при старте приложения)
def start_metrics_push():
    thread = threading.Thread(target=push_loop, daemon=True)
    thread.start()
