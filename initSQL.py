import os
import psycopg2
from psycopg2 import Error
# Подготовка БД
# Создание базы urls
connection = None
cursor = None
try:
    connection = psycopg2.connect(user=os.getenv('POSTGRES_USER', 'postgres'),
                                  password=os.getenv('POSTGRES_PASSWORD', '123'),
                                  host=os.getenv('POSTGRES_HOST', '150.241.76.47'),  # 150.241.76.47 - stockholm,  127.0.0.1 - local
                                  port=os.getenv('POSTGRES_PORT', '5432'))
    connection.autocommit = True
    cursor = connection.cursor()
    drop_database_query = 'DROP DATABASE IF EXISTS urls'
    create_database_query = 'CREATE DATABASE urls'
    cursor.execute(drop_database_query)
    cursor.execute(create_database_query)
    print('database urls create successful ')
except (Exception, Error) as error:
    print("ERROR with PostgreSQL", error)


# Создание таблицы urls
connection = None
cursor = None
try:
    connection = psycopg2.connect(user=os.getenv('POSTGRES_USER', 'postgres'),
                                  password=os.getenv('POSTGRES_PASSWORD', '123'),
                                  host=os.getenv('POSTGRES_HOST', '150.241.76.47'),  # 150.241.76.47 - stockholm,  127.0.0.1 - local
                                  port=os.getenv('POSTGRES_PORT', '5432'),
                                  database=os.getenv('POSTGRES_DB', 'urls'))

    cursor = connection.cursor()
    create_table_query = ''' CREATE TABLE urls
                                (id SERIAL PRIMARY KEY NOT NULL,
                                shorturl VARCHAR(16) UNIQUE,
                                longurl VARCHAR(512) UNIQUE NOT NULL); '''
    cursor.execute(create_table_query)
    connection.commit()
    print('Table created successful')
except (Exception, Error) as error:
    print("ERROR with PostgreSQL", error)

finally:
    if connection:
        cursor.close()
        connection.close()
        print("DB connection closed")