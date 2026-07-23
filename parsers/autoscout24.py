import asyncio
import re
from typing import List, Optional
from datetime import datetime
from bs4 import BeautifulSoup

from core.base_parser import BaseParser, VehicleListing
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AutoScout24Parser(BaseParser):
    source_name = 'autoscout24'
    base_url = 'https://www.autoscout24.com'

    async def search(self, query: str = "", make: str = "", model: str = "", max_pages: int = 1) -> List[VehicleListing]:
        """
        Выполняет поиск автомобилей на AutoScout24.
        Поддерживает поиск по марке/модели или по ключевым словам.
        """
        results = []
        for page in range(1, max_pages + 1):
            if make and model:
                # Поиск по марке и модели
                url = f"{self.base_url}/lst/{make}/{model}?atype=C&cy=D&page={page}"
            else:
                # Поиск по ключевому слову с фильтром по странам Европы
                url = f"{self.base_url}/lst?sort=standard&desc=0&atype=C&cy=D,A,B,E,F,I,L,NL&page={page}&query={query}"
            
            logger.info(f"Переход на страницу: {url}")
            success = await self.browser.goto_safe(url)
            if not success:
                logger.error(f"Не удалось открыть страницу {url}")
                continue
                
            await self.browser.wait(self.get_random_delay() * 1000)
            
            content = await self.browser.get_content()
            listings = await self.parse_listing_page(content)
            
            for listing in listings:
                results.append(listing)
                
            if not listings:
                logger.warning("Объявления не найдены, прерывание поиска.")
                break
                
        return results

    async def parse_listing_page(self, html_content: str) -> List[VehicleListing]:
        """
        Парсит страницу с результатами поиска и извлекает карточки автомобилей.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        # Находим все карточки автомобилей с fallback селекторами
        articles = soup.find_all('article', {'data-type': 'list-page-item'})
        if not articles:
            articles = soup.find_all('div', class_=re.compile(r'cldt-summary-full-item'))
            
        for article in articles:
            try:
                listing = VehicleListing(source=self.source_name, currency='EUR')
                
                # Извлечение ID и URL
                listing.listing_id = article.get('data-guid') or article.get('id')
                link_tag = article.find('a', {'data-item-name': 'detail-page-link'})
                if link_tag and link_tag.get('href'):
                    listing.url = self.base_url + link_tag.get('href')
                
                # Название
                title_tag = article.find('h2')
                if title_tag:
                    listing.title = title_tag.get_text(strip=True)
                    
                # Цена
                price_tag = article.find('span', {'data-item-name': 'price'})
                if price_tag:
                    price_str = price_tag.get_text(strip=True)
                    price_numbers = re.sub(r'[^\d]', '', price_str)
                    if price_numbers:
                        listing.price = int(price_numbers)
                
                # Дополнительные характеристики (год, пробег, трансмиссия, топливо)
                details_div = article.find('div', {'data-item-name': 'vehicle-details'})
                if details_div:
                    details = [span.get_text(strip=True) for span in details_div.find_all('span')]
                    for detail in details:
                        if 'km' in detail.lower():
                            km_str = re.sub(r'[^\d]', '', detail)
                            if km_str:
                                listing.mileage_km = int(km_str)
                        elif re.match(r'\d{2}/\d{4}', detail):
                            # Год выпуска формата MM/YYYY
                            listing.year = int(detail.split('/')[1])
                        elif detail in ['Manual', 'Automatic', 'Semi-automatic']:
                            listing.transmission = detail
                        elif detail in ['Gasoline', 'Diesel', 'Electric', 'Hybrid']:
                            listing.fuel_type = detail
                
                listing.parsed_at = datetime.now()
                listings.append(listing)
            except Exception as e:
                logger.error(f"Ошибка при парсинге карточки авто: {e}")
                
        return listings

    async def parse_detail_page(self, url: str) -> Optional[VehicleListing]:
        """
        Парсит детальную страницу автомобиля для извлечения полных характеристик.
        """
        success = await self.browser.goto_safe(url)
        if not success:
            return None
            
        await self.browser.wait(self.get_random_delay() * 1000)
        content = await self.browser.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        
        listing = VehicleListing(source=self.source_name, url=url, currency='EUR')
        
        try:
            # Извлечение названия
            title_tag = soup.find('h1')
            if title_tag:
                listing.title = title_tag.get_text(strip=True)
                
            # Извлечение цены
            price_tag = soup.find('span', {'data-testid': 'prime-price'})
            if price_tag:
                price_str = price_tag.get_text(strip=True)
                price_numbers = re.sub(r'[^\d]', '', price_str)
                if price_numbers:
                    listing.price = int(price_numbers)
                    
            # Дополнительные характеристики с детальной страницы
            # ...
            
            listing.parsed_at = datetime.now()
            return listing
        except Exception as e:
            logger.error(f"Ошибка при парсинге детальной страницы {url}: {e}")
            return None
