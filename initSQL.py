import psycopg2
from psycopg2 import Error
# Подготовка БД

# Создание таблицы urls
connection = None
cursor = None
try:
    connection = psycopg2.connect(user='postgres',
                                  password='123',
                                  host='127.0.0.1',
                                  port='5432',
                                  database='urls')

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