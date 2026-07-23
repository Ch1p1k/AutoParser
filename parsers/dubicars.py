"""
Парсер для dubicars.com (ОАЭ, автомобильная площадка).
Извлекает объявления о продаже автомобилей с указанием цен в AED.
"""

import asyncio
import json
import random
import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from core.base_parser import BaseParser, VehicleListing
from utils.logger import setup_logger

logger = setup_logger(__name__)


class DubiCarsParser(BaseParser):
    """Парсер площадки dubicars.com (ОАЭ)"""

    source_name = 'dubicars'
    base_url = 'https://www.dubicars.com'

    def _parse_price(self, price_str: str) -> Optional[float]:
        """Парсинг строки цены (удаление 'AED', запятых, пробелов)."""
        if not price_str:
            return None
        clean = re.sub(r'[^\d.]', '', price_str)
        try:
            return float(clean) if clean else None
        except ValueError:
            return None

    def _parse_mileage(self, mileage_str: str) -> Optional[int]:
        """Парсинг строки пробега (удаление 'km', запятых, пробелов)."""
        if not mileage_str:
            return None
        clean = re.sub(r'[^\d]', '', mileage_str)
        try:
            return int(clean) if clean else None
        except ValueError:
            return None

    async def search(self, query: str, max_pages: int = 3, min_year: Optional[int] = None, max_year: Optional[int] = None) -> List[VehicleListing]:
        """
        Поиск автомобилей по текстовому запросу и годам выпуска.
        Использует официальные параметры URL DubiCars: k (keyword), yf (year from), yt (year to).
        """
        all_results = []
        query_encoded = query.replace(' ', '+')

        # Базовые параметры URL DubiCars
        params = [f"k={query_encoded}", "c=new-and-used"]
        if min_year:
            params.append(f"yf={min_year}")
        if max_year:
            params.append(f"yt={max_year}")

        base_search_params = "&".join(params)

        for page_num in range(1, max_pages + 1):
            if page_num == 1:
                url = f"{self.base_url}/search?{base_search_params}"
            else:
                url = f"{self.base_url}/search?{base_search_params}&page={page_num}"

            logger.info(f"Парсинг страницы {page_num}/{max_pages}: {url}")

            page_results = await self.parse_listing_page(url)

            if not page_results:
                logger.info(f"Страница {page_num} пуста — завершаем поиск.")
                break

            all_results.extend(page_results)
            logger.info(f"Страница {page_num}: найдено {len(page_results)} объявлений (всего: {len(all_results)})")

            delay = self.get_random_delay()
            logger.debug(f"Пауза {delay:.1f} сек перед следующей страницей...")
            await asyncio.sleep(delay)

        logger.info(f"Поиск '{query}' завершён. Всего найдено: {len(all_results)} объявлений.")
        return all_results

    async def parse_listing_page(self, url: str) -> List[VehicleListing]:
        """Парсинг страницы результатов поиска."""
        results = []
        try:
            success = await self.browser.goto_safe(url)
            if not success:
                return results

            await self.browser.wait(3000)

            content = await self.browser.get_content()
            soup = BeautifulSoup(content, 'html.parser')

            # Точные селекторы DubiCars на основе анализа страницы
            cards = (
                soup.select('li.serp-list-item') or
                soup.select('li[data-item-id]') or
                soup.select('[data-listing-id]') or
                soup.select('.car-card, article.serp-item')
            )

            if not cards:
                logger.warning(f"Не найдено карточек объявлений на странице {url}")
                return results

            for card in cards:
                try:
                    listing = self._parse_card(card)
                    if listing and listing.title:
                        results.append(listing)
                except Exception as e:
                    logger.error(f"Ошибка при парсинге карточки: {e}")
                    continue

        except Exception as e:
            logger.error(f"Ошибка при загрузке страницы {url}: {e}")

        return results

    def _parse_card(self, card) -> Optional[VehicleListing]:
        """Парсинг карточки объявления (с поддержкой извлечения из JSON-атрибутов data-ga4-detail / data-clevertap-detail)."""
        listing_id = card.get('data-item-id') or card.get('data-listing-id', '')
        title = card.get('data-item-title', '')
        mileage_str = card.get('data-item-kilometers', '')

        # Инициализация переменных
        make = ""
        model = ""
        price = None
        year = None
        mileage_km = self._parse_mileage(mileage_str)
        fuel_type = ""
        transmission = ""
        body_type = ""
        color = ""
        location = ""
        seller_type = ""
        image_url = ""
        href = ""

        # 1. Попытка парсинга из встроенного JSON-атрибута data-ga4-detail или data-clevertap-detail
        ga4_raw = card.get('data-ga4-detail') or card.get('data-clevertap-detail') or card.get('data-mixpanel-detail')
        if ga4_raw:
            try:
                ga4_data = json.loads(ga4_raw)
                listing_id = str(ga4_data.get('item_id') or listing_id)
                make = ga4_data.get('car_make') or ga4_data.get('make') or ga4_data.get('item_make') or ""
                model = ga4_data.get('car_model') or ga4_data.get('model') or ga4_data.get('item_model') or ""
                price = float(ga4_data.get('price') or ga4_data.get('price_local') or 0) or None
                year = ga4_data.get('car_year') or ga4_data.get('year') or ga4_data.get('item_year')
                if year:
                    year = int(year)
                if not mileage_km and 'mileage' in ga4_data:
                    mileage_km = int(ga4_data['mileage'])
                fuel_type = ga4_data.get('fuel_type') or ga4_data.get('item_fuel_type') or ""
                transmission = ga4_data.get('transmission') or ga4_data.get('transmission_type') or ga4_data.get('item_gearbox') or ""
                body_type = ga4_data.get('body_type') or ga4_data.get('item_body_type') or ""
                color = ga4_data.get('exterior_color') or ga4_data.get('color_exterior') or ""
                location = ga4_data.get('city') or ga4_data.get('location') or ga4_data.get('item_location') or ""
                seller_type = ga4_data.get('seller_type') or ""
                image_url = ga4_data.get('image_url') or ""
            except Exception as e:
                logger.debug(f"Не удалось распарсить JSON атрибут карточки: {e}")

        # 2. Фолбэк на HTML-разметку, если поля не заполнены из JSON
        if not title:
            title_el = card.select_one('.title, h2, h3, a[title]')
            title = title_el.get_text(strip=True) if title_el else ""

        if not make or not model:
            parts = title.split(' ', 1) if title else []
            if not make and len(parts) > 0:
                make = parts[0]
            if not model and len(parts) > 1:
                model = parts[1]

        if not price:
            price_el = card.select_one('.price strong, .price, [class*="price"]')
            if price_el:
                price = self._parse_price(price_el.get_text(strip=True))

        # Ссылка на объявление
        link_el = card.select_one('a[href*=".html"], a[href]')
        if link_el:
            href = link_el.get('href', '')
            if href and not href.startswith('http'):
                href = self.base_url + href

        if not image_url:
            img_el = card.select_one('img')
            if img_el:
                image_url = img_el.get('src') or img_el.get('data-src') or ""
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url

        # Вспомогательный парсинг текста из блоков specs, если год/пробег еще не найдены
        if not year or not mileage_km or not location:
            specs = card.select('.specs span, .specs div')
            for spec in specs:
                txt = spec.get_text(strip=True)
                if not location and ('Dubai' in txt or 'Abu Dhabi' in txt or 'Sharjah' in txt or 'Ajman' in txt):
                    location = txt
                elif not year and re.match(r'^\d{4}$', txt):
                    year = int(txt)
                elif not mileage_km and ('Km' in txt or 'km' in txt):
                    mileage_km = self._parse_mileage(txt)

        return VehicleListing(
            source=self.source_name,
            listing_id=str(listing_id),
            url=href,
            title=title,
            make=make,
            model=model,
            year=year,
            price=price,
            currency='AED',
            mileage_km=mileage_km,
            fuel_type=fuel_type,
            transmission=transmission,
            body_type=body_type,
            color=color,
            location=location,
            seller_type=seller_type,
            image_url=image_url,
            parsed_at=datetime.now(),
        )

    async def parse_detail_page(self, url: str) -> Optional[VehicleListing]:
        """Парсинг детальной страницы конкретного автомобиля."""
        try:
            logger.info(f"Парсинг детальной страницы: {url}")
            success = await self.browser.goto_safe(url)
            if not success:
                return None

            await self.browser.wait(3000)
            content = await self.browser.get_content()
            soup = BeautifulSoup(content, 'html.parser')

            title_el = soup.select_one('h1.title, h1')
            title = title_el.get_text(strip=True) if title_el else ""
            parts = title.split(' ', 1) if title else []
            make = parts[0] if len(parts) > 0 else ""
            model = parts[1] if len(parts) > 1 else ""

            price_el = soup.select_one('.price strong, [class*="price"]')
            price = self._parse_price(price_el.get_text(strip=True)) if price_el else None

            img_el = soup.select_one('.gallery img, .thumbnail-div img, [class*="slider"] img')
            image_url = (img_el.get('src') or img_el.get('data-src') or "") if img_el else ""
            if image_url.startswith('//'):
                image_url = 'https:' + image_url

            year = None
            mileage_km = None
            fuel_type = ""
            transmission = ""
            body_type = ""
            color = ""
            location = ""

            rows = soup.select('table tr, dl div, [class*="spec"] li, [class*="detail"] div')
            for row in rows:
                text = row.get_text(strip=True).lower()
                if 'year' in text:
                    match = re.search(r'(\d{4})', text)
                    if match:
                        year = int(match.group(1))
                elif 'mileage' in text or 'kilometer' in text:
                    mileage_km = self._parse_mileage(text)
                elif 'fuel' in text:
                    val_el = row.select_one('td:last-child, dd, span:last-child')
                    fuel_type = val_el.get_text(strip=True) if val_el else ""
                elif 'transmission' in text or 'gearbox' in text:
                    val_el = row.select_one('td:last-child, dd, span:last-child')
                    transmission = val_el.get_text(strip=True) if val_el else ""

            return VehicleListing(
                source=self.source_name,
                listing_id=url.split('/')[-1],
                url=url,
                title=title,
                make=make,
                model=model,
                year=year,
                price=price,
                currency='AED',
                mileage_km=mileage_km,
                fuel_type=fuel_type,
                transmission=transmission,
                body_type=body_type,
                color=color,
                location=location,
                image_url=image_url,
                parsed_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Ошибка при парсинге детальной страницы {url}: {e}")
            return None
