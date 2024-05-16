import logging
import configs
import datetime
from typing import Dict
import requests
import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
import json
import random
import time
from bs4 import BeautifulSoup
import uvicorn
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from twocaptcha import TwoCaptcha
from playwright.async_api import async_playwright
import psycopg
logging.basicConfig(level=logging.CRITICAL, format="%(message)s")
DB = psycopg.connect(**configs.db_config())
DBC = DB.cursor()
app = FastAPI(title='UniReger')
SECURITY = HTTPBasic()
CC = {
    'server': 'rucaptcha.com',
    'apiKey': configs.TwoCaptchaApiKey,
    'softId': '',
    'callback': '',
    'defaultTimeout': 120,
    'recaptchaTimeout': 600,
    'pollingInterval': 10}
SOLVER = TwoCaptcha(**CC)
HEADERS = {}
with open('Names.txt', 'r') as F:
    Names = F.readlines()
    F.close()
with open('UserAgents.txt', 'r') as F:
    UserAgents = F.readlines()
    F.close()
STATISTICS = []
REGISTRATION_STARTED = False
random.seed()


async def make_request(method: str, url: str, params: Dict = None, headers: Dict = None, cookies: Dict = None, timeout: int = 60):
    async with aiohttp.ClientSession() as session:
        if method == 'get':
            async with session.get(url, params=params, headers=headers, cookies=cookies, timeout=timeout) as resp:
                response = await resp.text(errors='replace')
        if method == 'put':
            async with session.put(url, params=params, headers=headers, cookies=cookies, timeout=timeout) as resp:
                response = await resp.text(errors='replace')
    return response


async def create_proxy_list(kind: int = 3, ptype: str = 3, country: str = 'RU', max_amount: int = 10000):
    """Функция создаёт список из URL-строк прокси вида type://login:password@host:port. Прокси для этого берутся с одного из сайтов: [https://free-proxy-list.net или https://www.sslproxies.org] [https://proxy-manager.arbat.dev] [https://proxy6.net]."""
    proxy_list = []
    pt = ''
    if ptype == 1:
        pt = 'socks4://'
    if ptype == 2:
        pt = 'socks5://'
    if ptype == 3:
        pt = 'http://'
    # Получение бесплатных https прокси случайных стран с сайтов [https://free-proxy-list.net или https://www.sslproxies.org].
    if kind == 1 and ptype == 3:
        async with aiohttp.ClientSession() as session:
            response = await session.get('https://free-proxy-list.net')
            soup = BeautifulSoup(response.content, 'html.parser')
            for row in soup.find('table', attrs={'class': 'table table-striped table-bordered'}).find_all('tr')[1:]:
                tds = row.find_all('td')
                if tds[6].text.strip() == 'yes':
                    proxy_list.append(f'{pt}{tds[0].text.strip()}:{tds[1].text.strip()}')
    # Получение платных https или socks5 прокси указанной страны из объединения proxy6_net_pool сайта [https://proxy-manager.arbat.dev].
    if kind == 2 and ptype in [2, 3]:
        params = {'pool_id': '9f687b07-b5f5-4227-9d04-4888ac5be496', 'limit': 10000, 'sla': '0.7'}
        async with aiohttp.ClientSession() as session:
            response = await session.get('https://proxy-manager.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params)
            jd = json.loads(await response.text(errors='replace'))
            for proxy in jd:
                if proxy['proxy']['proxy_type'] == ptype and proxy['proxy']['country_code'] == country:
                    proxy_list.append(f"{pt}{proxy['proxy']['login']}:{proxy['proxy']['password']}@{proxy['proxy']['host']}:{proxy['proxy']['port']}")
    # Получение одной статичной эксклюзивной русской https или socks5 прокси с сайта [https://proxy6.net].
    if kind == 3 and ptype in [2, 3]:
        proxy_list.append(f'{pt}{configs.ProxyUserOfKind3}@193.187.144.37:8000')
    # Получение платных https прокси указанной страны из объединения playwright сайта [https://proxy-manager.arbat.dev].
    if kind == 4 and ptype == 3:
        params = {'limit': 10000, 'sla': '0.7'}
        async with aiohttp.ClientSession() as session:
            response = await session.get('https://proxy-manager.arbat.dev/pools/b4485d4d-d678-4b5f-9ada-b972db01764b/proxies', params=params)
            jd = json.loads(await response.text(errors='replace'))
            for proxy in jd:
                if proxy['proxy']['proxy_type'] == ptype and proxy['proxy']['country_code'] == country:
                    proxy_list.append(f"{pt}{proxy['proxy']['login']}:{proxy['proxy']['password']}@{proxy['proxy']['host']}:{proxy['proxy']['port']}")
    # Быстрое получение одной платной https или socks5 прокси указанной страны из объединения proxy6_net_pool сайта [https://proxy-manager.arbat.dev], которая дольше всех не использовалась.
    if kind == 5 and ptype in [2, 3]:
        params = {'pool_id': '9f687b07-b5f5-4227-9d04-4888ac5be496', 'sla': '0.7', "country": country}
        async with aiohttp.ClientSession() as session:
            response = await session.get('https://proxy-manager.arbat.dev/proxies/use', params=params)
            jd = json.loads(await response.text(errors='replace'))
            proxy = jd['proxy']
            proxy_list.append(f"{pt}{proxy['login']}:{proxy['password']}@{proxy['host']}:{proxy['port']}")
    random.shuffle(proxy_list)
    return proxy_list[:max_amount]


def get_proxies(kind: int, amount: int = 1000):
    """функция возвращает список полученных проксей с сайта https://free-proxy-list.net или из https://proxy-manager.arbat.dev или из https://www.sslproxies.org"""
    proxies = []
    if kind == 1:
        soup = BeautifulSoup(requests.get('https://free-proxy-list.net').content, 'html.parser')
        for row in soup.find('table', attrs={'class': 'table table-striped table-bordered'}).find_all('tr')[1:]:
            tds = row.find_all('td')
            if tds[2].text.strip() != 'RU' and tds[6].text.strip() == 'yes':
                proxies.append(f'{tds[0].text.strip()}:{tds[1].text.strip()}|{tds[2].text.strip()} 0')
    if kind == 2:
        params = {'limit': amount, 'offset': '0', 'sla': '0.7', "proxy_type": 2}
        # jd = json.loads(requests.get('https://proxy-manager.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params).text)
        jd = json.loads(asyncio.run(make_request('get', 'https://proxy-manager.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params)))
        for proxy in jd:
            proxies.append(proxy['proxy'])
    if kind == 3:
        proxies.append('193.187.144.37:8000|RU 0')
    random.shuffle(proxies)
    logging.critical('Proxies To Use Length: ' + str(len(proxies)))
    return proxies


def finish(reason: str, timeout: int = 100000000):
    logging.critical(reason)
    DB.close()
    logging.critical('Finished At: ' + str(datetime.datetime.now()) + ' Waiting For: ' + str(timeout) + ' Seconds Before Exit.')
    time.sleep(timeout)
    exit(666)


def create_new_proxy_session(kind: int, proxy):
    """функция создаёт новую aiohttp прокси сессию"""
    proxy_user = ''
    if kind == 2:
        proxy_user = f"socks5://{proxy['login']}:{proxy['password']}@"
    if kind == 3:
        proxy_user = configs.ProxyUserOfKind3
    if proxy is None:
        return requests.session()
    else:
        return aiohttp.ClientSession(connector=ProxyConnector.from_url(proxy_user + proxy['host'] + ':' + str(proxy['port'])))


def js_userandom_string(length):
    """таким образом VK создаёт DeviceID и UUID через JS"""
    s = ''
    i = 0
    while i < length:
        s += 'useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict'[random.randint(0, 63)]
        i += 1
    return s


def vkr_auth(proxy_session, uuid, cookies):
    """запрос к https://id.vk.com/auth возвращает html страницу регистрации нового пользователя или входа старого"""
    global HEADERS
    HEADERS = {
        'authority': 'id.vk.com',
        'cache-control': 'max-age=0',
        'referer': 'https://vk.com/',
        'upgrade-insecure-requests': '1',
        'user-agent': random.choice(UserAgents).strip()}
    params = {
        'app_id': '7913379',
        'v': '1.58.6',
        'redirect_uri': 'https://vk.com/join',
        'uuid': uuid,
        'scheme': 'bright_light',
        'action': 'eyJuYW1lIjoibm9fcGFzc3dvcmRfZmxvdyIsInBhcmFtcyI6eyJ0eXBlIjoic2lnbl91cCJ9fQ=='}
    return proxy_session.get('https://id.vk.com/auth', params=params, cookies=cookies, headers=HEADERS, timeout=7)


def vkr_validate_phone(proxy_session, phone, auth_token, device_id, cookies, captcha_key='', captcha_sid='', captcha_ts='', captcha_attempt=''):
    """запрос к https://api.vk.com/method/auth.validatePhone возвращает вердикт VK по отправке звонка или смс на предоставленный телефонный номер"""
    params = {'v': '5.207', 'client_id': '7913379'}
    if captcha_key == '':
        data = {
            'device_id': device_id,
            'external_device_id': '',
            'service_group': '',
            'lang': 'en',
            'phone': phone,
            "auth_token": auth_token,
            'sid': '',
            'allow_callreset': '1',
            'supported_ways': '',
            'access_token': ''}
    else:
        data = {
            'device_id': device_id,
            'external_device_id': '',
            'service_group': '',
            'lang': 'en',
            'phone': phone,
            "auth_token": auth_token,
            'sid': '',
            'allow_callreset': '1',
            'supported_ways': '',
            'captcha_key': captcha_key,
            'captcha_sid': captcha_sid,
            'captcha_ts': captcha_ts,
            'captcha_attempt': captcha_attempt,
            'access_token': ''}
    return proxy_session.post('https://api.vk.com/method/auth.validatePhone', params=params, cookies=cookies, headers=HEADERS, data=data, timeout=30)


def vkr_validate_phone_confirm(proxy_session, phone, auth_token, device_id, sid, code, cookies):
    """запрос к https://api.vk.com/method/auth.validatePhoneConfirm возвращает вердикт VK по приёму значений звонка или смс на предоставленный телефонный номер"""
    params = {'v': '5.207', 'client_id': '7913379'}
    data = {
        'device_id': device_id,
        'sid': sid,
        'phone': phone,
        'code': code,
        'auth_token': auth_token,
        'service_group': '',
        'can_skip_password': '1',
        'access_token': ''}
    return proxy_session.post('https://api.vk.com/method/auth.validatePhoneConfirm', params=params, cookies=cookies, headers=HEADERS, data=data, timeout=30)


def vkr_signup(proxy_session, phone, password, auth_token, device_id, sid, birthday, first_name, last_name, cookies):
    """запрос к https://api.vk.com/method/auth.signup возвращает вердикт VK по регистрации нового пользователя"""
    params = {'v': '5.207', 'client_id': '7913379'}
    data = {
        'phone': phone,
        'sid': sid,
        'password': password,
        'sex': '2',
        'birthday': birthday,
        'device_id': device_id,
        'external_device_id': '',
        'service_group': '',
        'first_name': first_name,
        'last_name': last_name,
        'full_name': '',
        'middle_name': '',
        'client_secret': 'xxx',
        'auth_token': auth_token,
        'extend': '',
        'can_skip_password': '0',
        'create_educational': '',
        'super_app_token': '',
        'access_token': ''}
    return proxy_session.post('https://api.vk.com/method/auth.signup', params=params, cookies=cookies, headers=HEADERS, data=data, timeout=30)


def save_account(phone_jd: str, password: str, info: str):
    """Отправка нового пользователя в БД"""
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
    }
    json_data = {
        "kind_id": 2,
        "phone": phone_jd,
        "password": password,
        "info": json.loads(info)
    }
    # rr = requests.post('https://accman-odata.arbat.dev/create', headers=headers, json=json_data)
    rr = asyncio.run(make_request('post', 'https://accman-odata.arbat.dev/create', headers=headers, params=json_data))
    logging.critical(rr.text)
    return rr


async def get_access_token(phone_string: str, password: str):
    """Запрос к https://oauth.vk.com/token возвращает access_token"""
    while 0 == 0:
        try:
            proxy = get_proxies(2)[0]
            proxy_session = create_new_proxy_session(2, proxy)
            # proxy_session.proxies.update(dict(http=proxy_session.params + proxy.split('|')[0], https=proxy_session.params + proxy.split('|')[0]))
            headers = {
                'authority': 'api.vk.com',
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'no-cache',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://dev.vk.com',
                'pragma': 'no-cache',
                'referer': 'https://dev.vk.com/'}
            params = {
                'grant_type': 'password',
                'v': '5.131',
                'client_id': '2274003',
                'client_secret': 'hHbZxrka2uZ6jB1inYsH',
                'username': phone_string,
                'password': password,
                'scope': 'notify,friends,photos,audio,video,docs,status,notes,pages,wall,groups,messages,offline,notifications,stories'
            }
            async with proxy_session.get('https://oauth.vk.com/token', params=params, headers=headers) as resp:
                rr = await resp.text(errors='replace')
            return rr
        except Exception as e:
            logging.critical(e)


@app.get("/revive-vk-access-token")
def revive_vk_access_token(phone_string: str, password: str, credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """Воскрешение доступа к учётной записи ВК."""
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!', status_code=200)
    html = asyncio.run(get_access_token(phone_string, password))
    return HTMLResponse(content=html, status_code=200)


@app.get("/balance")
def balance(credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """Проверка баланса рукапчи."""
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!', status_code=200)
    html = str(SOLVER.balance())
    return HTMLResponse(content=html, status_code=200)


@app.get("/")
def main():
    """Версия проекта."""
    html = 'Проект: VKReger<BR>Версия: 26.04.2024 17:18'
    return HTMLResponse(content=html, status_code=200)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
