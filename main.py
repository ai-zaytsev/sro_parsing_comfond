import aiohttp
import asyncio
import os
from sys import argv
import ssl
import certifi
import logging

# Настройка логирования с сохранением в файл
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),  # Логи будут сохраняться в файл "app.log" в корне проекта
        logging.StreamHandler()  # Логи также будут выводиться в консоль
    ]
)
logger = logging.getLogger(__name__)

async def fetch(session, url, json_data=None):
    logger.debug(f"Sending POST request to {url}")
    async with session.post(url, json=json_data) as response:
        if response.status != 200:
            text = await response.text()
            logger.error(f"Failed request to {url}: Status {response.status}. Response: {text}")
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"Unexpected response status: {response.status}",
                headers=response.headers
            )
        response_data = await response.json()
        logger.debug(f"Received response: {response_data}")
        return response_data


async def get_compfund_fee_odo_sum_from_page(session, url, page_num):
    logger.debug(f"Fetching data for page {page_num}")
    json_data = {"filters": {"member_status": 1}, "page": page_num, "pageCount": "100", "sortBy": {}}
    data_dict = await fetch(session, url, json_data)
    data = data_dict['data']['data']
    compensation_fund_fee_odo_per_page = sum(float(i.get('compensation_fund_fee_odo', 0)) for i in data)
    logger.debug(f"Page {page_num} sum: {compensation_fund_fee_odo_per_page}")
    return compensation_fund_fee_odo_per_page


async def get_number_of_pages(session, url):
    logger.debug(f"Fetching number of pages for URL: {url}")
    json_data = {"filters": {"member_status": 1}, "page": 1, "pageCount": "100", "sortBy": {}}
    data_dict = await fetch(session, url, json_data)
    number_of_pages = int(data_dict['data']['countPages'])
    logger.debug(f"Number of pages: {number_of_pages}")
    return number_of_pages


async def get_compfund_fee_odo_sum_per_sro(session, url):
    logger.debug(f"Starting to collect compensation fund fee ODO sum for URL: {url}")
    comfund_odo_total = 0
    number_of_pages = await get_number_of_pages(session, url)
    logger.debug(f"Total pages to process: {number_of_pages}")
    tasks = [get_compfund_fee_odo_sum_from_page(session, url, page) for page in range(1, number_of_pages + 1)]
    results = await asyncio.gather(*tasks)
    comfund_odo_total = sum(results)
    logger.debug(f"Total compensation fund fee ODO sum: {comfund_odo_total}")
    return comfund_odo_total


def write_to_file(filename, data):
    logger.debug(f"Attempting to write data to {filename}")
    try:
        with open(filename, "a") as file:
            file.write(data)
        logger.debug(f"Data successfully written to {filename}")
    except Exception as e:
        logger.error(f"Failed to write data to {filename}: {e}")
        raise

async def get_nostroy_dict_items(session):
    nostroy_sro_dict = {}
    for i in range(1, 600):
        sro_url = f"https://reestr.nostroy.ru/api/sro/{i}"
        try:
            data_dict = await fetch(session, sro_url)
            short_description = data_dict['data']['short_description']
            registration_number = data_dict['data']['registration_number']
            dict_key = f"{registration_number} {short_description}"
            nostroy_sro_dict[dict_key] = i
            logger.debug(f"Добавлено {short_description} с ID {i}")
        except Exception as e:
            logger.warning(f"СРО с ID {i} не найдено.")
    return nostroy_sro_dict.items()

async def get_nopriz_dict_items(session):
    nopriz_sro_dict = {}
    for i in range(1, 600):
        sro_url = f"https://reestr.nopriz.ru/api/sro/{i}"
        try:
            data_dict = await fetch(session, sro_url)
            short_description = data_dict['data']['short_description']
            registration_number = data_dict['data']['registration_number']
            dict_key = f"{registration_number} {short_description}"
            nopriz_sro_dict[dict_key] = i
            logger.debug(f"Добавлено {short_description} с ID {i}")
        except Exception as e:
            logger.warning(f"СРО с ID {i} не найдено.")
    return nopriz_sro_dict.items()

async def main():
    script, sro = argv

    home_dir = os.path.expanduser("~")
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    # Отключение проверки сертификата (для тестирования)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        if sro == 'nostroy':
            logger.debug(f"Processing 'nostroy' SRO")
            filename = os.path.join(home_dir, "nostroy.txt")
            nostroy_dict_items = await get_nostroy_dict_items(session)
            logger.debug("Dictionary full")
            tasks = []
            for key, value in nostroy_dict_items:
                url = f"https://reestr.nopriz.ru/api/sro/{value}/member/list"
                task = asyncio.create_task(get_compfund_fee_odo_sum_per_sro(session, url))
                tasks.append((key, task))

            for key, task in tasks:
                data = f"{key} : {await task}\n"
                logger.debug("Starting writing to file")
                write_to_file(filename, data)
                logger.debug("Info added to file")
            logger.info("Script completed with status: Done")

        elif sro == 'nopriz':
            logger.debug(f"Processing 'nopriz' SRO")
            filename = os.path.join(home_dir, "nopriz.txt")
            nopriz_dict_items = await get_nopriz_dict_items(session)
            logger.debug("Dictionary full")
            tasks = []
            for key, value in nopriz_dict_items:
                url = f"https://reestr.nopriz.ru/api/sro/{value}/member/list"
                task = asyncio.create_task(get_compfund_fee_odo_sum_per_sro(session, url))
                tasks.append((key, task))

            for key, task in tasks:
                data = f"{key} : {await task}\n"
                logger.debug("Starting writing to file")
                write_to_file(filename, data)
                logger.debug("Info added to file")
            logger.info("Script completed with status: Done")

        else:
            print(f'Unknown argument: {sro}. Please type "nopriz" or "nostroy"')

if __name__ == '__main__':
    logger.info("Script started")
    try:
        asyncio.run(main())
        logger.info("Script finished successfully")
    except Exception as e:
        logger.exception("Script terminated with an error")
