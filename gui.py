"""
Графическое приложение AutoParser для DubiCars (ОАЭ).
Без внешних СУБД: само скачивает объявления и выводит их в интерактивную таблицу.
"""

import asyncio
import logging
import os
import sys
import threading
import webbrowser
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.browser import BrowserManager
from core.export import export_to_csv, export_to_json, export_to_excel
from parsers.dubicars import DubiCarsParser
from utils.logger import setup_logger

# Настройка стиля CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class TextHandler(logging.Handler):
    """Кастомный handler для вывода логов в консольный виджет приложения."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state="normal")
            self.text_widget.insert("end", msg + "\n")
            self.text_widget.see("end")
            self.text_widget.configure(state="disabled")
        self.text_widget.after(0, append)


class AutoParserGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AutoParser — DubiCars (ОАЭ)")
        self.geometry("1100 x 750")
        self.minsize(950, 650)

        self.is_running = False
        self.parsed_listings = []

        self._create_ui()
        self._setup_logger()

    def _create_ui(self):
        """Создание элементов пользовательского интерфейса."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # === 1. ЗАГОЛОВОК ===
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="ew")

        title_label = ctk.CTkLabel(
            header_frame,
            text="🇦🇪 DubiCars AutoParser",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(side="left")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Автономное приложение для поиска автомобилей на dubicars.com",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        subtitle_label.pack(side="left", padx=15, pady=(6, 0))

        # === 2. ПАНЕЛЬ НАСТРОЕК (ПОИСК И ФИЛЬТРЫ) ===
        form_frame = ctk.CTkFrame(self)
        form_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        form_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Поисковый запрос
        ctk.CTkLabel(form_frame, text="Марка / Модель:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=15, pady=(12, 2), sticky="w")
        self.entry_query = ctk.CTkEntry(form_frame, placeholder_text="например: Mitsubishi Outlander")
        self.entry_query.insert(0, "Mitsubishi Outlander")
        self.entry_query.grid(row=1, column=0, columnspan=2, padx=15, pady=(0, 10), sticky="ew")

        # Год от
        ctk.CTkLabel(form_frame, text="Год от:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=15, pady=(12, 2), sticky="w")
        self.entry_min_year = ctk.CTkEntry(form_frame, placeholder_text="2022")
        self.entry_min_year.insert(0, "2022")
        self.entry_min_year.grid(row=1, column=2, padx=15, pady=(0, 10), sticky="ew")

        # Год до
        ctk.CTkLabel(form_frame, text="Год до:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, padx=15, pady=(12, 2), sticky="w")
        self.entry_max_year = ctk.CTkEntry(form_frame, placeholder_text="2026")
        self.entry_max_year.insert(0, "2026")
        self.entry_max_year.grid(row=1, column=3, padx=15, pady=(0, 10), sticky="ew")

        # Количество страниц
        ctk.CTkLabel(form_frame, text="Страниц (макс.):", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, padx=15, pady=(5, 2), sticky="w")
        self.entry_pages = ctk.CTkEntry(form_frame)
        self.entry_pages.insert(0, "3")
        self.entry_pages.grid(row=3, column=0, padx=15, pady=(0, 12), sticky="ew")

        # Формат автоматического экспорта
        ctk.CTkLabel(form_frame, text="Формат сохранения:", font=ctk.CTkFont(weight="bold")).grid(row=2, column=1, padx=15, pady=(5, 2), sticky="w")
        self.combo_format = ctk.CTkOptionMenu(form_frame, values=["Excel", "CSV", "JSON"])
        self.combo_format.set("Excel")
        self.combo_format.grid(row=3, column=1, padx=15, pady=(0, 12), sticky="ew")

        # Переключатель Headless
        self.switch_headless = ctk.CTkSwitch(form_frame, text="Фоновый режим браузера (без окна)")
        self.switch_headless.select()
        self.switch_headless.grid(row=3, column=2, columnspan=2, padx=15, pady=(0, 12), sticky="w")

        # === 3. КНОПКИ ДЕЙСТВИЙ И СТАТУС ===
        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.btn_start = ctk.CTkButton(
            controls_frame,
            text="🚀 Начать поиск",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=42,
            fg_color="#2FA572",
            hover_color="#1E7A52",
            command=self.start_parsing
        )
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_open_link = ctk.CTkButton(
            controls_frame,
            text="🔗 Открыть выбранное объявление",
            font=ctk.CTkFont(size=13),
            height=42,
            fg_color="#3B8ED0",
            hover_color="#1F6AA5",
            command=self.open_selected_link
        )
        self.btn_open_link.pack(side="left", padx=5)

        self.btn_open_folder = ctk.CTkButton(
            controls_frame,
            text="📁 Папка с файлами",
            font=ctk.CTkFont(size=13),
            height=42,
            fg_color="#5A6268",
            hover_color="#43494E",
            command=self.open_results_folder
        )
        self.btn_open_folder.pack(side="left", padx=5)

        self.lbl_status = ctk.CTkLabel(
            controls_frame,
            text="Готов к работе",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#2FA572"
        )
        self.lbl_status.pack(side="right", padx=10)

        # === 4. ВКЛАДКИ (ТАБЛИЦА РЕЗУЛЬТАТОВ / ЛОГ ВЫПОЛНЕНИЯ) ===
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=3, column=0, padx=20, pady=(5, 15), sticky="nsew")

        self.tab_results = self.tabview.add("📊 Результаты поиска (0)")
        self.tab_log = self.tabview.add("📋 Журнал событий")

        # --- ВКЛАДКА 1: ТАБЛИЦА РЕЗУЛЬТАТОВ ---
        self.tab_results.grid_columnconfigure(0, weight=1)
        self.tab_results.grid_rowconfigure(0, weight=1)

        # Таблица Treeview в тёмном стиле
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background="#2A2D2E",
                        foreground="white",
                        rowheight=28,
                        fieldbackground="#2A2D2E",
                        font=('Arial', 11))
        style.configure("Treeview.Heading",
                        background="#1F2122",
                        foreground="white",
                        font=('Arial', 11, 'bold'))
        style.map("Treeview", background=[('selected', '#1F6AA5')])

        columns = ("make", "model", "year", "price", "mileage", "fuel", "transmission", "location", "title")
        self.tree = ttk.Treeview(self.tab_results, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("make", text="Марка")
        self.tree.heading("model", text="Модель")
        self.tree.heading("year", text="Год")
        self.tree.heading("price", text="Цена (AED)")
        self.tree.heading("mileage", text="Пробег (км)")
        self.tree.heading("fuel", text="Топливо")
        self.tree.heading("transmission", text="КПП")
        self.tree.heading("location", text="Город")
        self.tree.heading("title", text="Полный заголовок")

        self.tree.column("make", width=90, anchor="center")
        self.tree.column("model", width=110, anchor="center")
        self.tree.column("year", width=65, anchor="center")
        self.tree.column("price", width=100, anchor="e")
        self.tree.column("mileage", width=95, anchor="e")
        self.tree.column("fuel", width=90, anchor="center")
        self.tree.column("transmission", width=90, anchor="center")
        self.tree.column("location", width=90, anchor="center")
        self.tree.column("title", width=300, anchor="w")

        scrollbar = ttk.Scrollbar(self.tab_results, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Двойной клик открывает ссылку в браузере
        self.tree.bind("<Double-1>", lambda e: self.open_selected_link())

        # --- ВКЛАДКА 2: ЛОГИ ---
        self.tab_log.grid_columnconfigure(0, weight=1)
        self.tab_log.grid_rowconfigure(0, weight=1)

        self.log_textbox = ctk.CTkTextbox(
            self.tab_log,
            font=ctk.CTkFont(family="Courier", size=12),
            wrap="word",
            state="disabled"
        )
        self.log_textbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    def _setup_logger(self):
        """Настройка логгера для вывода сообщений во вкладку логов."""
        self.logger = setup_logger("gui_logger")
        text_handler = TextHandler(self.log_textbox)
        text_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        self.logger.addHandler(text_handler)

        dubi_logger = logging.getLogger("parsers.dubicars")
        dubi_logger.addHandler(text_handler)

    def start_parsing(self):
        """Запуск парсинга в фоновом потоке."""
        if self.is_running:
            return

        query = self.entry_query.get().strip()
        if not query:
            self.logger.warning("Введите марку или модель для поиска!")
            return

        try:
            pages = int(self.entry_pages.get().strip())
        except ValueError:
            self.logger.warning("Укажите корректное число страниц!")
            return

        min_year = None
        if self.entry_min_year.get().strip():
            try:
                min_year = int(self.entry_min_year.get().strip())
            except ValueError:
                pass

        max_year = None
        if self.entry_max_year.get().strip():
            try:
                max_year = int(self.entry_max_year.get().strip())
            except ValueError:
                pass

        output_format = self.combo_format.get().lower()
        headless = bool(self.switch_headless.get())

        self.is_running = True
        self.btn_start.configure(state="disabled", text="⏳ Парсинг...")
        self.lbl_status.configure(text="Выполняется скачивание...", text_color="#E5A93C")

        # Очищаем таблицу перед новым запуском
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.parsed_listings.clear()

        # Запуск в фоновом потоке (чтобы интерфейс не замерзал)
        threading.Thread(
            target=self._run_async_parsing,
            args=(query, pages, min_year, max_year, output_format, headless),
            daemon=True
        ).start()

    def _run_async_parsing(self, query, pages, min_year, max_year, output_format, headless):
        """Фоновый поток с asyncio событиями."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(
                self._async_parse_task(query, pages, min_year, max_year, output_format, headless)
            )
        except Exception as e:
            self.logger.error(f"Ошибка парсинга: {e}")
        finally:
            self.is_running = False
            self.after(0, self._on_parsing_finished)

    async def _async_parse_task(self, query, pages, min_year, max_year, output_format, headless):
        """Асинхронная задача скачивания объявлений."""
        self.logger.info("=" * 50)
        self.logger.info(f"Старт DubiCars | Поиск: '{query}' | Года: {min_year or 'все'}-{max_year or 'все'} | Страниц: {pages}")
        self.logger.info("=" * 50)

        async with BrowserManager(headless=headless) as browser:
            parser = DubiCarsParser(browser)
            results = await parser.search(
                query=query,
                max_pages=pages,
                min_year=min_year,
                max_year=max_year
            )
            self.parsed_listings = results

        base_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(base_dir, 'results')
        os.makedirs(results_dir, exist_ok=True)

        if results:
            timestamp = int(datetime.now().timestamp())
            if output_format == 'excel':
                filepath = os.path.join(results_dir, f'dubicars_{timestamp}.xlsx')
                export_to_excel(results, filepath)
            elif output_format == 'csv':
                filepath = os.path.join(results_dir, f'dubicars_{timestamp}.csv')
                export_to_csv(results, filepath)
            else:
                filepath = os.path.join(results_dir, f'dubicars_{timestamp}.json')
                export_to_json(results, filepath)

            self.logger.info(f"🎉 Скачано {len(results)} объявлений! Файл сохранён: {filepath}")
        else:
            self.logger.warning("Объявлений по заданным критериям не найдено.")

    def _on_parsing_finished(self):
        """Заполнение интерактивной таблицы результатами и обновление UI."""
        self.btn_start.configure(state="normal", text="🚀 Начать поиск")

        # Наполняем таблицу данными
        for idx, item in enumerate(self.parsed_listings):
            price_str = f"{item.price:,.0f}" if item.price else "-"
            mileage_str = f"{item.mileage_km:,}" if item.mileage_km is not None else "-"

            self.tree.insert("", "end", iid=str(idx), values=(
                item.make or "-",
                item.model or "-",
                item.year or "-",
                price_str,
                mileage_str,
                item.fuel_type or "-",
                item.transmission or "-",
                item.location or "-",
                item.title or "-"
            ))

        count = len(self.parsed_listings)
        self.tabview._segmented_button._buttons_dict["📊 Результаты поиска (0)"].configure(
            text=f"📊 Результаты поиска ({count})"
        )

        if count > 0:
            self.lbl_status.configure(text=f"Найдено {count} авто ✅", text_color="#2FA572")
            # Переключаем вкладку на результаты
            self.tabview.set("📊 Результаты поиска (0)")
        else:
            self.lbl_status.configure(text="Автомобили не найдены ❌", text_color="#E74C3C")

    def open_selected_link(self):
        """Открытие ссылки выбранного автомобиля в браузере."""
        selected = self.tree.selection()
        if not selected:
            self.logger.warning("Выберите строку в таблице для открытия ссылки!")
            return

        idx = int(selected[0])
        if 0 <= idx < len(self.parsed_listings):
            url = self.parsed_listings[idx].url
            if url:
                self.logger.info(f"Открытие ссылки: {url}")
                webbrowser.open(url)
            else:
                self.logger.warning("У выбранного автомобиля нет ссылки.")

    def open_results_folder(self):
        """Открытие папки results в Finder."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(base_dir, 'results')
        os.makedirs(results_dir, exist_ok=True)

        if sys.platform == 'darwin':
            subprocess.run(['open', results_dir])
        elif sys.platform == 'win32':
            os.startfile(results_dir)
        else:
            subprocess.run(['xdg-open', results_dir])


if __name__ == "__main__":
    app = AutoParserGUI()
    app.mainloop()
