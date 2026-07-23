"""
Менеджер браузера Playwright.
Управляет жизненным циклом браузера, поддерживает stealth-режим и прокси.
"""

import random
import logging
from typing import Optional
from playwright.async_api import async_playwright, Playwright, BrowserContext, Browser, Page

import config


class BrowserManager:
    """Менеджер для управления жизненным циклом браузера Playwright"""

    def __init__(self, headless: bool = False, proxy: Optional[dict] = None):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._headless = headless
        self._proxy = proxy

        # Общие разрешения экранов для случайного выбора
        self._viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1440, "height": 900},
            {"width": 1536, "height": 864},
            {"width": 1600, "height": 900},
        ]

    async def __aenter__(self):
        """Поддержка асинхронного контекстного менеджера"""
        await self.launch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие при выходе из контекстного менеджера"""
        await self.close()

    async def launch(self, locale: str = 'en-US'):
        """Запуск браузера со скрытными (stealth) настройками"""
        self._playwright = await async_playwright().start()

        launch_args = {
            'headless': self._headless,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ],
        }

        browser_type = self._playwright.chromium

        # Попытка запустить через установленный Google Chrome
        try:
            launch_args['channel'] = 'chrome'
            self._browser = await browser_type.launch(**launch_args)
            logging.info("Запущен Google Chrome")
        except Exception:
            launch_args.pop('channel', None)
            self._browser = await browser_type.launch(**launch_args)
            logging.info("Запущен Chromium (Chrome не найден)")

        # Настройки контекста
        user_agent = random.choice(config.USER_AGENTS)
        viewport = random.choice(self._viewports)

        context_args = {
            'viewport': viewport,
            'locale': locale,
            'user_agent': user_agent,
        }

        if self._proxy:
            context_args['proxy'] = self._proxy

        self._context = await self._browser.new_context(**context_args)

        # Скрываем маркер автоматизации navigator.webdriver
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Создаём основную рабочую страницу
        self._page = await self._context.new_page()

    async def get_page(self) -> Page:
        """Получить текущую рабочую страницу"""
        if not self._page:
            raise RuntimeError("Браузер не запущен. Сначала вызовите launch().")
        return self._page

    async def new_page(self) -> Page:
        """Создать новую страницу в текущем контексте"""
        if not self._context:
            raise RuntimeError("Контекст браузера не инициализирован.")
        return await self._context.new_page()

    async def goto_safe(self, url: str, wait_until: str = 'domcontentloaded', retries: int = 3) -> bool:
        """Безопасный переход по URL с повторными попытками"""
        page = await self.get_page()
        for attempt in range(retries):
            try:
                await page.goto(url, wait_until=wait_until, timeout=30000)
                return True
            except Exception as e:
                logging.warning(f"Попытка {attempt + 1}/{retries} загрузить {url}: {e}")
                if attempt == retries - 1:
                    logging.error(f"Не удалось загрузить {url} после {retries} попыток.")
                    return False
        return False

    async def get_content(self) -> str:
        """Получить HTML-содержимое текущей страницы"""
        page = await self.get_page()
        return await page.content()

    async def wait(self, timeout: int = 2000):
        """Ожидание загрузки контента (в миллисекундах)"""
        page = await self.get_page()
        await page.wait_for_timeout(timeout)

    async def close(self):
        """Закрытие контекста и браузера"""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
