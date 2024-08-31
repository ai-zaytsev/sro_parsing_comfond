import aiohttp
import asyncio
import os
from sys import argv
import ssl
import certifi

async def fetch(session, url, json_data=None):
    async with session.post(url, json=json_data) as response:
        return await response.json()

async def get_compfund_see_odo_sum_from_page(session, url, page_num):
    json_data = {"filters": {"member_status": 1}, "page": page_num, "pageCount": "100", "sortBy": {}}
    data_dict = await fetch(session, url, json_data)
    data = data_dict['data']['data']
    compensation_fund_fee_odo_per_page = sum(float(i.get('compensation_fund_fee_odo', 0)) for i in data)
    return compensation_fund_fee_odo_per_page

async def get_number_of_pages(session, url):
    json_data = {"filters": {"member_status": 1}, "page": 1, "pageCount": "100", "sortBy": {}}
    data_dict = await fetch(session, url, json_data)
    number_of_pages = int(data_dict['data']['countPages'])
    return number_of_pages

async def get_compfund_see_odo_sum_per_sro(session, url):
    comfund_odo_total = 0
    number_of_pages = await get_number_of_pages(session, url)
    tasks = [get_compfund_see_odo_sum_from_page(session, url, page) for page in range(1, number_of_pages + 1)]
    results = await asyncio.gather(*tasks)
    comfund_odo_total = sum(results)
    return comfund_odo_total

def write_to_file(filename, data):
    with open(filename, "a") as file:
        file.write(data)

async def get_nostroy_dict_items(session):
    nostroy_sro_dict = {}
    for i in range(1, 600):
        sro_url = f"https://reestr.nostroy.ru/api/sro/{i}"
        data_dict = await fetch(session, sro_url)
        print(data_dict)
        try:
            data_dict = await fetch(session, sro_url)
            short_description = data_dict['data']['short_description']
            registration_number = data_dict['data']['registration_number']
            dict_key = f"{registration_number} {short_description}"
            nostroy_sro_dict[dict_key] = i
            print(f"Added {short_description} with ID {i}")
        except:
            print(f"{i} not found")
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
            print(f"Added {short_description} with ID {i}")
        except:
            print(f"{i} not found")
    return nopriz_sro_dict.items()

async def main():
    script, sro = argv

    home_dir = os.path.expanduser("~")
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        if sro == 'nostroy':
            filename = os.path.join(home_dir, "nostroy.txt")
            nostroy_dict_items = await get_nostroy_dict_items(session)
            print("Dict full")
            tasks = []
            for key, value in nostroy_dict_items:
                url = f"https://api-open-nostroy.anonamis.ru/api/sro/{value}/member/list"
                task = asyncio.create_task(get_compfund_see_odo_sum_per_sro(session, url))
                tasks.append((key, task))

            for key, task in tasks:
                data = f"{key} : {await task}\n"
                print("Starting writing to file")
                write_to_file(filename, data)
                print("Info added to file")
            print("Script completed with status: Done")

        elif sro == 'nopriz':
            filename = os.path.join(home_dir, "nopriz.txt")
            nopriz_dict_items = await get_nopriz_dict_items(session)
            print("Dict full")
            tasks = []
            for key, value in nopriz_dict_items:
                url = f"https://reestr.nopriz.ru/api/sro/{value}/member/list"
                task = asyncio.create_task(get_compfund_see_odo_sum_per_sro(session, url))
                tasks.append((key, task))

            for key, task in tasks:
                data = f"{key} : {await task}\n"
                print("Starting writing to file")
                write_to_file(filename, data)
                print("Info added to file")
            print("Script completed with status: Done")

        else:
            print(f'Unknown argument: {sro}. Please type "nopriz" or "nostroy"')

if __name__ == '__main__':
    asyncio.run(main())
