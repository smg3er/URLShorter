## Простое приложение для генерации коротких ссылок

Короткий урл генерится пока что внешней библиотекой, размер в 6 символов, пример:
"9aAOdv"

Символы короткого урла могут быть из словаря длины 62 :
"abcdefgjijklmnopqrstuvwxyz" + 
"ABCDEFGHIJKLMNOPQRSTUVWXYZ" +
"0123456789"

Короткий урл может содержать уникальных значений:
62^6 = 56 800 235 584

При наличии совпадения, делается еще 1 попытка перегенерить короткий урл с слолью
Итого решение может предоставить 2*(56 800 235 584) уникальных коротких урлов

---
Порядок действий для запуска:
1. top10milliondomains.zip следует разархивировать
2. Поднять postgreSQL
3. Выполнить sqlPreparing.py
4. Запустить apiServer.py
5. Запустить генератор запросов frontApp.py
----

### TODO
    - Оптимизировать взаимодействие с БД
    - Обработка исключений и проброс на фронт
    - Написать свою функцию генерацию shortUrl (сейчас использована библиотека hashids)

## Локальное окружение (Docker)

Требуется Docker Desktop (compose v2). Два независимых стека:

- `docker-compose.db.yml` — PostgreSQL + PgBouncer (transaction-pooling)
- `docker-compose.redis.yml` — Redis + RedisInsight (UI)

Порты биндятся только на `127.0.0.1`: `5432` (postgres), `6432` (pgbouncer), `6379` (redis), `8001` (RedisInsight UI).

### Настройка

```bat
copy .env.example .env
rem заполнить .env реальными значениями (см. комментарии в файле)
```

`.env` не коммитится (в `.gitignore`).

### Запуск / остановка

```bat
docker compose -f docker-compose.db.yml up -d
docker compose -f docker-compose.redis.yml up -d

docker compose -f docker-compose.db.yml down
docker compose -f docker-compose.redis.yml down
```

### Инициализация схемы БД

`initSQL.py` принудительно пересоздаёт базу `urls` — запускается вручную, compose схему не трогает. Инициализация идёт напрямую в postgres (5432, мимо пула):

```bat
set "POSTGRES_HOST=127.0.0.1"
set "POSTGRES_PORT=5432"
py initSQL.py
```

### Запуск приложения

Приложение работает через pgbouncer (6432) и Redis (6379):

```bat
set "POSTGRES_HOST=127.0.0.1"
set "POSTGRES_PORT=6432"
set "REDIS_HOST=127.0.0.1"
set "REDIS_PORT=6379"
py apiServer.py
```

Примечание: хост/порт в `uvicorn.run` внутри `apiServer.py` захардкожены (`192.168.68.110:8000`, существующий техдолг). Если этот IP не назначен машине, запускать через:

```bat
py -m uvicorn apiServer:app --host 127.0.0.1 --port 8000
```

Актуатор метрик: `http://127.0.0.1:8000/actuator/prometheus/` (со слэшем).

### Отладочная инфа (удалить потом)

Проверить отсутствие дубликатов (после добавление constraints их не должно быть)
```
select * from urls u where id in (
	select id from urls where longurl in (
			select longurl from (
				select longurl, count(*) as repeat_qty from urls u 
				group by longurl, longurl 
				having count(*)>1)))
```