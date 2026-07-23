import asyncio
import re
from typing import List, Optional
from datetime import datetime
from bs4 import BeautifulSoup

from core.base_parser import BaseParser, VehicleListing
from utils.logger import setup_logger

logger = setup_logger(__name__)

class BidCarsParser(BaseParser):
    source_name = 'bidcars'
    base_url = 'https://bid.cars'

    async def search(self, query: str = "", max_pages: int = 1) -> List[VehicleListing]:
        """
        Ищет автомобили на аукционах США через сайт BidCars.
        """
        results = []
        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/en/search?q={query}&page={page}"
            logger.info(f"Переход на страницу: {url}")
            
            success = await self.browser.goto_safe(url)
            if not success:
                logger.error(f"Не удалось открыть страницу {url}")
                continue
                
            await self.browser.wait(self.get_random_delay() * 1000)
            
            content = await self.browser.get_content()
            listings = await self.parse_listing_page(content)
            
            results.extend(listings)
                
            if not listings:
                logger.warning("Объявления не найдены, прерывание поиска.")
                break
                
        return results

    async def parse_listing_page(self, html_content: str) -> List[VehicleListing]:
        """
        Парсит страницу результатов поиска на аукционе и извлекает карточки лотов.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        # Находим все карточки аукционов
        cards = soup.find_all('div', class_=re.compile(r'lot-card|vehicle-card'))
        
        for card in cards:
            try:
                listing = VehicleListing(source=self.source_name, currency='USD')
                
                # URL
                link_tag = card.find('a', href=True)
                if link_tag:
                    listing.url = self.base_url + link_tag['href']
                    # Извлечение ID лота из URL или атрибута
                    listing.listing_id = link_tag['href'].split('/')[-1]
                
                # Название (из которого можно извлечь год, марку и модель)
                title_tag = card.find(['h2', 'h3'])
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    listing.title = title
                    
                    # Пытаемся распарсить год, марку, модель ('2023 Toyota Camry')
                    match = re.match(r'^(\d{4})\s+([A-Za-z\-]+)\s+(.+)$', title)
                    if match:
                        listing.year = int(match.group(1))
                        listing.make = match.group(2)
                        listing.model = match.group(3)
                
                # VIN, пробег, повреждения
                details_list = card.find_all('li')
                for li in details_list:
                    text = li.get_text(strip=True)
                    if 'Odometer:' in text or 'Mileage:' in text:
                        mil_str = re.sub(r'[^\d]', '', text)
                        if mil_str:
                            listing.mileage_km = int(int(mil_str) * 1.60934)  # Мили в км
                
                # Цена
                price_tag = card.find(string=re.compile(r'\$'))
                if price_tag:
                    price_str = price_tag.get_text(strip=True)
                    price_numbers = re.sub(r'[^\d]', '', price_str)
                    if price_numbers:
                        listing.price = int(price_numbers)
                
                listing.parsed_at = datetime.now()
                listings.append(listing)
            except Exception as e:
                logger.error(f"Ошибка при парсинге карточки BidCars: {e}")
                
        return listings

    async def parse_detail_page(self, url: str) -> Optional[VehicleListing]:
        """
        Парсит детальную страницу лота для извлечения полной информации об аукционе.
        (VIN, тип повреждения, номер лота и т.д.)
        """
        success = await self.browser.goto_safe(url)
        if not success:
            return None
            
        await self.browser.wait(self.get_random_delay() * 1000)
        content = await self.browser.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        
        listing = VehicleListing(source=self.source_name, url=url, currency='USD')
        
        try:
            title_tag = soup.find('h1')
            if title_tag:
                title = title_tag.get_text(strip=True)
                listing.title = title
                match = re.match(r'^(\d{4})\s+([A-Za-z\-]+)\s+(.+)$', title)
                if match:
                    listing.year = int(match.group(1))
                    listing.make = match.group(2)
                    listing.model = match.group(3)
                    
            # Извлечение детальных параметров
            
            listing.parsed_at = datetime.now()
            return listing
        except Exception as e:
            logger.error(f"Ошибка при парсинге детальной страницы BidCars {url}: {e}")
            return None
