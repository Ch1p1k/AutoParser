"""
CLI точка входа для AutoParser.

Примеры использования:
  python main.py -p dubicars -q 'Toyota Land Cruiser' --pages 5
  python main.py -p autoscout24 -q 'BMW X5' -o json
  python main.py -p all -q 'Mercedes'
"""

import argparse
import asyncio
import sys
import os
import time
from typing import Dict, Type, List

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.base_parser import BaseParser, VehicleListing
from core.browser import BrowserManager
from core.export import export_to_csv, export_to_json, export_to_excel
from core.proxy_manager import ProxyManager
from utils.logger import setup_logger

# === Импорт парсеров ===
from parsers.dubicars import DubiCarsParser
from parsers.autoscout24 import AutoScout24Parser
from parsers.bidcars import BidCarsParser
from parsers.encar import EncarParser
from parsers.che168 import Che168Parser
from parsers.autohome import AutoHomeParser

# Словарь доступных парсеров (название -> класс)
PARSERS: Dict[str, Type[BaseParser]] = {
    'dubicars': DubiCarsParser,       # ОАЭ
    'autoscout24': AutoScout24Parser, # Европа
    'bidcars': BidCarsParser,         # США
    'encar': EncarParser,             # Корея
    'che168': Che168Parser,           # Китай (б/у авто)
    'autohome': AutoHomeParser,       # Китай (каталог новых)
}


async def main() -> None:
    """Главная функция: парсинг CLI-аргументов, запуск парсера, экспорт результатов."""

    parser = argparse.ArgumentParser(
        description="AutoParser — автоматический парсер автомобильных площадок.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python main.py -p dubicars -q 'Toyota Land Cruiser' --pages 5
  python main.py -p dubicars -q 'BMW X5' -o json
  python main.py -p all -q 'Mercedes'
        """
    )
    parser.add_argument('-p', '--platform', required=True,
                        choices=list(PARSERS.keys()) + ['all'],
                        help="Платформа для парсинга или 'all' для всех")
    parser.add_argument('-q', '--query', default='', type=str,
                        help="Поисковый запрос (например, 'Toyota Camry')")
    parser.add_argument('--pages', type=int, default=3,
                        help="Максимальное количество страниц (по умолчанию 3)")
    parser.add_argument('-o', '--output', choices=['csv', 'json', 'excel'], default='csv',
                        help="Формат вывода (по умолчанию csv)")
    parser.add_argument('--min-year', type=int, default=None,
                        help="Минимальный год выпуска (например, 2022)")
    parser.add_argument('--max-year', type=int, default=None,
                        help="Максимальный год выпуска (например, 2026)")
    parser.add_argument('--proxy-file', type=str,
                        help="Путь к файлу с прокси (по одному на строку)")
    parser.add_argument('--headless', action='store_true',
                        help="Запуск браузера в фоновом режиме (без окна)")

    args = parser.parse_args()

    # Настройка логгера
    logger = setup_logger('autoparser')
    logger.info("=" * 50)
    logger.info("Запуск AutoParser")
    logger.info(f"Платформа: {args.platform}")
    logger.info(f"Запрос: '{args.query}'")
    logger.info(f"Года: {args.min_year or 'все'} - {args.max_year or 'все'}")
    logger.info(f"Страниц: {args.pages}, Формат: {args.output}")
    logger.info("=" * 50)

    start_time = time.time()

    # Загрузка прокси (если указан файл)
    proxy_dict = None
    if args.proxy_file:
        proxy_manager = ProxyManager()
        proxy_manager.load_from_file(args.proxy_file)
        proxy_dict = proxy_manager.get_next()
        if proxy_dict:
            logger.info(f"Используется прокси: {proxy_dict.get('server', '?')}")
        else:
            logger.warning("Файл прокси пуст или все прокси недоступны.")

    # Определяем, какие парсеры запускать
    if args.platform == 'all':
        platforms_to_run = list(PARSERS.keys())
    else:
        platforms_to_run = [args.platform]

    all_results: List[VehicleListing] = []

    # Запуск браузера и парсеров
    async with BrowserManager(headless=args.headless, proxy=proxy_dict) as browser:
        for platform_name in platforms_to_run:
            parser_cls = PARSERS[platform_name]
            logger.info(f"Запуск парсера: {platform_name} ({parser_cls.__name__})")

            try:
                parser_instance = parser_cls(browser)
                results = await parser_instance.search(
                    query=args.query,
                    max_pages=args.pages,
                    min_year=args.min_year,
                    max_year=args.max_year
                )

                # Фильтрация по годам в коде (на случай если сайт не отфильтровал)
                if args.min_year or args.max_year:
                    filtered = []
                    for r in results:
                        if r.year is not None:
                            if args.min_year and r.year < args.min_year:
                                continue
                            if args.max_year and r.year > args.max_year:
                                continue
                        filtered.append(r)
                    results = filtered

                all_results.extend(results)
                logger.info(f"[{platform_name}] Найдено {len(results)} объявлений после фильтрации")
            except Exception as e:
                logger.error(f"[{platform_name}] Ошибка: {e}")

    # Экспорт результатов
    base_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(base_dir, 'results')
    os.makedirs(results_dir, exist_ok=True)

    if all_results:
        timestamp = int(time.time())
        if args.output == 'csv':
            output_file = os.path.join(results_dir, f'results_{timestamp}.csv')
            export_to_csv(all_results, output_file)
        elif args.output == 'json':
            output_file = os.path.join(results_dir, f'results_{timestamp}.json')
            export_to_json(all_results, output_file)
        else:
            output_file = os.path.join(results_dir, f'results_{timestamp}.xlsx')
            export_to_excel(all_results, output_file)

        logger.info(f"Результаты сохранены в: {output_file}")
    else:
        output_file = ""
        logger.warning("Не найдено ни одного объявления. Файл не создан.")

    # Итоговая сводка
    elapsed = time.time() - start_time
    print("\n" + "=" * 50)
    print("Сводка")
    print("=" * 50)
    print(f"  Платформы:   {', '.join(platforms_to_run)}")
    print(f"  Запрос:      '{args.query}'")
    print(f"  Найдено:     {len(all_results)} объявлений")
    print(f"  Время:       {elapsed:.1f} сек")
    if output_file:
        print(f"  Файл:        {output_file}")
    print("=" * 50)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма прервана пользователем (Ctrl+C). Выход...")
        sys.exit(0)
