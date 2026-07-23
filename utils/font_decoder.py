import io
import urllib.request
from typing import Dict

from fontTools.ttLib import TTFont

from utils.logger import setup_logger

logger = setup_logger(__name__)

class FontDecoder:
    """
    Декодер веб-шрифтов для китайских автомобильных сайтов (например, che168, autohome).
    Решает проблему обфускации, при которой цифры заменяются на символы 
    из области пользовательского использования (Private Use Area - PUA).
    """

    def __init__(self, font_data: bytes):
        """
        Инициализирует декодер сырыми байтами файла шрифта (.woff или .ttf).
        """
        try:
            # Загружаем шрифт в fontTools из бинарных данных
            self.font = TTFont(io.BytesIO(font_data))
            # Строим словарь маппинга
            self.mapping = self._build_mapping()
            logger.info(f"Успешно инициализирован FontDecoder, найдено {len(self.mapping)} символов.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке и парсинге шрифта: {e}")
            self.mapping = {}

    def _build_mapping(self) -> dict[str, str]:
        """
        Строит маппинг из PUA Unicode символов в реальные цифры (0-9).
        
        Ключевая логика: китайские сайты используют кастомные шрифты, 
        где символы PUA (например, &#xea90;) соответствуют визуальным цифрам 0-9.
        Обычно порядок глифов или анализ их контуров позволяет сопоставить их с цифрами.
        """
        mapping = {}
        try:
            # Получаем лучшую таблицу cmap (соответствие Unicode кодов именам глифов)
            cmap = self.font['cmap'].getBestCmap()
            
            # Получаем порядок глифов. В некоторых обфускациях цифры идут
            # последовательно после определенных стандартных глифов.
            glyph_order = self.font.getGlyphOrder()
            
            for codepoint, glyph_name in cmap.items():
                # Конвертируем кодпоинт в реальный символ
                char = chr(codepoint)
                
                # Здесь реализована базовая эвристика.
                # В реальных сценариях (che168/autohome) может потребоваться
                # сравнение координат контуров (outlines из таблицы 'glyf') 
                # с эталонными цифрами.
                try:
                    index = glyph_order.index(glyph_name)
                    # Простая заглушка: используем индекс глифа для определения цифры.
                    # Требует точной подстройки под конкретный алгоритм генерации шрифта сайтом.
                    real_digit = str((max(0, index - 1)) % 10)
                    mapping[char] = real_digit
                except ValueError:
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка при построении словаря маппинга шрифта: {e}")
            
        return mapping

    def decode(self, encoded_text: str) -> str:
        """
        Принимает текст с обфусцированными PUA символами и возвращает 
        строку, где они заменены на реальные цифры.
        """
        if not self.mapping:
            logger.warning("Словарь маппинга пуст, возвращаем исходный текст.")
            return encoded_text

        decoded_text = encoded_text
        for pua_char, real_digit in self.mapping.items():
            # Заменяем каждый найденный спецсимвол на соответствующую цифру
            decoded_text = decoded_text.replace(pua_char, real_digit)
            
        return decoded_text

    @staticmethod
    def download_font(url: str) -> bytes:
        """
        Скачивает файл шрифта (WOFF/TTF) по указанному URL.
        """
        try:
            logger.info(f"Загрузка файла шрифта по URL: {url}")
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req) as response:
                font_data = response.read()
            logger.info("Файл шрифта успешно загружен.")
            return font_data
        except Exception as e:
            logger.error(f"Не удалось загрузить шрифт с {url}: {e}")
            return b""
