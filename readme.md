# URLShorter

Учебный сервис сокращения ссылок на FastAPI. Короткий код создаётся библиотекой `hashids`, пары ссылок хранятся в PostgreSQL и кэшируются в Redis. `frontApp.py` генерирует тестовую нагрузку, а `metricsPush.py` отправляет метрики в Pushgateway.

Проект рассчитан на Python 3.10.

## Установка зависимостей

```bat
python -m pip install -r requirements.txt
```

## Единый файл конфигурации

Все Python-компоненты автоматически загружают один рабочий файл `URLShorter/.env`. Дополнительные env-файлы и предварительные команды `set` не нужны. Переменные, заданные окружением процесса, имеют приоритет над значениями из файла.

Рабочий `.env` хранится в репозитории и уже присутствует после `git clone`, поэтому создавать или копировать его перед запуском не нужно. Для другого стенда измените значения в `.env` либо переопределите их переменными окружения процесса.

`.env.example` остаётся безопасным справочным шаблоном и во время работы не загружается. Не добавляйте production-секреты в версионируемый `.env`.

Группы настроек:

- `POSTGRES_*` — обычное подключение приложения, прямое административное подключение и имя целевой БД;
- `REDIS_*` — подключение к Redis;
- `API_*`, `SHORT_URL_BASE_URL`, `REDIS_TTL_SECONDS`, `HASHIDS_*` — HTTP-сервер и генерация коротких ссылок;
- `METRICS_*` — Pushgateway и интервал отправки метрик;
- `FRONT_APP_*` — адрес API, CSV-файл, профиль нагрузки и timeout запросов.

Полный список ключей и безопасные примеры находятся в `.env.example`. Если обязательный ключ отсутствует или имеет неверный формат, компонент завершится до подключения к сети, чтения CSV или запуска потоков.

## Локальная тестовая инфраструктура

Docker используется только для локальных PostgreSQL/PgBouncer, Redis и monitoring-стека. Конфигурацию самого приложения определяет корневой `.env`.

```bat
docker compose -f docker-compose.db.yml up -d
docker compose -f docker-compose.redis.yml up -d
docker compose -f docker-compose.monitoring.yml up -d
```

Порты локальных сервисов: PostgreSQL `5432`, PgBouncer `6432`, Redis `6379`, RedisInsight `8001`, Prometheus `9090`, Pushgateway `9091`, Grafana `3000`.

Остановка:

```bat
docker compose -f docker-compose.monitoring.yml down
docker compose -f docker-compose.redis.yml down
docker compose -f docker-compose.db.yml down
```

## Запуск компонентов

### 1. Инициализация PostgreSQL

Внимание: `initSQL.py` удаляет и заново создаёт базу, указанную в `POSTGRES_DB`. Для административного подключения используются `POSTGRES_ADMIN_PORT` и `POSTGRES_ADMIN_DB`, поэтому временно менять обычный `POSTGRES_PORT` не требуется.

```bat
python initSQL.py
```

### 2. API и встроенная отправка метрик

```bat
python apiServer.py
```

API использует `API_HOST` и `API_PORT`. Ручка сокращения: `/api/v1/urls/short?site=example.org`, метрики: `/actuator/prometheus/`.

Демон из `metricsPush.py` автоматически стартует вместе с API. Для отдельной проверки только демона его можно запустить самостоятельно:

```bat
python metricsPush.py
```

Не запускайте отдельный демон одновременно с API, если второй экземпляр отправителя метрик не нужен.

### 3. Генератор нагрузки

Распакуйте CSV с колонкой `Domain` и укажите путь в `FRONT_APP_DOMAINS_FILE`. Затем запустите:

```bat
python frontApp.py
```

Размер выборки, число потоков, запросы на поток, частота дополнительной выборки и HTTP timeout задаются ключами `FRONT_APP_*` в том же `.env`.

## TODO

- сделать операции PostgreSQL атомарными;
- добавить пул соединений и retry;
- закрыть служебную ручку `/stop` авторизацией;
- добавить редирект с короткой ссылки на исходный URL.
