import fastapi
from hashids import Hashids
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
from psycopg2 import Error
import psycopg2
import uvicorn
import psutil
import redis
import time
import prometheus_client
import metricsPush
from config import get_positive_int_env, get_required_env, get_url_env


POSTGRES_USER = get_required_env('POSTGRES_USER')
POSTGRES_PASSWORD = get_required_env('POSTGRES_PASSWORD')
POSTGRES_HOST = get_required_env('POSTGRES_HOST')
POSTGRES_PORT = get_positive_int_env('POSTGRES_PORT', maximum=65535)
POSTGRES_DB = get_required_env('POSTGRES_DB')
REDIS_HOST = get_required_env('REDIS_HOST')
REDIS_PORT = get_positive_int_env('REDIS_PORT', maximum=65535)
API_HOST = get_required_env('API_HOST')
API_PORT = get_positive_int_env('API_PORT', maximum=65535)
SHORT_URL_BASE_URL = get_url_env('SHORT_URL_BASE_URL').rstrip('/') + '/'
REDIS_TTL_SECONDS = get_positive_int_env('REDIS_TTL_SECONDS')
HASHIDS_SALT = get_required_env('HASHIDS_SALT')
HASHIDS_MIN_LENGTH = get_positive_int_env('HASHIDS_MIN_LENGTH')

# Функция генерации короткого урла на основании id записи из БД
def simple_shorter(urls_id):
    hashids = Hashids(min_length=HASHIDS_MIN_LENGTH)
    link = hashids.encode(urls_id)
    short_url = ('{link}'.format(link=link))
    return short_url

# Функиця генерации короткого урла с солью на основании id записи из БД
def simple_shorter_salt(urls_id):
    hashids = Hashids(salt=HASHIDS_SALT, min_length=HASHIDS_MIN_LENGTH)
    link = hashids.encode(urls_id)
    short_url = ('{link}'.format(link=link))
    return short_url

# Функция взаимодействия с базой данных PostgreSQL
def data_base_interaction(site):
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(user=POSTGRES_USER,
                                      password=POSTGRES_PASSWORD,
                                      host=POSTGRES_HOST,
                                      port=POSTGRES_PORT,
                                      database=POSTGRES_DB)
        cursor = connection.cursor()
        cursor.execute('SELECT shorturl, longurl FROM urls ' +
                       'WHERE longurl=%(longurl)s', {'longurl': site})
        select_result = cursor.fetchall()
        if len(select_result) != 0:
            return select_result[0][0]  # Возвращаем уже существующий shorturl из БД
        else:
            cursor.execute('INSERT INTO urls (longurl) VALUES (%(longurl)s)',  # Добавляем запись с longurl в БД
                           {'longurl': site})
            cursor.execute('SELECT id FROM urls WHERE longurl=%(longurl)s', {'longurl': site})
            urls_id = cursor.fetchall()[0][0]  # Получаем id записи в БД
            short_url = simple_shorter(urls_id)  # Герерим короткий урл
            # Проверяем нет ли других записей с таким коротким урлом в БД
            cursor.execute('SELECT * FROM urls WHERE shorturl=%(shorturl)s', {'shorturl': short_url})
            select_check = cursor.fetchall()
            if len(select_check) != 0:  # Если запись с таким коротким урлом существует, то перегенериваем с солью
                short_url_salt = simple_shorter_salt(urls_id)
                cursor.execute('UPDATE urls SET shorturl=%(shorturl_salt)s WHERE id=%(urls_id)s',
                               {'shorturl_salt': short_url_salt, 'urls_id': urls_id})
                connection.commit()
            else:
                cursor.execute('UPDATE urls SET shorturl=%(shorturl)s WHERE id=%(urls_id)s',
                           {'shorturl':short_url, 'urls_id':urls_id})
                connection.commit()
            cursor.execute('SELECT shorturl, longurl FROM urls ' +
                           'WHERE longurl=%(longurl)s', {'longurl': site})
            return cursor.fetchall()[0][0]  # Возвращаем короткий урл

    except (Exception, Error) as error:
        print("ERROR with PostgreSQL", error)
        if connection:
            cursor.close()
            connection.close()
    finally:
        if connection:
            cursor.close()
            connection.close()
        #   print("DB connection closed")


# Функции сервера fastAPI
# Чтобы запустить из cmd "uvicorn apiServer:app --reload"
app = FastAPI()

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)


@app.get("/api/v1/urls/short")
def get_request_processor(site):
    redis_data = r.get(site)  # Получаем пару из Redis по longurl
    if redis_data is None:
        data = data_base_interaction(site) # Если в Redis нет значения, то взаимодействуем с PostgreSQL
        if data == None or str(data) == 'None': # Если вызов функции вернул Null
            return JSONResponse(status_code=500,
                                content={'code': 'HTTP_500_INTERNAL_SERVER_ERROR',
                                         'error': 'DB_INTERACTION_ERROR',
                                         'data': str(data)})
        else:
            short_url = SHORT_URL_BASE_URL + str(data)
            response = {"longUrl": site, "shortUrl": short_url, "redis": "miss"}
            r.set(site, short_url, ex=REDIS_TTL_SECONDS)  # Добавляем в Redis пару
            return JSONResponse(content=response)
    else:  # Иначе возвращаем из Redis
        short_url = str(redis_data.decode('utf-8'))
        response = {"longUrl": site, "shortUrl": short_url, "redis": "hit"}
        return JSONResponse(content=response)


#  Актуатор
metrics_app = prometheus_client.make_asgi_app()
app.mount("/actuator/prometheus", metrics_app)

http_requests = prometheus_client.Counter('http_requests', 'Total count of HTTP requests',
                                          ['method', 'status_code'])
http_requests_seconds = prometheus_client.Histogram('http_requests_seconds', 'Duration of HTTP requests in seconds',
                                                    ['method'])

@app.middleware("http")
async def http_metrics(request: fastapi.Request, call_next):
    if request.url.path.startswith('/actuator/prometheus'):
        return await call_next(request)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        route = request.scope.get('route')
        if route is not None:
            http_requests.labels(method=route.path, status_code='500').inc()
            http_requests_seconds.labels(method=route.path).observe(time.perf_counter() - start)
        raise
    route = request.scope.get('route')
    if route is not None:
        http_requests.labels(method=route.path, status_code=str(response.status_code)).inc()
        http_requests_seconds.labels(method=route.path).observe(time.perf_counter() - start)
    return response

@app.get("/stop")
def stop():

    parent_pid = os.getpid()
    parent = psutil.Process(parent_pid)
    for child in parent.children(recursive=True):
        child.kill()
    parent.kill()

# Запуск фонового демона отправки метрик в Pushgateway (см. metricsPush.py)
metricsPush.start_metrics_push()

if __name__ == '__main__':
    uvicorn.run(app, host=API_HOST, port=API_PORT)
