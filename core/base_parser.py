"""
Базовый абстрактный класс парсера и модель данных VehicleListing.
Все парсеры площадок наследуются от BaseParser.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import random

import config


@dataclass
class VehicleListing:
    """Единая модель данных для транспортного средства (все площадки)"""
    source: str = ""                    # Название площадки (dubicars, autoscout24, ...)
    listing_id: str = ""                # Уникальный ID объявления на площадке
    url: str = ""                       # Прямая ссылка на объявление
    title: str = ""                     # Полное название (марка + модель + комплектация)
    make: str = ""                      # Марка (Toyota, BMW, ...)
    model: str = ""                     # Модель (Camry, X5, ...)
    trim: str = ""                      # Комплектация / версия
    year: Optional[int] = None          # Год выпуска
    price: Optional[float] = None       # Цена
    currency: str = ""                  # Валюта (USD, EUR, KRW, CNY, AED)
    mileage_km: Optional[int] = None    # Пробег в километрах
    fuel_type: str = ""                 # Тип топлива
    transmission: str = ""              # КПП (Автомат / Механика)
    body_type: str = ""                 # Тип кузова
    color: str = ""                     # Цвет
    location: str = ""                  # Местоположение
    seller_type: str = ""               # Тип продавца (Дилер / Частное лицо)
    image_url: str = ""                 # URL главного фото
    parsed_at: datetime = field(default_factory=datetime.now)  # Дата и время парсинга


class BaseParser(ABC):
    """
    Базовый абстрактный класс для всех парсеров.
    Каждый парсер площадки наследуется от него и реализует абстрактные методы.
    """

    source_name: str = "unknown"  # Переопределяется в дочерних классах

    def __init__(self, browser_manager):
        """
        Инициализация парсера.
        :param browser_manager: экземпляр BrowserManager для управления браузером
        """
        self.browser = browser_manager

    @abstractmethod
    async def search(self, query: str, max_pages: int = 3, min_year: Optional[int] = None, max_year: Optional[int] = None) -> List[VehicleListing]:
        """Поиск объявлений по текстовому запросу и фильтрам по годам"""
        pass

    @abstractmethod
    async def parse_listing_page(self, url: str) -> List[VehicleListing]:
        """Парсинг страницы со списком объявлений"""
        pass

    @abstractmethod
    async def parse_detail_page(self, url: str) -> Optional[VehicleListing]:
        """Парсинг страницы конкретного объявления"""
        pass

    def get_random_delay(self) -> float:
        """Получить случайную задержку между запросами"""
        return random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX)

    def get_random_user_agent(self) -> str:
        """Получить случайный User-Agent из списка конфигурации"""
        return random.choice(config.USER_AGENTS)
