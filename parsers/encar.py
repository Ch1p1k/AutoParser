import asyncio
import re
from typing import Optional

from bs4 import BeautifulSoup

from core.base_parser import BaseParser, VehicleListing
from utils.logger import setup_logger

logger = setup_logger(__name__)

class EncarParser(BaseParser):
    """
    Парсер для корейского автомаркетплейса Encar.
    Сайт работает как SPA (Single Page Application), поэтому используется
    управление браузером Playwright для ожидания загрузки контента.
    """
    source_name = 'encar'
    base_url = 'https://www.encar.com'

    async def search(self, query: str) -> list[VehicleListing]:
        """
        Выполняет поиск автомобилей по заданному запросу.
        """
        logger.info(f"Начинаем поиск на Encar по запросу: {query}")
        # Формируем примерный URL поиска. Реальный URL может зависеть от API
        search_url = f"{self.base_url}/dc/dc_carsearchlist.do?q={query}"
        return await self.parse_listing_page(search_url)

    async def parse_listing_page(self, url: str) -> list[VehicleListing]:
        """
        Собирает ссылки на карточки автомобилей со страницы списка.
        """
        listings = []
        try:
            # Используем кастомный User-Agent для обхода блокировок
            user_agent = self.browser.get_random_user_agent()
            logger.debug(f"Используем User-Agent: {user_agent}")

            # Переходим на страницу
            success = await self.browser.goto_safe(url)
            if not success:
                logger.error(f"Не удалось загрузить страницу списка: {url}")
                return listings

            # Ждем выполнения JavaScript и рендеринга SPA
            await self.browser.wait(2000)
            await asyncio.sleep(self.browser.get_random_delay())

            html_content = await self.browser.get_content()
            soup = BeautifulSoup(html_content, 'html.parser')

            # Ищем элементы карточек (селектор примерный, требует уточнения под верстку)
            car_cards = soup.select('.carList .list_item')

            for card in car_cards:
                car_link = card.select_one('a')
                if car_link and 'href' in car_link.attrs:
                    href = car_link['href']
                    # Извлекаем ID объявления из ссылки для формирования ссылки на деталку
                    match = re.search(r'carid=(\d+)', href)
                    if match:
                        car_id = match.group(1)
                        detail_url = f"https://www.encar.com/dc/dc_cardetailview.do?carid={car_id}"
                        
                        # Парсим каждую детальную страницу
                        vehicle = await self.parse_detail_page(detail_url)
                        if vehicle:
                            listings.append(vehicle)

            logger.info(f"Собрано {len(listings)} автомобилей со страницы списка.")
        except Exception as e:
            logger.error(f"Ошибка при парсинге страницы списка {url}: {e}")

        return listings

    async def parse_detail_page(self, url: str) -> Optional[VehicleListing]:
        """
        Извлекает подробные характеристики автомобиля с детальной страницы.
        """
        try:
            success = await self.browser.goto_safe(url)
            if not success:
                logger.error(f"Не удалось загрузить карточку авто: {url}")
                return None

            # Ожидаем подгрузки данных (включая изображения и скрытые поля)
            await self.browser.wait(1500)
            html_content = await self.browser.get_content()
            soup = BeautifulSoup(html_content, 'html.parser')

            # Извлекаем car_id из URL
            car_id_match = re.search(r'carid=(\d+)', url)
            car_id = car_id_match.group(1) if car_id_match else "unknown"

            # Извлекаем заголовок (марка, модель, комплектация)
            title_elem = soup.select_one('.prod_name')
            title = title_elem.text.strip() if title_elem else "Неизвестно"
            
            # Извлекаем цену и конвертируем в float
            price_elem = soup.select_one('.prod_price')
            price_text = price_elem.text.replace(',', '').strip() if price_elem else "0"
            price_match = re.sub(r'[^\d.]', '', price_text)
            price = float(price_match) if price_match else 0.0

            # Создаем объект VehicleListing со специфичной для Кореи валютой
            vehicle = VehicleListing(
                source=self.source_name,
                listing_id=car_id,
                url=url,
                title=title,
                price=price,
                currency='KRW',
                # TODO: Добавить извлечение make, model, year, mileage_km и других полей
            )
            
            logger.info(f"Успешно спарсили авто: {title} (ID: {car_id})")
            return vehicle

        except Exception as e:
            logger.error(f"Ошибка при разборе детальной страницы {url}: {e}")
            return None
