import aiohttp
import asyncio
import csv
import logging
import os
import random
import ssl
from sys import argv

import certifi

# ========== Settings ==========
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "100"))
PAGE_CONCURRENCY = int(os.getenv("PAGE_CONCURRENCY", "8"))
MEMBER_CONCURRENCY = int(os.getenv("MEMBER_CONCURRENCY", "4"))
FETCH_RETRIES = int(os.getenv("FETCH_RETRIES", "5"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "1.5"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Global semaphore that limits the total number of page requests.
page_sem = asyncio.Semaphore(PAGE_CONCURRENCY)


def resolve_output_path(script_dir):
    output_dir = os.getenv("OUTPUT_DIR")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, "result.csv")

    container_data_dir = "/data"
    if os.path.isdir(container_data_dir) and os.access(container_data_dir, os.W_OK):
        return os.path.join(container_data_dir, "result.csv")

    return os.path.join(script_dir, "result.csv")


def build_member_payload(page_num):
    return {
        "filters": {"member_status": 1},
        "page": page_num,
        "pageCount": str(PAGE_SIZE),
        "searchString": "",
        "sortBy": {},
    }


def extract_compfund_sum(resp):
    total = 0.0
    for member in resp["data"]["data"]:
        odo = (member.get("member_right_odo") or {}).get("compensation_fund")
        if odo is None:
            odo = member.get("compensation_fund_fee_odo", 0)
        try:
            total += float(odo)
        except (TypeError, ValueError):
            continue
    return total


async def fetch(session, url, json_data):
    """POST request with retries for transient network failures."""
    last_error = None

    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            async with session.post(url, json=json_data) as resp:
                resp.raise_for_status()
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_error = exc
            if attempt == FETCH_RETRIES:
                break

            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            logger.warning(
                "Request failed (%s/%s) for %s page=%s: %s. Retrying in %.1fs",
                attempt,
                FETCH_RETRIES,
                url,
                json_data.get("page"),
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    raise RuntimeError(
        f"Failed to fetch {url} page={json_data.get('page')} after {FETCH_RETRIES} attempts"
    ) from last_error


async def get_nopriz_sro_items(session):
    """List of active and pending SRO records from NOPRIZ."""
    url = "https://reestr.nopriz.ru/api/sro/list"
    payload = {
        "filters": {"state": ["enabled", "wait"]},
        "pageCount": str(PAGE_SIZE),
        "searchString": None,
        "sortBy": {
            "registry_registration_date": "DESC",
            "suspension_date": "DESC",
        },
    }
    first = await fetch(session, url, {**payload, "page": 1})
    pages = int(first["data"]["countPages"])
    items = []
    for page in range(1, pages + 1):
        resp = await fetch(session, url, {**payload, "page": page})
        for sro in resp["data"]["data"]:
            items.append(
                (
                    sro["registration_number"],
                    sro["short_description"],
                    sro["id"],
                    "nopriz",
                )
            )
    return items


async def get_nostroy_sro_items(session):
    """List of active SRO records from NOSTROY."""
    url = "https://reestr.nostroy.ru/api/sro/list"
    payload = {
        "filters": {"state": "enabled"},
        "pageCount": str(PAGE_SIZE),
        "sortBy": {},
    }
    first = await fetch(session, url, {**payload, "page": 1})
    pages = int(first["data"]["countPages"])
    items = []
    for page in range(1, pages + 1):
        resp = await fetch(session, url, {**payload, "page": page})
        for sro in resp["data"]["data"]:
            items.append(
                (
                    sro["registration_number"],
                    sro["short_description"],
                    sro["id"],
                    "nostroy",
                )
            )
    return items


async def sum_for_one_page(session, list_url, page_num):
    """Sum compensation fund values for one members/list page."""
    async with page_sem:
        resp = await fetch(session, list_url, build_member_payload(page_num))
        return extract_compfund_sum(resp)


async def compute_sro(session, api_base, reg_no, short_desc, sid, sem):
    """Process one SRO and return a row for CSV output."""
    async with sem:
        list_url = f"{api_base}/{sid}/member/list"

        try:
            first = await fetch(session, list_url, build_member_payload(1))
            pages = int(first["data"]["countPages"])
            totals = [extract_compfund_sum(first)]

            if pages > 1:
                tasks = [
                    asyncio.create_task(sum_for_one_page(session, list_url, page_num))
                    for page_num in range(2, pages + 1)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        raise result
                    totals.append(result)

            total_int = int(round(sum(totals)))
            logger.info("Processed %s (%s): %s", reg_no, sid, total_int)
            return reg_no, short_desc, total_int
        except Exception as exc:
            logger.exception("Failed to process %s (%s): %s", reg_no, sid, exc)
            return reg_no, short_desc, 0


async def main():
    mode = argv[1] if len(argv) > 1 and argv[1] in ("nopriz", "nostroy", "both") else "both"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = resolve_output_path(script_dir)

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(
            ["registration_number", "short_description", "compfund_fee_odo_sum"]
        )

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    connector = aiohttp.TCPConnector(
        ssl=ssl_ctx,
        limit=max(PAGE_CONCURRENCY * MEMBER_CONCURRENCY, PAGE_CONCURRENCY),
        limit_per_host=max(PAGE_CONCURRENCY, MEMBER_CONCURRENCY),
    )
    sem = asyncio.Semaphore(MEMBER_CONCURRENCY)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        all_sros = []
        if mode in ("nopriz", "both"):
            all_sros += await get_nopriz_sro_items(session)
        if mode in ("nostroy", "both"):
            all_sros += await get_nostroy_sro_items(session)

        tasks = [
            asyncio.create_task(
                compute_sro(
                    session,
                    "https://reestr.nopriz.ru/api/sro"
                    if src == "nopriz"
                    else "https://reestr.nostroy.ru/api/sro",
                    reg_no,
                    short_desc,
                    sid,
                    sem,
                )
            )
            for reg_no, short_desc, sid, src in all_sros
        ]

        batch = []
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

    logger.info("Done. CSV saved to %s", out_path)


if __name__ == "__main__":
    asyncio.run(main())
