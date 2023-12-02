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

# Функция генерации короткого урла на основании id записи из БД
def simple_shorter(urls_id):
    hashids = Hashids(min_length=6)
    link = hashids.encode(urls_id)
    short_url = ('{link}'.format(link=link))
    return short_url

# Функиця генерации короткого урла с солью на основании id записи из БД
def simple_shorter_salt(urls_id):
    hashids = Hashids(salt='amazing smg3', min_length=6)
    link = hashids.encode(urls_id)
    short_url = ('{link}'.format(link=link))
    return short_url

# Функция взаимодействия с базой данных PostgreSQL
def data_base_interaction(site):
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(user='postgres',
                                      password='123',
                                      host='192.168.68.110',
                                      port='6432',
                                      database='urls')
        cursor = connection.cursor()
        cursor.execute('SELECT shorturl, longurl FROM urls ' +
                       'WHERE longurl=%(longurl)s', {'longurl': site})
        select_result = cursor.fetchall()
        if len(select_result) != 0:
            return select_result[0][0]  # Возвращаем уже существующий shorturl из БД
        else:
            cursor.execute('INSERT INTO urls (longurl) VALUES (%(longurl)s)',  # Добавляем запись с longurl в БД
                           {'longurl': site})
            # connection.commit()
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
        ## print("ERROR with PostgreSQL", error)
        print("69 ERROR")
        time.sleep(0.5)
        if connection:
            cursor.close()
            connection.close()
            time.sleep(0.5)
    finally:
        if connection:
            cursor.close()
            connection.close()
        #   print("DB connection closed")


# Функции сервера fastAPI
# Чтобы запустить из cmd "uvicorn apiServer:app --reload"
app = FastAPI()
r = redis.Redis(host='192.168.68.110', port=6379)
call_db_retry_cnt = 3
@app.get("/api/v1/urls/short")
def get_request_processor(site):
    domain = 'https://smg3.ru/'
    redis_data = r.get(site)  # Получаем пару из Redis по longurl
    if redis_data is None:
        data = data_base_interaction(site)# Если в Redis нет значения, то взаимодействуем с PostgreSQL
        if data == None or str(data) == 'None':
            return JSONResponse(content={'error': 'DB_NONE'})
        else:
            short_url = domain + str(data)
            response = {"longUrl": site, "shortUrl": short_url, "redis": "miss"}
            r.set(site, short_url, ex=600)  # Добавляем в Redis пару
            return JSONResponse(content=response)
    else:  # Иначе возвращаем из Redis
        short_url = str(redis_data.decode('utf-8'))
        response = {"longUrl": site, "shortUrl": short_url, "redis": "hit"}
        return JSONResponse(content=response)

@app.get("/stop")
def stop():

    parent_pid = os.getpid()
    parent = psutil.Process(parent_pid)
    for child in parent.children(recursive=True):
        child.kill()
    parent.kill()



if __name__ == '__main__':
    uvicorn.run(app, host='192.168.68.110', port=8000)