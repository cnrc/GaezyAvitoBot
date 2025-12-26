import asyncio
import html
import json
import random
import re
import time
from urllib.parse import unquote, urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from curl_cffi import requests
from loguru import logger
from pydantic import ValidationError
from requests.cookies import RequestsCookieJar

from src.common_data import HEADERS
from src.dto import Proxy, AvitoConfig
from src.get_cookies import get_cookies
from src.hide_private_data import log_config
from src.config import get_avito_config
from src.models import ItemsResponse, Item


DEBUG_MODE = False

logger.add("logs/app.log", rotation="5 MB", retention="5 days", level="DEBUG")


class AvitoParse:
    def __init__(
            self,
            config: AvitoConfig,
            stop_event=None
    ):
        self.config = config
        self.proxy_obj = self.get_proxy_obj()
        self.stop_event = stop_event
        self.cookies = None
        self.session = requests.Session()
        self.headers = HEADERS
        self.good_request_count = 0
        self.bad_request_count = 0
        self.current_ip = None  # Текущий IP для проверки
        self.current_url_index = 0  # Индекс текущей ссылки для смены IP

        log_config(config=self.config)

    def get_proxy_obj(self) -> Proxy | None:
        # Определяем какую ссылку использовать для Proxy объекта
        change_ip_link = None
        if self.config.proxy_change_urls:  # Приоритет - первая ссылка из списка
            change_ip_link = self.config.proxy_change_urls[0]
        elif self.config.proxy_change_url:  # Fallback - одна ссылка
            change_ip_link = self.config.proxy_change_url
        
        if self.config.proxy_string and change_ip_link:
            return Proxy(
                proxy_string=self.config.proxy_string,
                change_ip_link=change_ip_link
            )
        logger.info("Работаем без прокси")
        return None

    def get_cookies(self, max_retries: int = 1, delay: float = 2.0) -> dict | None:
        for attempt in range(1, max_retries + 1):
            try:
                # Безопасный вызов асинхронной функции в синхронном контексте
                try:
                    loop = asyncio.get_running_loop()
                    # Если event loop уже запущен, создаем новый поток
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, get_cookies(proxy=self.proxy_obj, headless=True))
                        cookies, user_agent = future.result()
                except RuntimeError:
                    # Если нет запущенного event loop, используем asyncio.run
                    cookies, user_agent = asyncio.run(get_cookies(proxy=self.proxy_obj, headless=True))
                if cookies:
                    logger.info(f"[get_cookies] Успешно получены cookies с попытки {attempt}")

                    self.headers["user-agent"] = user_agent
                    return cookies
                else:
                    raise ValueError("Пустой результат cookies")
            except Exception as e:
                logger.warning(f"[get_cookies] Попытка {attempt} не удалась: {e}")
                if attempt < max_retries:
                    time.sleep(delay * attempt)  # увеличиваем задержку
                else:
                    logger.error(f"[get_cookies] Все {max_retries} попытки не удались")
                    return None

    def save_cookies(self) -> None:
        """Сохраняет cookies из requests.Session в JSON-файл."""
        with open("cookies.json", "w") as f:
            json.dump(self.session.cookies.get_dict(), f)

    def load_cookies(self) -> None:
        """Загружает cookies из JSON-файла в requests.Session."""
        try:
            with open("cookies.json", "r") as f:
                cookies = json.load(f)
                jar = RequestsCookieJar()
                for k, v in cookies.items():
                    jar.set(k, v)
                self.session.cookies.update(jar)
        except FileNotFoundError:
            pass

    def fetch_data(self, url, retries=3, backoff_factor=1):
        proxy_data = None
        use_http3 = True
        timeout = 20  # Таймаут по умолчанию
        if self.proxy_obj:
            proxy_url = f"http://{self.config.proxy_string}"
            proxy_data = {"http": proxy_url, "https": proxy_url}
            use_http3 = True  # Отключаем HTTP/3 при использовании прокси
            timeout = 60  # Увеличиваем таймаут для прокси (парсинг Авито может быть медленным)
            logger.info(f"Используем прокси: {self.config.proxy_string.split('@')[1] if '@' in self.config.proxy_string else 'скрыт'}")

        for attempt in range(1, retries + 1):
            if self.stop_event and self.stop_event.is_set():
                return

            try:
                request_params = {
                    "url": url,
                    "headers": self.headers,
                    "proxies": proxy_data,
                    "cookies": self.cookies,
                    "impersonate": "chrome",
                    "timeout": timeout,
                    "verify": False
                }
                if use_http3:
                    request_params["http_version"] = 3
                
                response = self.session.get(**request_params)
                logger.debug(f"Попытка {attempt}: {response.status_code}")

                if response.status_code >= 500:
                    raise requests.RequestsError(f"Ошибка сервера: {response.status_code}")
                if response.status_code == 429:
                    self.bad_request_count += 1
                    self.session = requests.Session()
                    self.change_ip()
                    if attempt >= 3:
                        self.cookies = self.get_cookies()
                    raise requests.RequestsError(f"Слишком много запросов: {response.status_code}")
                if response.status_code in [403, 302]:
                    self.cookies = self.get_cookies()
                    raise requests.RequestsError(f"Заблокирован: {response.status_code}")

                self.save_cookies()
                self.good_request_count += 1
                return response.text
            except requests.RequestsError as e:
                error_str = str(e)
                logger.debug(f"Попытка {attempt} закончилась неуспешно: {e}")
                
                # Проверяем на ошибку прокси (502, 503, connect failed, timeout, connection timeout)
                if any(err in error_str for err in ["502", "503", "CONNECT tunnel failed", "(56)", "Connection timed out", "(28)", "timed out"]):
                    logger.warning("Ошибка прокси/сети! Пытаемся сменить IP...")
                    if self.proxy_obj:
                        self.change_ip()
                        time.sleep(2)  # Небольшая пауза после смены IP
                
                if attempt < retries:
                    sleep_time = backoff_factor * attempt
                    logger.debug(f"Повтор через {sleep_time} секунд...")
                    time.sleep(sleep_time)
                else:
                    logger.info("Все попытки были неуспешными")
                    return None

    def parse(self):
        self.load_cookies()

        for _index, url in enumerate(self.config.urls):
            for i in range(0, self.config.count):
                if self.stop_event and self.stop_event.is_set():
                    return
                if DEBUG_MODE:
                    html_code = open("response.txt", "r", encoding="utf-8").read()
                else:
                    html_code = self.fetch_data(url=url, retries=self.config.max_count_of_retry)

                if not html_code:
                    return self.parse()

                data_from_page = self.find_json_on_page(html_code=html_code)
                try:
                    ads_models = ItemsResponse(**data_from_page.get("data", {}).get("catalog"))
                except ValidationError as err:
                    logger.error(f"При валидации объявлений произошла ошибка: {err}")
                    continue

                ads = self._clean_null_ads(ads=ads_models.items)

                ads = self._add_seller_to_ads(ads=ads)

                if not ads:
                    logger.info("Объявления закончились, заканчиваю работу с данной ссылкой")
                    break

                filter_ads = self.filter_ads(ads=ads)
                filter_ads = self.parse_views(ads=filter_ads)

                # Сохранение в БД отключено. Ничего не сохраняем.

                url = self.get_next_page_url(url=url)

                logger.info(f"Пауза {self.config.pause_between_links} сек.")
                time.sleep(self.config.pause_between_links)

        logger.info(f"Хорошие запросы: {self.good_request_count}шт, плохие: {self.bad_request_count}шт")

    @staticmethod
    def _clean_null_ads(ads: list[Item]) -> list[Item]:
        return [ad for ad in ads if ad.id]

    @staticmethod
    def find_json_on_page(html_code, data_type: str = "mime") -> dict:
        soup = BeautifulSoup(html_code, "html.parser")
        try:
            for _script in soup.select('script'):
                script_type = _script.get('type')

                if data_type == 'mime' and script_type == 'mime/invalid':
                    script_content = html.unescape(_script.text)
                    parsed_data = json.loads(script_content)

                    if 'state' in parsed_data:
                        return parsed_data['state']

                    elif 'data' in parsed_data:
                        logger.info("data")
                        return parsed_data['data']

                    else:
                        return parsed_data

        except Exception as err:
            logger.error(f"Ошибка при поиске информации на странице: {err}")
        return {}

    def filter_ads(self, ads: list[Item]) -> list[Item]:
        """Сортирует объявления"""
        filters = [
            self._filter_by_price_range,
            self._filter_by_black_keywords,
            self._filter_by_white_keyword,
            self._filter_by_address,
            self._filter_by_seller,
            self._filter_by_recent_time,
            self._filter_by_reserve,
            self._filter_by_promotion,
        ]

        for filter_fn in filters:
            ads = filter_fn(ads)
            logger.info(f"После фильтрации {filter_fn.__name__} осталось {len(ads)}")
            if not len(ads):
                return ads
        return ads

    def _filter_by_price_range(self, ads: list[Item]) -> list[Item]:
        try:
            return [ad for ad in ads if self.config.min_price <= ad.priceDetailed.value <= self.config.max_price]
        except Exception as err:
            logger.debug(f"Ошибка при фильтрации по цене: {err}")
            return ads

    def _filter_by_black_keywords(self, ads: list[Item]) -> list[Item]:
        if not self.config.keys_word_black_list:
            return ads
        try:
            return [ad for ad in ads if not self._is_phrase_in_ads(ad=ad, phrases=self.config.keys_word_black_list)]
        except Exception as err:
            logger.debug(f"Ошибка при проверке объявлений по списку стоп-слов: {err}")
            return ads

    def _filter_by_white_keyword(self, ads: list[Item]) -> list[Item]:
        if not self.config.keys_word_white_list:
            return ads
        try:
            return [ad for ad in ads if self._is_phrase_in_ads(ad=ad, phrases=self.config.keys_word_white_list)]
        except Exception as err:
            logger.debug(f"Ошибка при проверке объявлений по списку обязательных слов: {err}")
            return ads

    def _filter_by_address(self, ads: list[Item]) -> list[Item]:
        if not self.config.geo:
            return ads
        try:
            return [ad for ad in ads if self.config.geo in ad.geo.formattedAddress]
        except Exception as err:
            logger.debug(f"Ошибка при проверке объявлений по адресу: {err}")
            return ads


    def _add_seller_to_ads(self, ads: list[Item]) -> list[Item]:
        for ad in ads:
            if seller_id := self._extract_seller_slug(data=ad):
                ad.sellerId = seller_id
        return ads

    @staticmethod
    def _add_promotion_to_ads(ads: list[Item]) -> list[Item]:
        for ad in ads:
            ad.isPromotion = any(
                v.get("title") == "Продвинуто"
                for step in (ad.iva or {}).get("DateInfoStep", [])
                for v in step.payload.get("vas", [])
            )
        return ads

    def _filter_by_seller(self, ads: list[Item]) -> list[Item]:
        if not self.config.seller_black_list:
            return ads
        try:
            return [ad for ad in ads if not ad.sellerId or ad.sellerId not in self.config.seller_black_list]
        except Exception as err:
            logger.debug(f"Ошибка при отсеивании объявления с продавцами из черного списка : {err}")
            return ads

    def _filter_by_recent_time(self, ads: list[Item]) -> list[Item]:
        if not self.config.max_age:
            return ads
        try:
            return [ad for ad in ads if
                    self._is_recent(timestamp_ms=ad.sortTimeStamp, max_age_seconds=self.config.max_age)]
        except Exception as err:
            logger.debug(f"Ошибка при отсеивании слишком старых объявлений: {err}")
            return ads

    def _filter_by_reserve(self, ads: list[Item]) -> list[Item]:
        if not self.config.ignore_reserv:
            return ads
        try:
            return [ad for ad in ads if not ad.isReserved]
        except Exception as err:
            logger.debug(f"Ошибка при отсеивании объявлений в резерве: {err}")
            return ads

    def _filter_by_promotion(self, ads: list[Item]) -> list[Item]:
        ads = self._add_promotion_to_ads(ads=ads)
        if not self.config.ignore_promotion:
            return ads
        try:
            return [ad for ad in ads if not ad.isPromotion]
        except Exception as err:
            logger.debug(f"Ошибка при отсеивании продвинутых объявлений: {err}")
            return ads

    def parse_views(self, ads: list[Item]) -> list[Item]:
        if not self.config.parse_views:
            return ads

        logger.info("Начинаю парсинг просмотров")

        for ad in ads:
            try:
                html_code_full_page = self.fetch_data(url=f"https://www.avito.ru{ad.urlPath}")
                ad.total_views, ad.today_views = self._extract_views(html=html_code_full_page)
                delay = random.uniform(0.1, 0.9)
                time.sleep(delay)
            except Exception as err:
                logger.warning(f"Ошибка при парсинге {ad.urlPath}: {err}")
                continue

        return ads

    @staticmethod
    def _extract_views(html: str) -> tuple:
        soup = BeautifulSoup(html, "html.parser")

        def extract_digits(element):
            return int(''.join(filter(str.isdigit, element.get_text()))) if element else None

        total = extract_digits(soup.select_one('[data-marker="item-view/total-views"]'))
        today = extract_digits(soup.select_one('[data-marker="item-view/today-views"]'))

        return total, today

    def get_current_ip(self) -> str | None:
        """Получить текущий IP адрес через прокси"""
        try:
            if self.proxy_obj:
                proxy_url = f"http://{self.config.proxy_string}"
                proxy_data = {"http": proxy_url, "https": proxy_url}
                response = requests.get(
                    "https://api.ipify.org?format=text",
                    proxies=proxy_data,
                    timeout=10,
                    verify=False
                )
                if response.status_code == 200:
                    return response.text.strip()
            else:
                # Без прокси
                response = requests.get(
                    "https://api.ipify.org?format=text",
                    timeout=10,
                    verify=False
                )
                if response.status_code == 200:
                    return response.text.strip()
        except Exception as err:
            logger.warning(f"Не удалось получить текущий IP: {err}")
        return None

    def change_ip(self) -> bool:
        """Смена IP с использованием списка ссылок"""
        # Получаем список ссылок для смены IP
        change_urls = []
        if self.config.proxy_change_urls:  # Приоритет - список ссылок
            change_urls = self.config.proxy_change_urls
        elif self.config.proxy_change_url:  # Fallback - одна ссылка
            change_urls = [self.config.proxy_change_url]
        else:
            logger.info("Сейчас бы была смена ip, но мы без прокси")
            return False
        
        # Получаем текущий IP перед сменой
        old_ip = self.get_current_ip()
        if old_ip:
            logger.info(f"Текущий IP: {old_ip}")
        
        # Пытаемся сменить IP с помощью текущей ссылки
        current_url = change_urls[self.current_url_index % len(change_urls)]
        logger.info(f"Меняю IP используя ссылку {self.current_url_index + 1}/{len(change_urls)}")
        
        try:
            res = requests.get(url=current_url, verify=False, timeout=10)
            if res.status_code == 200:
                # Проверяем, изменился ли IP
                time.sleep(2)  # Небольшая пауза для применения смены IP
                new_ip = self.get_current_ip()
                
                if new_ip and new_ip != old_ip:
                    logger.info(f"IP успешно изменен: {old_ip} -> {new_ip}")
                    self.current_ip = new_ip
                    # Сбрасываем индекс на первую ссылку, так как смена прошла успешно
                    self.current_url_index = 0
                    return True
                elif new_ip == old_ip:
                    logger.warning(f"IP не изменился ({old_ip}), пробую следующую ссылку")
                    # Увеличиваем индекс для использования следующей ссылки
                    self.current_url_index += 1
                    # Если прошли все ссылки, начинаем сначала
                    if self.current_url_index >= len(change_urls):
                        self.current_url_index = 0
                    # Пробуем снова с следующей ссылкой
                    time.sleep(random.randint(2, 5))
                    return self.change_ip()
                else:
                    logger.warning("Не удалось получить новый IP после смены")
                    return False
        except Exception as err:
            logger.warning(f"При смене ip возникла ошибка: {err}")
        
        # Если не удалось, пробуем снова с той же или следующей ссылкой
        logger.info("Не удалось изменить IP, пробую еще раз")
        self.current_url_index = (self.current_url_index + 1) % len(change_urls)
        time.sleep(random.randint(3, 10))
        return self.change_ip()

    @staticmethod
    def _extract_seller_slug(data):
        match = re.search(r"/brands/([^/?#]+)", str(data))
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _is_phrase_in_ads(ad: Item, phrases: list) -> bool:
        full_text_from_ad = (ad.title + ad.description).lower()
        return any(phrase.lower() in full_text_from_ad for phrase in phrases)

    # Удалена логика проверки просмотренных объявлений

    @staticmethod
    def _is_recent(timestamp_ms: int, max_age_seconds: int) -> bool:
        now = datetime.utcnow()
        published_time = datetime.utcfromtimestamp(timestamp_ms / 1000)
        return (now - published_time) <= timedelta(seconds=max_age_seconds)

    # Удалено сохранение данных в БД

    def get_next_page_url(self, url: str):
        """Получает следующую страницу"""
        try:
            url_parts = urlparse(url)
            query_params = parse_qs(url_parts.query)
            current_page = int(query_params.get('p', [1])[0])
            query_params['p'] = current_page + 1
            if self.config.one_time_start:
                logger.debug(f"Страница {current_page}")

            new_query = urlencode(query_params, doseq=True)
            next_url = urlunparse((url_parts.scheme, url_parts.netloc, url_parts.path, url_parts.params, new_query,
                                   url_parts.fragment))
            return next_url
        except Exception as err:
            logger.error(f"Не смог сформировать ссылку на следующую страницу для {url}. Ошибка: {err}")


if __name__ == "__main__":
    try:
        config = get_avito_config()
    except Exception as err:
        logger.error(f"Ошибка загрузки конфига: {err}")
        exit(1)

    while True:
        try:
            parser = AvitoParse(config)
            parser.parse()
            if config.one_time_start:
                logger.info("Парсинг завершен т.к. включён one_time_start в настройках")
                break
            logger.info(f"Парсинг завершен. Пауза {config.pause_general} сек")
            time.sleep(config.pause_general)
        except Exception as err:
            logger.error(f"Произошла ошибка {err}. Будет повторный запуск через 30 сек.")
            time.sleep(30)
