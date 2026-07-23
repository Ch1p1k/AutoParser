import asyncio
import re
from typing import List, Optional
from bs4 import BeautifulSoup

from core.base_parser import BaseParser, VehicleListing
from utils.logger import setup_logger

try:
    from utils.font_decoder import FontDecoder
except ImportError:
    FontDecoder = None

logger = setup_logger(__name__)

class AutoHomeParser(BaseParser):
    """
    Парсер каталога новых автомобилей Autohome.
    Включает логику для расшифровки цен и характеристик, скрытых через кастомные веб-шрифты.
    """
    source_name = 'autohome'
    base_url = 'https://www.autohome.com.cn'

    async def _decrypt_font_data(self, html: str, encrypted_text: str) -> str:
        """
        Поиск woff файла в CSS правилах (@font-face), его загрузка 
        и расшифровка текста (замена PUA Unicode символов).
        """
        if not FontDecoder:
            logger.warning("Модуль FontDecoder не импортирован. Возвращаем оригинальный текст.")
            return encrypted_text

        try:
            # Ищем ссылку на файл шрифта .woff или .ttf
            font_url_match = re.search(r"url\('([^']+\.woff)'\)", html)
            if not font_url_match:
                font_url_match = re.search(r'url\("([^"]+\.woff)"\)', html)
            
            if not font_url_match:
                logger.warning("Не удалось найти ссылку на шрифт в HTML.")
                return encrypted_text

            font_url = font_url_match.group(1)
            if font_url.startswith('//'):
                font_url = f"https:{font_url}"

            logger.info(f"Найден шрифт для расшифровки: {font_url}")
            
            # Декодируем текст
            # (Предполагается, что FontDecoder умеет скачивать шрифт по URL)
            decoder = FontDecoder(font_url)
            decrypted_text = decoder.decode(encrypted_text)
            return decrypted_text

        except Exception as e:
            logger.error(f"Ошибка при расшифровке шрифта: {e}")
            return encrypted_text

    async def search(self, query: str) -> List[VehicleListing]:
        """
        Поиск по моделям (сериям) на Autohome.
        """
        logger.info(f"Поиск моделей по запросу: {query}")
        search_url = f"https://sou.autohome.com.cn/zonghe?q={query}"
        return await self.parse_listing_page(search_url)

    async def parse_listing_page(self, url: str) -> List[VehicleListing]:
        """
        Парсинг страницы со списком моделей (series) или дилерских цен.
        """
        logger.info(f"Загрузка страницы списка: {url}")
        success = await self.browser.goto_safe(url)
        if not success:
            logger.error(f"Ошибка перехода по URL: {url}")
            return []

        await self.browser.wait(int(self.get_random_delay() * 1000))
        html = await self.browser.get_content()
        soup = BeautifulSoup(html, 'html.parser')
        
        listings = []
        try:
            # Ищем элементы списка
            items = soup.select('.list-cont .list-cont-bg, .list-dl')
            for item in items:
                title_elem = item.select_one('.main-title a, dt a')
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                detail_url = title_elem.get('href', '')
                if detail_url and detail_url.startswith('//'):
                    detail_url = f"https:{detail_url}"
                
                # Извлекаем цену
                price_elem = item.select_one('.font-arial, .lever-price')
                price_raw = price_elem.text.strip() if price_elem else ''
                
                # Декодируем цену
                price = await self._decrypt_font_data(html, price_raw) if price_raw else ''
                
                listings.append(VehicleListing(
                    source=self.source_name,
                    url=detail_url,
                    title=title,
                    price=price,
                    currency='CNY'
                ))
        except Exception as e:
            logger.error(f"Ошибка при парсинге страницы {url}: {e}")
            
        return listings

    async def parse_detail_page(self, url: str) -> Optional[VehicleListing]:
        """
        Парсинг детальных технических характеристик и цен комплектации.
        """
        logger.info(f"Загрузка страницы характеристик: {url}")
        success = await self.browser.goto_safe(url)
        if not success:
            logger.error(f"Не удалось открыть страницу {url}")
            return None

        await self.browser.wait(int(self.get_random_delay() * 1000))
        html = await self.browser.get_content()
        soup = BeautifulSoup(html, 'html.parser')

        try:
            # Название серии/модели
            title_elem = soup.select_one('.name-text, .subnav-title-name')
            title = title_elem.text.strip() if title_elem else ''
            
            # Извлечение цены
            price_elem = soup.select_one('.price-text, .information-price')
            price_raw = price_elem.text.strip() if price_elem else ''
            price = await self._decrypt_font_data(html, price_raw) if price_raw else ''
            
            # Извлечение других характеристик: двигатель, коробка, и т.д.
            # На Autohome параметры обычно лежат в таблицах с классоem 'config-table'
            # или списках параметров 'param-item'
            
            return VehicleListing(
                source=self.source_name,
                url=url,
                title=title,
                price=price,
                currency='CNY'
            )
        except Exception as e:
            logger.error(f"Ошибка сбора деталей с {url}: {e}")
            return None
