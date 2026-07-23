import logging
from typing import Optional, Dict

class ProxyManager:
    """Менеджер для ротации прокси-серверов"""

    def __init__(self):
        self.proxies = []
        self.failed_proxies = []
        self.current_index = 0

    def load_from_file(self, filepath: str):
        """Загрузка прокси из текстового файла"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        parsed = self._parse_proxy(line)
                        if parsed:
                            self.proxies.append(parsed)
            logging.info(f"Загружено {len(self.proxies)} прокси из {filepath}")
        except Exception as e:
            logging.error(f"Ошибка загрузки прокси из {filepath}: {e}")

    def _parse_proxy(self, proxy_str: str) -> Optional[Dict]:
        """Парсинг строки прокси в формат Playwright"""
        try:
            # Формат: protocol://user:pass@ip:port или protocol://ip:port
            if '@' in proxy_str:
                auth_part, server_part = proxy_str.split('@')
                protocol, auth = auth_part.split('://')
                user, password = auth.split(':')
                server = f"{protocol}://{server_part}"
                return {'server': server, 'username': user, 'password': password}
            else:
                return {'server': proxy_str}
        except Exception as e:
            logging.warning(f"Неверный формат прокси {proxy_str}: {e}")
            return None

    def get_next(self) -> Optional[Dict]:
        """Получить следующий прокси в очереди"""
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy

    def mark_failed(self, proxy: Dict):
        """Отметить прокси как неработающий и переместить в конец или удалить"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            self.failed_proxies.append(proxy)
            # При необходимости можно возвращать в конец self.proxies, но сейчас просто переносим в failed

    def get_stats(self) -> Dict:
        """Получить статистику по прокси"""
        return {
            'total': len(self.proxies) + len(self.failed_proxies),
            'working': len(self.proxies),
            'failed': len(self.failed_proxies)
        }
