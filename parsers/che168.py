import asyncio
import datetime
from typing import List, Optional
from bs4 import BeautifulSoup

from core.base_parser import BaseParser, VehicleListing
from utils.logger import setup_logger

logger = setup_logger(__name__)

class Che168Parser(BaseParser):
    """
    Парсер для сайта che168.com (китайский рынок подержанных автомобилей).
    """
    source_name = 'che168'
    base_url = 'https://www.che168.com'

    async def search(self, query: str) -> List[VehicleListing]:
        """
        Поиск автомобилей по текстовому запросу.
        """
        logger.info(f"Начинаем поиск по запросу: {query}")
        # Переходим на страницу поиска по всей стране
        search_url = f"{self.base_url}/china/list/?pvareaid=100945&key={query}"
        return await self.parse_listing_page(search_url)

    async def parse_listing_page(self, url: str) -> List[VehicleListing]:
        """
        Парсинг страницы со списком автомобилей (карточки).
        """
        logger.info(f"Загрузка страницы со списком: {url}")
        success = await self.browser.goto_safe(url)
        if not success:
            logger.error(f"Не удалось загрузить страницу {url}")
            return []

        # Ждем загрузки динамических элементов
        await self.browser.wait(int(self.get_random_delay() * 1000))
        html = await self.browser.get_content()
        soup = BeautifulSoup(html, 'html.parser')
        
        listings = []
        try:
            # Ищем карточки машин в списке
            cards = soup.select('ul.viewlist_ul li.cards-li')
            for card in cards:
                a_tag = card.select_one('a.carinfo')
                if not a_tag:
                    continue
                
                detail_url = a_tag.get('href', '')
                if detail_url and not detail_url.startswith('http'):
                    detail_url = f"https:{detail_url}"
                
                title = card.select_one('.card-name')
                price_tag = card.select_one('.pro-price')
                
                # Обрабатываем потенциальное шифрование шрифта или сложные форматы
                # В che168 иногда цена бывает текстом, а иногда картинкой/шрифтом
                price_text = price_tag.text.strip() if price_tag else ''
                
                listing = VehicleListing(
                    source=self.source_name,
                    url=detail_url,
                    title=title.text.strip() if title else '',
                    price=price_text,
                    currency='CNY'
                )
                listings.append(listing)
        except Exception as e:
            logger.error(f"Ошибка при парсинге страницы списка {url}: {e}")
            
        return listings

    async def parse_detail_page(self, url: str) -> Optional[VehicleListing]:
        """
        Сбор детальной информации (спецификаций) о конкретном автомобиле.
        Обработка кодировки (GBK/GB2312) происходит на уровне Playwright или BeautifulSoup.
        """
        logger.info(f"Загрузка детальной страницы: {url}")
        success = await self.browser.goto_safe(url)
        if not success:
            logger.error(f"Не удалось открыть страницу: {url}")
            return None

        await self.browser.wait(int(self.get_random_delay() * 1000))
        html = await self.browser.get_content()
        soup = BeautifulSoup(html, 'html.parser')

        try:
            # Название: 品牌 (Make) и 车系 (Model)
            title_elem = soup.select_one('.car-brand-name')
            title = title_elem.text.strip() if title_elem else ''

            # Цена: 售价 (Price)
            price_elem = soup.select_one('.car-price ins')
            price = price_elem.text.strip() if price_elem else ''
            
            # Извлекаем параметры из карточки характеристик
            details_ul = soup.select('.brand-unit-item li')
            mileage = ''
            first_reg = ''
            transmission = ''
            
            for li in details_ul:
                text = li.text.strip()
                if '万公里' in text:  # 行驶里程 (mileage in 10k km)
                    # Вытаскиваем числовое значение
                    val = text.replace('万公里', '').replace('里程', '').strip()
                    try:
                        # Переводим в обычные км
                        mileage = str(int(float(val) * 10000))
                    except ValueError:
                        mileage = val
                elif '年' in text and '月' in text:  # 首次上牌时间 (first registration)
                    first_reg = text.strip()
                elif '自动' in text or '手动' in text:  # 变速箱 (transmission)
                    transmission = text.strip()
                    
            # Предупреждаем о возможных зашифрованных значениях
            if not price or any(c in price for c in ['&#', '\\u']):
                logger.warning(f"Возможно цена зашифрована шрифтом на странице {url}")
                    
            return VehicleListing(
                source=self.source_name,
                url=url,
                title=title,
                price=price,
                currency='CNY',
                mileage_km=mileage,
                transmission=transmission,
                year=first_reg
            )
        except Exception as e:
            logger.error(f"Ошибка при сборе детальной информации {url}: {e}")
            return None
