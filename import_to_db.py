"""
Скрипт импорта сохранённых CSV результатов в базу данных PostgreSQL.
"""

import csv
import os
import sys
import psycopg2
from psycopg2.extras import execute_values

# Настройки подключения к PostgreSQL (замените на свои)
DB_CONFIG = {
    'dbname': 'AutoParser',
    'user': 'postgres',
    'password': '1234',
    'host': 'localhost',
    'port': 5432
}


def create_table_if_not_exists(cursor):
    """Создание таблицы и индексов в PostgreSQL."""
    create_query = """
    CREATE TABLE IF NOT EXISTS vehicle_listings (
        id SERIAL PRIMARY KEY,
        source VARCHAR(50) NOT NULL,
        listing_id VARCHAR(100) NOT NULL,
        url TEXT NOT NULL,
        title VARCHAR(255) NOT NULL,
        make VARCHAR(100),
        model VARCHAR(100),
        trim VARCHAR(100),
        year INT,
        price NUMERIC(15, 2),
        currency VARCHAR(10) DEFAULT 'USD',
        mileage_km INT,
        fuel_type VARCHAR(50),
        transmission VARCHAR(50),
        body_type VARCHAR(50),
        color VARCHAR(50),
        location VARCHAR(100),
        seller_type VARCHAR(50),
        image_url TEXT,
        parsed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT unique_source_listing UNIQUE (source, listing_id)
    );

    CREATE INDEX IF NOT EXISTS idx_vehicles_make_model ON vehicle_listings (make, model);
    CREATE INDEX IF NOT EXISTS idx_vehicles_price ON vehicle_listings (price);
    """
    cursor.execute(create_query)


def import_csv_to_postgres(csv_filepath: str, db_config: dict):
    """Импорт данных из CSV файла в PostgreSQL с обработкой дубликатов."""
    if not os.path.exists(csv_filepath):
        print(f"Ошибка: Файл {csv_filepath} не найден!")
        return

    print(f"Подключение к БД {db_config['dbname']}@{db_config['host']}...")
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        # 1. Создаем таблицу, если ее нет
        create_table_if_not_exists(cursor)

        # 2. Читаем CSV
        with open(csv_filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            print("CSV файл пуст.")
            return

        # 3. Подготовка данных для вставки
        data_tuples = []
        for r in rows:
            data_tuples.append((
                r.get('source'),
                r.get('listing_id'),
                r.get('url'),
                r.get('title'),
                r.get('make'),
                r.get('model'),
                r.get('trim'),
                int(r['year']) if r.get('year') else None,
                float(r['price']) if r.get('price') else None,
                r.get('currency'),
                int(r['mileage_km']) if r.get('mileage_km') else None,
                r.get('fuel_type'),
                r.get('transmission'),
                r.get('body_type'),
                r.get('color'),
                r.get('location'),
                r.get('seller_type'),
                r.get('image_url'),
                r.get('parsed_at')
            ))

        # 4. Выполняем быструю массовую вставку с игнорированием дубликатов (UPSERT)
        insert_query = """
        INSERT INTO vehicle_listings (
            source, listing_id, url, title, make, model, trim, year,
            price, currency, mileage_km, fuel_type, transmission,
            body_type, color, location, seller_type, image_url, parsed_at
        ) VALUES %s
        ON CONFLICT (source, listing_id) DO UPDATE SET
            price = EXCLUDED.price,
            mileage_km = EXCLUDED.mileage_km,
            parsed_at = EXCLUDED.parsed_at;
        """

        execute_values(cursor, insert_query, data_tuples)
        conn.commit()

        print(f"✅ Успешно импортировано {len(data_tuples)} записей из {csv_filepath} в БД!")

    except Exception as e:
        print(f"❌ Ошибка при импорте в БД: {e}")
    finally:
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование: python import_to_db.py results/results_XXXX.csv")
    else:
        import_csv_to_postgres(sys.argv[1], DB_CONFIG)
