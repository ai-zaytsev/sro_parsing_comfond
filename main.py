import aiohttp
import asyncio
import os
import ssl
import certifi
import csv
from sys import argv

# ========== Настройки ==========
PAGE_SIZE = 100
PAGE_CONCURRENCY = 100    # макс. одновременных запросов страниц
MEMBER_CONCURRENCY = 50   # макс. одновременных задач по SRO

# семафор для ограничения параллельных fetch по страницам
page_sem = asyncio.Semaphore(PAGE_CONCURRENCY)

async def fetch(session, url, json_data):
    """POST-запрос с проверкой статуса."""
    async with session.post(url, json=json_data) as resp:
        resp.raise_for_status()
        return await resp.json()

async def get_nopriz_sro_items(session):
    """Список действующих и ожидающих СРО из NOPRIZ."""
    url = "https://reestr.nopriz.ru/api/sro/list"
    payload = {
        "filters": {"state": ["enabled", "wait"]},
        "pageCount": str(PAGE_SIZE),
        "searchString": None,
        "sortBy": {
            "registry_registration_date": "DESC",
            "suspension_date": "DESC"
        }
    }
    first = await fetch(session, url, {**payload, "page": 1})
    pages = int(first['data']['countPages'])
    items = []
    for page in range(1, pages + 1):
        resp = await fetch(session, url, {**payload, "page": page})
        for s in resp['data']['data']:
            items.append((s['registration_number'], s['short_description'], s['id'], "nopriz"))
    return items

async def get_nostroy_sro_items(session):
    """Список действующих СРО из NOSTROY."""
    url = "https://reestr.nostroy.ru/api/sro/list"
    payload = {
        "filters": {"state": "enabled"},
        "pageCount": str(PAGE_SIZE),
        "sortBy": {}
    }
    first = await fetch(session, url, {**payload, "page": 1})
    pages = int(first['data']['countPages'])
    items = []
    for page in range(1, pages + 1):
        resp = await fetch(session, url, {**payload, "page": page})
        for s in resp['data']['data']:
            items.append((s['registration_number'], s['short_description'], s['id'], "nostroy"))
    return items

async def sum_for_one_page(session, list_url, page_num):
    """Суммируем по одной странице members/list."""
    async with page_sem:
        payload = {
            "filters": {"member_status": 1},
            "page": page_num,
            "pageCount": str(PAGE_SIZE),
            "searchString": "",
            "sortBy": {}
        }
        resp = await fetch(session, list_url, payload)
        total = 0.0
        for m in resp['data']['data']:
            odo = (m.get('member_right_odo') or {}).get('compensation_fund')
            if odo is None:
                odo = m.get('compensation_fund_fee_odo', 0)
            try:
                total += float(odo)
            except (TypeError, ValueError):
                pass
        return total

async def compute_sro(session, api_base, reg_no, short_desc, sid, sem):
    """Задача: суммирует фонд по SRO и возвращает данные для CSV."""
    async with sem:
        list_url = f"{api_base}/{sid}/member/list"
        first = await fetch(session, list_url, {
            "filters": {"member_status": 1},
            "page": 1,
            "pageCount": str(PAGE_SIZE),
            "searchString": "",
            "sortBy": {}
        })
        pages = int(first['data']['countPages'])
        tasks = [asyncio.create_task(sum_for_one_page(session, list_url, p))
                 for p in range(1, pages + 1)]
        results = await asyncio.gather(*tasks)
        total_int = int(round(sum(results)))
        return reg_no, short_desc, total_int

async def main():
    mode = argv[1] if len(argv) > 1 and argv[1] in ("nopriz", "nostroy", "both") else "both"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(script_dir, "result.csv")

    # подготовка CSV
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(["registration_number", "short_description", "compfund_fee_odo_sum"])

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_ctx, limit=200)
    sem = asyncio.Semaphore(MEMBER_CONCURRENCY)

    async with aiohttp.ClientSession(connector=connector) as session:
        all_sros = []
        if mode in ("nopriz", "both"):
            all_sros += await get_nopriz_sro_items(session)
        if mode in ("nostroy", "both"):
            all_sros += await get_nostroy_sro_items(session)

        tasks = [asyncio.create_task(
            compute_sro(
                session,
                "https://reestr.nopriz.ru/api/sro" if src == "nopriz" else "https://reestr.nostroy.ru/api/sro",
                reg_no, short_desc, sid, sem
            )
        ) for reg_no, short_desc, sid, src in all_sros]

        # Batch write CSV по мере готовности
        batch = []
        BATCH_SIZE = 50
        with open(out_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for coro in asyncio.as_completed(tasks):
                reg_no, short_desc, total_int = await coro
                batch.append([reg_no, short_desc, total_int])
                if len(batch) >= BATCH_SIZE:
                    writer.writerows(batch)
                    batch.clear()
            if batch:
                writer.writerows(batch)

if __name__ == '__main__':
    asyncio.run(main())
