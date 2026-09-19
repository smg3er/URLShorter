import psycopg2
from psycopg2 import sql

from config import get_positive_int_env, get_required_env


def load_database_config():
    return {
        'user': get_required_env('POSTGRES_USER'),
        'password': get_required_env('POSTGRES_PASSWORD'),
        'host': get_required_env('POSTGRES_HOST'),
        'admin_port': get_positive_int_env('POSTGRES_ADMIN_PORT', maximum=65535),
        'admin_database': get_required_env('POSTGRES_ADMIN_DB'),
        'database': get_required_env('POSTGRES_DB'),
    }


def create_database(settings, connect_func=psycopg2.connect):
    connection = connect_func(
        user=settings['user'],
        password=settings['password'],
        host=settings['host'],
        port=settings['admin_port'],
        database=settings['admin_database'],
    )
    try:
        connection.autocommit = True
        cursor = connection.cursor()
        try:
            database_name = sql.Identifier(settings['database'])
            cursor.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(database_name))
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(database_name))
            print(f"Database {settings['database']} created successfully")
        finally:
            cursor.close()
    finally:
        connection.close()


def create_table(settings, connect_func=psycopg2.connect):
    connection = connect_func(
        user=settings['user'],
        password=settings['password'],
        host=settings['host'],
        port=settings['admin_port'],
        database=settings['database'],
    )
    try:
        cursor = connection.cursor()
        try:
            cursor.execute('''CREATE TABLE urls
                              (id SERIAL PRIMARY KEY NOT NULL,
                               shorturl VARCHAR(16) UNIQUE,
                               longurl VARCHAR(512) UNIQUE NOT NULL);''')
            connection.commit()
            print('Table created successfully')
        finally:
            cursor.close()
    finally:
        connection.close()


def main(connect_func=psycopg2.connect):
    settings = load_database_config()
    create_database(settings, connect_func)
    create_table(settings, connect_func)


if __name__ == '__main__':
    main()
