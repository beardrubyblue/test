import os
import json
import pytz
import random
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from configs import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logging.basicConfig(level=logging.CRITICAL, format="%(message)s")

ANON_TOKEN = None
MSK_TZ = pytz.timezone("Europe/Moscow")
proxy_list = []
proxy_index = 0


async def standart_get_proxies(kind=2, ptype=3, country='RU', max_amount=10000):
    proxy_list = []
    pt = 'http://' if ptype == 3 else 'socks5://'
    if kind == 2 and ptype in [2, 3]:
        params = {'pool_id': '9f687b07-b5f5-4227-9d04-4888ac5be496', 'limit': 10000, 'sla': '0.0'}
        async with aiohttp.ClientSession() as session:
            response = await session.get('https://proxy-manager.ad.dev.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params)
            jd = json.loads(await response.text(errors='replace'))
            for proxy in jd:
                if proxy['proxy']['proxy_type'] == ptype and proxy['proxy']['country_code'] == country:
                    proxy_list.append(f"{pt}{proxy['proxy']['login']}:{proxy['proxy']['password']}@{proxy['proxy']['host']}:{proxy['proxy']['port']}")
    random.shuffle(proxy_list)
    return proxy_list[:max_amount]


async def get_fresh_token():
    global ANON_TOKEN
    logging.critical("🔄 Получаем свежий токен...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://dev.vk.com/getAnonymousToken') as token_resp:
                token_data = await token_resp.json()
                new_token = token_data.get("response", {}).get("token")
                if new_token:
                    ANON_TOKEN = new_token
                    logging.critical("✅ Токен успешно получен перед запуском.")
                else:
                    logging.error("❌ Не удалось получить токен: пустой ответ.")
    except Exception as e:
        logging.error(f"❌ Ошибка при получении токена: {e}")


def send_telegram_message(text):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})


def extract_params(method_data):
    params = method_data.get("contents", {}).get("params", [])
    result = {}
    for idx, param in enumerate(params, 1):
        name = param.get("name")
        type_ = param.get("type")
        if name and type_:
            result[str(idx)] = f"{name}: {type_}"
    return result


async def fetch_method_info(session, method, proxy):
    global ANON_TOKEN

    try:
        url = "https://api.vk.com/method/documentation.getPage"
        params = {
            "access_token": ANON_TOKEN,
            "v": "5.131",
            "lang": "ru",
            "page": f"/method/{method}"
        }
        async with session.get(url, params=params, proxy=proxy, timeout=10) as response:
            data = await response.json()
            info = data.get("response", {}).get("page", {})
            if info:
                param_data = extract_params(info)
                return {method: param_data}
    except Exception as e:
        logging.warning(f"Ошибка при получении {method}: {e}")
    return None


async def parse_all_methods_api(methods):
    global proxy_list, proxy_index
    results = []
    proxy_list = await standart_get_proxies()
    proxy_index = 0

    sem = asyncio.Semaphore(20)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for idx, method in enumerate(methods):
            if proxy_index >= len(proxy_list):
                proxy_list = await standart_get_proxies()
                proxy_index = 0
                logging.critical(f"\nПрокси обновлены, осталось методов: {len(methods) - idx}")

            try:
                pr = proxy_list[proxy_index].split('://')[1].split('@')
                username_proxy, password_proxy = pr[0].split(':')
                host, port = pr[1].split(':')
                proxy_url = f"http://{username_proxy}:{password_proxy}@{host.strip()}:{port.strip()}"
                proxy_index += 1
            except Exception as e:
                logging.warning(f"Ошибка прокси-парсинга: {e}")
                continue

            async def bound_fetch(m=method, p=proxy_url):
                async with sem:
                    result = await fetch_method_info(session, m, p)
                    if result:
                        results.append(result)

            tasks.append(bound_fetch())

        await asyncio.gather(*tasks)
    return results


def compare_data(old, new):
    changes = []
    old_dict = {list(x.keys())[0]: list(x.values())[0] for x in old}
    new_dict = {list(x.keys())[0]: list(x.values())[0] for x in new}

    for method in new_dict:
        if method not in old_dict:
            changes.append(f"Новый метод: {method}")
            continue
        old_fields = old_dict[method]
        new_fields = new_dict[method]

        for key in new_fields:
            if key not in old_fields:
                changes.append(f"{method}: добавлено поле '{new_fields[key]}'")
            elif new_fields[key] != old_fields[key]:
                changes.append(f"{method}: '{old_fields[key]}' → '{new_fields[key]}'")

        for key in old_fields:
            if key not in new_fields:
                changes.append(f"{method}: удалено поле '{old_fields[key]}'")

    return changes


async def run(return_json=False):
    logging.critical(f"\nЗапуск: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with open("method_urls.json", "r", encoding="utf-8") as f:
        urls = json.load(f)
    method_names = [url.split("/")[-1] for url in urls]

    await get_fresh_token()

    parsed_methods = await parse_all_methods_api(method_names)

    prev_file = "labels_data_prev.json"
    previous = []
    if os.path.exists(prev_file):
        with open(prev_file, "r", encoding="utf-8") as f:
            previous = json.load(f)

    changes = compare_data(previous, parsed_methods)

    new_methods = []
    new_method_names = {list(x.keys())[0] for x in parsed_methods}
    old_method_names = set(method_names)
    new_only = new_method_names - old_method_names

    if new_only:
        new_urls = [f"https://dev.vk.com/method/{m}" for m in new_only]
        urls.extend(new_urls)
        new_methods = list(new_only)
        with open("method_urls.json", "w", encoding="utf-8") as f:
            json.dump(urls, f, ensure_ascii=False, indent=2)

    if not return_json:
        if changes or new_methods:
            text = ""
            if new_methods:
                text += "Найдены новые методы:\n" + "\n".join(new_methods) + "\n\n"
            if changes:
                text += "Изменения в параметрах:\n" + "\n".join(changes)
            send_telegram_message(text)
            logging.info(text)
        else:
            send_telegram_message("Изменений не обнаружено.")
            logging.critical("Изменений не обнаружено.")

    with open(prev_file, "w", encoding="utf-8") as f:
        json.dump(parsed_methods, f, ensure_ascii=False, indent=2)

    if not return_json:
        logging.critical({
            "new_methods": new_methods,
            "changes": changes,
            "status": "ok" if changes or new_methods else "no_changes"
        })


async def scheduler():
    await run()

    while True:
        now = datetime.now(MSK_TZ)
        target = now.replace(hour=10, minute=0, second=0, microsecond=0)

        if now >= target:
            target += timedelta(days=1)

        sleep_seconds = (target - now).total_seconds()
        logging.critical(f"Следующий запуск в {target.strftime('%Y-%m-%d %H:%M:%S')} МСК")
        await asyncio.sleep(sleep_seconds)

        await run()
