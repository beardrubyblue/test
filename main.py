import logging
import re
import os
import string
import datetime
from typing import Optional
import requests
import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
import json
import random
from transliterate import translit
from playwright.async_api import async_playwright
import time
from bs4 import BeautifulSoup
import uvicorn
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from twocaptcha import TwoCaptcha
from fake_useragent import UserAgent
import psycopg
import configs
from models import AccountCreation
import vkapi
logging.basicConfig(level=logging.CRITICAL, format="%(message)s")

UA = UserAgent()

DB = psycopg.connect(**configs.db_config())
DBC = DB.cursor()

SECURITY = HTTPBasic()

CC = {
    'server': 'rucaptcha.com',
    'apiKey': 'configs.TwoCaptchaApiKey',
    'softId': '',
    'callback': '',
    'defaultTimeout': 120,
    'recaptchaTimeout': 600,
    'pollingInterval': 10}

SOLVER = TwoCaptcha(**CC)

HEADERS = {}

with open('Names.txt') as F:
    Names = F.readlines()
    F.close()
with open('UserAgents.txt') as F:
    UserAgents = F.readlines()
    F.close()

STATISTICS = []
GMAIL_KIND_ID = 3
MAIL_KIND_ID = 19
VK_MAIL_RU = 35
YANDEX_KIND_ID = 50
RAMBLER_KIND_ID = 31
FACEBOOK_KIND_ID = 75
REGISTRATION_STARTED = False
random.seed()
CONTAINER_NAME = 'UniReger' + os.getenv('CONTAINER_NAME')
logging.critical(f"CONTAINER_NAME: {CONTAINER_NAME}")
APP = FastAPI(title='UniReger')
APP.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def screen(id_user, message, id_screen, hnml=' '):
    with open("screen.png", "rb") as f:
        image_data = f.read()
    DBC.execute('INSERT INTO "Testing".screenshot(photo, name, html, id_user, id_screen) VALUES (%s, %s, %s, %s, %s)', (image_data, message, hnml, id_user, id_screen))
    DB.commit()


def standart_finish(reason: str, timeout: int = 10):
    """Стандартная финализация работы контейнера."""
    logging.critical(reason)
    logging.critical('Finished At: ' + str(datetime.datetime.now()) + ' Waiting For: ' + str(timeout) + ' Seconds Before Exit.')
    time.sleep(timeout)
    return


async def standart_request(method: str, url: str, proxy_url: str = None, timeout: int = 60, params: dict = None, headers: dict = None, cookies: dict = None, data: dict = None, jsn: dict = None):
    """Стандартный запрос с возвратом текста его ответа."""
    pc = None
    if url and timeout and proxy_url:
        pc = ProxyConnector.from_url(proxy_url)
    request = 'url,timeout=timeout'
    if params:
        request += ',params=params'
    if headers:
        request += ',headers=headers'
    if cookies:
        request += ',cookies=cookies'
    if data:
        request += ',data=data,'
    if jsn:
        request += ',json=jsn'
    async with aiohttp.ClientSession(connector=pc) as session:
        async with eval(f"session.{method}(url,timeout=timeout,params=params,headers=headers,cookies=cookies,data=data,json=jsn)") as resp:
            response = await resp.text(errors='replace')
            await session.close()
    return response


async def random_delay(min_sec: float, max_sec: float):
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def standart_get_proxies(kind: int = 3, ptype: str = 3, country: str = 'RU', max_amount: int = 10000):
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
            response = await response.text()
            soup = BeautifulSoup(response, 'html.parser')
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
    if kind == 4:
        params = {'limit': 10000, 'sla': '0.7'}
        async with aiohttp.ClientSession() as session:
            response = await session.get('https://proxy-manager.arbat.dev/pools/956e7252-3f64-4822-88d8-d85c65903d01/proxies', params=params)
            jd = json.loads(await response.text(errors='replace'))
            for proxy in jd:
                if proxy['proxy']['proxy_type'] == ptype and proxy['proxy']['country_code'] == country:
                    proxy_list.append(f"http://{proxy['proxy']['login']}:{proxy['proxy']['password']}@{proxy['proxy']['host']}:{proxy['proxy']['port']}")
    # Быстрое получение одной платной https или socks5 прокси указанной страны из объединения proxy6_net_pool сайта [https://proxy-manager.arbat.dev], которая дольше всех не использовалась.
    if kind == 5 and ptype in [2, 3]:
        params = {'pool_id': '9f687b07-b5f5-4227-9d04-4888ac5be496', 'sla': '0.7', "country": country, "proxy_type": 3}
        async with aiohttp.ClientSession() as session:
            response = await session.get('https://proxy-manager.arbat.dev/proxies/use', params=params)
            jd = json.loads(await response.text(errors='replace'))
            proxy = jd['proxy']
            proxy_list.append(f"{pt}{proxy['login']}:{proxy['password']}@{proxy['host']}:{proxy['port']}")
    random.shuffle(proxy_list)
    return proxy_list[:max_amount]


async def standart_execute_sql(sql: str):
    """Подключение к БД проекта и выполнение там переданного SQL с возвращением его результатов."""
    db = await psycopg.AsyncConnection.connect(**configs.db_config())
    dbc = db.cursor()
    await dbc.execute(sql)
    if dbc.description:
        result = await dbc.fetchall()
    else:
        result = None
    await db.close()
    return result


def get_proxies(kind: int, amount: int = 1000):
    """функция возвращает список полученных проксей с сайта https://free-proxy-list.net, или из https://proxy-manager.arbat.dev, или из https://www.sslproxies.org"""
    proxies = []
    if kind == 1:
        pr = {
            'http': 'http://WgdSgr:xfYRp3@193.187.144.37:8000'
        }
        soup = BeautifulSoup(requests.get('https://free-proxy-list.net', proxies=pr).content, 'html.parser')
        for row in soup.find('table', attrs={'class': 'table table-striped table-bordered'}).find_all('tr')[1:]:
            tds = row.find_all('td')
            if tds[2].text.strip() != 'RU' and tds[6].text.strip() == 'yes':
                proxies.append(f'{tds[0].text.strip()}:{tds[1].text.strip()}|{tds[2].text.strip()} 0')
        soup = BeautifulSoup(requests.get('https://www.sslproxies.org').content, 'html.parser')
        for row in soup.find('table', attrs={'class': 'table table-striped table-bordered'}).find_all('tr')[1:]:
            tds = row.find_all('td')
            if tds[2].text.strip() != 'RU' and tds[6].text.strip() == 'yes':
                proxies.append(f'{tds[0].text.strip()}:{tds[1].text.strip()}|{tds[2].text.strip()} 0')
    if kind == 2:
        params = {'limit': amount, 'offset': '0', 'sla': '0.5'}
        jd = json.loads(requests.get('https://proxy-manager.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params).text)
        # jd = json.loads(asyncio.run(standart_request('get', 'https://proxy-manager.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params)))
        for proxy in jd:
            proxies.append(proxy['proxy'])
    if kind == 3:
        proxies.append('193.187.144.37:8000|RU 0')
    random.shuffle(proxies)
    logging.critical('Proxies To Use Length: ' + str(len(proxies)))
    return proxies


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


def save_account(phone_jd: str, password: str, info: str, humanoid_id: int = None):
    """Сохранение новой учётной записи в БД"""
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
    }
    json_data = {
        "kind_id": 2,
        "phone": phone_jd,
        "password": password,
        "info": json.loads(info),
        "humanoid_id": humanoid_id
    }
    rr = requests.post('https://accman.ad.dev.arbat.dev/create', headers=headers, json=json_data)
    # rr = asyncio.run(make_request('post', 'https://accman.ad.dev.arbat.dev/create', headers=headers, params=json_data))
    logging.critical(rr.text)
    return rr


def get_access_token(phone_string: str, password: str):
    """Запрос к https://oauth.vk.com/token возвращает access_token"""
    while 0 == 0:
        try:
            proxy = get_proxies(2)[0]
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
            rr = requests.get('https://oauth.vk.com/token', params=params, headers=headers, timeout=10, proxies={'https': f"socks5://{proxy['login']}:{proxy['password']}@{proxy['host']}:{proxy['port']}"})
            return rr
        except Exception as e:
            logging.critical(e)


@APP.get("/vk-revive-access-token")
def vk_revive_access_token(phone_string: str, password: str, credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """Воскрешение доступа к учётной записи ВК."""
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!')
    html = get_access_token(phone_string, password).content
    return HTMLResponse(content=html)


@APP.get("/vk-execute-api-method")
def vk_execute_api_method(account_id: int = 51, api_method: str = 'https://api.vk.com/method/groups.getById', v: str = '5.154', ids: str = '1,2,3,4,5,6,7,8,9,10', offset: int = 0, credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """Выполнение API методов ВК."""
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!')
    at = asyncio.run(standart_execute_sql(f"select info->>'access_token' from accounts where id={account_id}"))
    html = 'Try Another Method please. A ha Ha ha ha HAAAA !!! :)'
    if api_method == 'https://api.vk.com/method/users.get':
        html = asyncio.run(standart_request('post', api_method, data={'user_ids': ids, 'access_token': at[0], 'v': v}))
    if api_method == 'https://api.vk.com/method/groups.getById':
        html = asyncio.run(standart_request('post', api_method, data={'group_ids': ids, 'access_token': at[0], 'v': v}))
    if api_method == 'https://api.vk.com/method/users.getSubscriptions':
        html = asyncio.run(standart_request('post', api_method, data={'user_id': int(ids), 'offset': offset, 'extended': True, 'count': 1, 'access_token': at[0], 'v': v}))
    if api_method == 'https://api.vk.com/method/wall.get':
        html = asyncio.run(standart_request('post', api_method, data={'domain': int(ids), 'access_token': at[0], 'v': v}))
    return HTMLResponse(content=html)


@APP.get("/vk-mass-accounts-check")
def vk_mass_accounts_check(account_kind_id: int = 2, limit: int = 10, offset: int = 0, api_method: str = 'https://api.vk.com/method/groups.getById', v: str = '5.154', credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """Выполнение массовое проверки учётных записей ВК."""
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!')
    accounts = asyncio.run(standart_execute_sql(f"select id, info->>'access_token' from accounts where kind_id={account_kind_id} order by id limit {limit} offset {offset}"))
    proxy_list = asyncio.run(standart_get_proxies(kind=2, ptype=2))
    logging.critical('Proxy List Length: ' + str(len(proxy_list)))
    for account in accounts:
        success = False
        try_number = 0
        proxy_url = proxy_list[(account[0] - 1) % len(proxy_list)]
        while success is False:
            try_number += 1
            try:
                if api_method == 'https://api.vk.com/method/groups.getById':
                    ids_count = random.randint(1, 10)
                    ids = ''
                    for c in range(ids_count):
                        ids += str(random.randint(1, 200000000)) + ','
                    resp = asyncio.run(standart_request('post', api_method, proxy_url=proxy_url, data={'group_ids': ids[:-1], 'access_token': account[1], 'v': v}))
                jr = json.loads(resp)
                logging.critical('ProxyURL: ' + proxy_url + ' AccountID: ' + str(account[0]) + ' ' + str(jr))
                success = True
            except Exception as e:
                logging.critical(f'TRY #{try_number} ProxyURL: {proxy_url} {e}')
                time.sleep(5)
                if try_number % 5 == 0:
                    proxy_url = random.choice(proxy_list)
    html = '!WELL DONE!'
    return HTMLResponse(content=html)


@APP.get("/vk-register")
# def vk_register(kind='1', credentials: HTTPBasicCredentials = Depends(SECURITY)):
def vk_register(kind='1'):
    """регистрация одного или пачки учётных записей ВК"""
    global REGISTRATION_STARTED
    # if credentials.username != 'AlanD' or credentials.password != 'Bober666':
    #     return HTMLResponse(content='В доступе отказано!', status_code=200)
    # if REGISTRATION_STARTED:
    #     return HTMLResponse(content='ERROR! Only One Registration Process Allowed!', status_code=404)
    REGISTRATION_STARTED = True
    html_response = ''
    html_errors = ''
    logging.critical('Registration Started At: ' + str(datetime.datetime.now()))
    html_response += 'Registration Started At: ' + str(datetime.datetime.now())
    for n in range(200):
        logging.critical('STEP NUMBER: ' + str(n + 1))
        pl = get_proxies(1)
        html_response += '<BR><BR>' + str(n + 1) + ' ---------------------------------------------------- Proxies Founded: ' + str(len(pl)) + '<BR>'
        proxy_session = requests.session()
        for c, proxy in enumerate(pl):
            html_response += '<BR>' + str(c + 1) + ' ' + str(datetime.datetime.now()) + ' ----------------------------------------------------------------------------------'
            html_response += '<BR>Proxy: ' + proxy
            proxy_session.proxies.update(dict(http=proxy.split('|')[0], https=proxy.split('|')[0]))
            # logging.critical(proxy_session.get('https://icanhazip.com').text)
            phone_jd = json.loads(requests.get('http://10.9.20.135:3000/phones/random?service=vk&bank=virtual').text)
            phone_string = '+' + phone_jd['phone'][0] + ' ' + phone_jd['phone'][1:4] + ' ' + phone_jd['phone'][4:7] + '-' + phone_jd['phone'][7:9] + '-' + phone_jd['phone'][9:11]
            html_response += '<BR>Phone: ' + phone_string
            cookies = {}
            uuid = js_userandom_string(21)
            device_id = js_userandom_string(21)
            try:
                rr = vkr_auth(proxy_session, uuid, cookies)
                cookies = rr.cookies
                # if rr.text[:10] == '{"error":{':
                #     jd = json.loads(rr.text)['error']
                #     if jd['error_code'] != 9:
                #         response = requests.get(jd['captcha_img'])
                #         with open("LastCaptcha.jpg", 'wb') as f:
                #             f.write(response.content)
                #             f.close()
                #         cid = SOLVER.send(file="LastCaptcha.jpg")
                #         time.sleep(20)
                #         ck = SOLVER.get_result(cid)
                #         rr = vkr_auth(proxy_session, uuid, cookies, ck, jd['captcha_sid'], jd['captcha_ts'], jd['captcha_attempt'])
                #         cookies = rr.cookies
                soup = BeautifulSoup(rr.text, 'lxml')
                s1 = soup.head.findAll('script')[2].text
                auth_token = s1[s1.find('"access_token":"') + 16:s1.find('","anonymous_token"')]
                logging.critical('AUTH TOKEN: ' + auth_token)
                html_response += '<BR>Auth Token: ' + auth_token
                rr = vkr_validate_phone(proxy_session, phone_string, auth_token, device_id, cookies)
                cookies = rr.cookies
                if rr.text[:10] == '{"error":{':
                    jd = json.loads(rr.text)['error']
                    if jd['error_code'] != 9:
                        response = requests.get(jd['captcha_img'])
                        with open("LastCaptcha.jpg", 'wb') as f:
                            f.write(response.content)
                            f.close()
                        cid = SOLVER.send(file="LastCaptcha.jpg")
                        time.sleep(20)
                        ck = SOLVER.get_result(cid)
                        rr = vkr_validate_phone(proxy_session, phone_string, auth_token, device_id, cookies, ck, jd['captcha_sid'], jd['captcha_ts'], jd['captcha_attempt'])
                        logging.critical(rr.text)
                        cookies = rr.cookies
                jd = json.loads(rr.text)['response']
                login_sid = jd['sid']
                logging.critical('Login SID: ' + login_sid)
                html_response += '<BR>Phone Validation Response: ' + rr.text + '<BR>'
                time.sleep(1.16)
                for r in range(50):
                    rr = requests.get('http://10.9.20.135:3000/phones/messages/' + str(phone_jd['phone']) + '?fromTs=0' + str(phone_jd['listenFromTimestamp']))
                    if rr.text != '{"messages":[]}':
                        break
                    time.sleep(0.2)
                logging.critical('SMS response: ' + rr.text)
                jd = json.loads(rr.text)['messages']
                html_response += '<BR>SMS Response: ' + rr.text + '<BR>'
                rr = vkr_validate_phone_confirm(proxy_session, phone_string, auth_token, device_id, login_sid, str(jd).split(' ')[1], cookies)
                html_response += '<BR>Phone Validation Confirmation Response: ' + rr.text + '<BR>'
                cookies = rr.cookies
                jd = json.loads(rr.text)['response']
                logging.critical('SID: ' + login_sid)
                password = js_userandom_string(21)
                hrr = requests.get('https://accman.ad.dev.arbat.dev/get-innocent-humanoid?kind_id=2')
                humanoid = json.loads(hrr.text)
                first_name = humanoid['first_name']
                last_name = humanoid['last_name']
                birthday = f"{humanoid['birth_date'][8:10]}.{humanoid['birth_date'][5:7]}.{humanoid['birth_date'][0:4]}"
                # first_name = random.choice(Names).split(' ')[1]
                # last_name = random.choice(Names).split(' ')[0]
                # birthday = str(random.randint(10, 28)) + '.0' + str(random.randint(1, 9)) + '.' + str(random.randint(1980, 2004))
                rr = vkr_signup(proxy_session, phone_string, password, auth_token, device_id, jd['sid'], birthday, first_name, last_name, cookies)
                html_response += '<BR>Signup Response: ' + rr.text + '<BR>'
                logging.critical('RR TEXT: ' + rr.text + ' ' + phone_string + ' ' + password)
                jd = json.loads(rr.text)
                if 'response' in jd:
                    jd = json.loads(rr.text)['response']
                    time.sleep(8)
                    rt = get_access_token(phone_string, password).text
                    logging.critical('Access Token Getting Response: ' + rt)
                    html_response += '<BR>Access Token Getting Response: ' + rt
                    access_token = rt.split('{"access_token":"')[1].split('","expires_in"')[0]
                    requests.post('http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?', data={'service': 'vk'})
                    info = json.dumps({'mid': str(jd['mid']), 'first_name': first_name, 'last_name': last_name, 'birth_date': birthday, 'access_token': access_token}, ensure_ascii=False)
                    save_account(phone_jd['phone'], password, info, humanoid['id'])
                    logging.critical('MISSION ACCOMPLISHED! New Account: ' + phone_jd['phone'] + ':' + password)
                    html_response += '<BR><BR>MISSION ACCOMPLISHED! New Account:<BR>' + phone_jd['phone'] + ':' + password + '<BR>' + info + '<BR>'
                    if kind == '1':
                        return HTMLResponse(content=html_response)
                elif 'error' in jd:
                    jd = json.loads(rr.text)['error']
                    if jd['error_msg'] == "Flood control: can't accept this phone (security reason)":
                        requests.post('http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?', data={'service': 'vk'})
                        html_response += "<BR>" + phone_jd['phone'] + " FLOOD CONTROL: can't accept this phone (security reason)<BR>"
                        logging.critical('FLOOD CONTROL! Account: ' + phone_jd['phone'] + ':' + password)
            except Exception as E:
                logging.critical(E)
                logging.critical('----------------------------------------------------------')
                # requests.post('http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?', json={'service': 'vk', 'broken': True})
                html_errors += '<BR>' + str(E) + '<BR>'
        time.sleep(random.randint(1, 180))
    logging.critical('Registration Finished At: ' + str(datetime.datetime.now()))
    html_response += '<BR>Registration Finished At: ' + str(datetime.datetime.now()) + '<BR><BR><BR>'
    html_response += '<BR>Errors List:<BR>' + html_errors
    REGISTRATION_STARTED = False
    return HTMLResponse(content=html_response)


@APP.get("/rucaptcha-balance")
def rucaptcha_balance(credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """Проверка баланса рукапчи."""
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!')
    html = str(SOLVER.balance())
    return HTMLResponse(content=html)


# @app.get("/")
# def main():
#     """Версия проекта."""
#     return JSONResponse(content=json.loads(json.dumps({'project': 'UniReger', 'version': '30.05.2024 14:00'})), status_code=200)


def add_loggs(message, id_log):
    DBC.execute('INSERT INTO "Testing".logs(log, id_log) VALUES (%s, %s)', (message, id_log))
    DB.commit()


def generate_mail(first_name, last_name, year):
    first_name = translit(first_name, 'ru', reversed=True)
    last_name = translit(last_name, 'ru', reversed=True)
    gmail = f'{first_name.lower()}.{last_name.lower()}{year + str(random.randint(1, 999))}'
    gmail = gmail.replace('`', '')
    gmail = gmail.replace("'", '')
    return gmail


def generate_pass(length):
    characters = string.ascii_letters + string.digits + string.digits
    password = ''.join(random.choice(characters) for _ in range(length))
    return password


async def send_acc(kind_id, phone_jd: str, password, first_name, last_name, birthday, humanoid_id, last_cookies, email: str = ''):
    data = {
        'kind_id': kind_id,
        'phone': phone_jd,
        'password': password,
        'info': {
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'birth_date': birthday
        },
        "humanoid_id": humanoid_id,
        "last_cookies": last_cookies
    }
    logging.critical(data)
    async with aiohttp.ClientSession() as session:
        async with session.post('https://accman.ad.dev.arbat.dev/create', json=data) as response:
            return response


async def send_acc_vk(phone_jd: str, password, mid, first_name, last_name, birthday, humanoid_id, last_cookies, access_token):
    data = {
        'kind_id': 2,
        'phone': phone_jd,
        'password': password,
        'info': {
            'mid': mid,
            'first_name': first_name,
            'last_name': last_name,
            'birth_date': birthday,
            'access_token': access_token
        },
        "humanoid_id": humanoid_id,
        "last_cookies": last_cookies
    }
    logging.critical(data)
    async with aiohttp.ClientSession() as session:
        async with session.post('https://accman.ad.dev.arbat.dev/create', json=data) as response:
            return response


@APP.get("/gmail-register")
async def gmail_register(count: Optional[int] = None):
    """Регистрация одного или пачки учётных записей GMail"""

    accounts = []
    count_acc = 0
    proxy_list = await standart_get_proxies(kind=2)

    proxy_index = 0
    if len(proxy_list) == 0:
        standart_finish('There Are No Proxies Found! Waiting 1000 Seconds Before Exit.')
    logging.critical(len(proxy_list))
    while count is None or len(accounts) < count:

        # -----Proxy generate-----
        if proxy_index >= len(proxy_list):
            proxy_list = await standart_get_proxies(kind=2)
            proxy_index = 0
        pr = proxy_list[proxy_index].split('://')[1].split('@')
        username, password = pr[0].split(':')
        host, port = pr[1].split(':')
        if " " in host:
            host = host.replace(" ", "")
        proxy = {
            'server': f'http://{host}:{port}',
            'username': username,
            'password': password
        }

        # -----UserAgent generate-----
        user_agent = UA.random

        # -----User generate-----
        users = json.loads(
            await standart_request('get', f'https://accman.ad.dev.arbat.dev/get-innocent-humanoid?kind_id={GMAIL_KIND_ID}'))

        # -----Start simulation-----
        async with async_playwright() as playwright:
            chromium = playwright.firefox
            browser = await chromium.launch(headless=False)
            context = await browser.new_context(proxy=proxy, user_agent=user_agent)
            page = await context.new_page()
            account = await gmail_account_registration(context, page, users)
            await browser.close()
            add_loggs(f'Ответ: {account}', 1)
            accounts.append(account)
            add_loggs('------------------------------------', 1)

        proxy_index += 1
        count_acc += 1
        logging.critical(count_acc)
    return {'accounts': accounts}


async def gmail_account_registration(context, page, users):

    # -----Params-----
    global sms
    humanoid_id = users['id']
    add_loggs(f'humanoid_id: {humanoid_id}', 1)
    first_name = users['first_name']
    last_name = users['last_name']
    phone_jd = json.loads(await standart_request('get', 'http://10.9.20.135:3000/phones/random?service=gmail&bank=virtual'))
    phone_string = '+' + phone_jd['phone'][0] + ' ' + phone_jd['phone'][1:4] + ' ' + phone_jd['phone'][4:7] + '-' + \
                   phone_jd['phone'][7:9] + '-' + phone_jd['phone'][9:11]
    day = users['birth_date'].split('-')[2]
    month = users['birth_date'].split('-')[1]
    year = users['birth_date'].split('-')[0]
    if users['sex'] == 'female':
        gender = 1
    else:
        gender = 2
    gmail = generate_mail(first_name, last_name, year)
    password = generate_pass(random.randint(15, 20))

    # -----Mining-----
    try:
        await page.goto('https://google.com')
        await asyncio.sleep(4)
        await page.click('xpath=/html/body/div[1]/div[1]/div/div/div/div/div[2]/a')
        await asyncio.sleep(4)
        await page.locator('xpath=//*[@id="yDmH0d"]/c-wiz/div/div[3]/div/div[2]/div/div/div[1]/div/button').click()
        await asyncio.sleep(2)
        await page.locator('xpath=//*[@id="yDmH0d"]/c-wiz/div/div[3]/div/div[2]/div/div/div[2]/div/ul/li[1]').click()

        # -----FullName-----
        await random_delay(0.3, 1)
        await page.type('#firstName', first_name, delay=random.uniform(0.1, 0.3))
        await random_delay(0.3, 1)
        await page.type('#lastName', last_name, delay=random.uniform(0.1, 0.3))
        await random_delay(0.3, 1)
        await page.click('.VfPpkd-LgbsSe')
        await page.wait_for_timeout(2000)

        # -----Birthday-----
        await page.type('#day', day, delay=random.uniform(0.1, 0.3))
        await random_delay(0.3, 1)
        await page.select_option('#month', index=int(month))
        await random_delay(0.3, 1)
        await page.type('#year', year, delay=random.uniform(0.1, 0.3))

        # -----Gender-----
        await random_delay(0.3, 1)
        await page.select_option('#gender', index=gender)
        await random_delay(0.3, 1)
        await page.click('.VfPpkd-LgbsSe')
        await random_delay(3, 4.5)

        # -----Gmail-----
        element = await page.query_selector('body')
        elem = await element.text_content()
        if 'Создать собственный адрес Gmail' in elem.strip():
            await random_delay(1, 1.5)
            await page.click(
                'xpath=/html/body/div[1]/div[1]/div[2]/c-wiz/div/div[2]/div/div/div/form/span/section/div/div/div[1]/div[1]/div/span/div[3]/div/div[1]/div/div[3]/div')
            await random_delay(1, 1.5)
            await page.type('input[name="Username"]', gmail, delay=random.uniform(0.1, 0.3))
            await random_delay(0.3, 1)
            await page.click('#next', timeout=100)
            await random_delay(3.5, 4.5)
        else:
            await page.type('input[name="Username"]', gmail, delay=random.uniform(0.1, 0.3))
            await random_delay(0.3, 1)
            await page.click('#next', timeout=100)

        # -----Password-----
        await page.type('input[name="Passwd"]', password, delay=random.uniform(0.1, 0.3))
        await random_delay(0.3, 1)
        await page.type('input[name="PasswdAgain"]', password, delay=random.uniform(0.1, 0.3))
        await random_delay(0.3, 1)
        await page.click('.VfPpkd-LgbsSe')
        await random_delay(4, 6)
        element = await page.query_selector('body')
        elem = await element.text_content()
        if 'Отсканируйте QR-код, чтобы подтвердить номер телефона' in elem.strip():
            await asyncio.sleep(60000000000000000000000000000000000000000000000)

        # -----Phone-----
        element = await page.query_selector('body')
        elem = await element.text_content()
        if 'wants to access your Google Account' in elem.strip() or 'Не удалось создать аккаунт Google.' in elem.strip():
            return {'Ошибка': 'Не удалось создать аккаунт Google.'}

        await page.type('#phoneNumberId', phone_string, delay=random.uniform(0.1, 0.3))
        await random_delay(0.3, 1)
        await page.click('.VfPpkd-LgbsSe')
        await random_delay(1.3, 2)

        # -----Sms-----
        for r in range(30):
            url = 'http://10.9.20.135:3000/phones/messages/' + str(phone_jd['phone']) + '?fromTs=0' + str(
                phone_jd['listenFromTimestamp'])
            sms = await standart_request('get', url)
            if sms != '{"messages":[]}':
                break
            await asyncio.sleep(0.2)
        pattern = r'\d+'
        sms = re.findall(pattern, sms)
        sms = ' '.join(sms)

        if not sms:
            return 'bad proxy or phone'

        await page.type('#code', sms, delay=random.uniform(0.1, 0.3))
        await random_delay(0.3, 1)
        await page.click('.VfPpkd-LgbsSe')
        await random_delay(2.3, 3)

        # -----Politic-----
        await page.click('xpath=/html/body/div[1]/div[1]/div[2]/div/div/div[3]/div/div[1]/div[2]/div/div/button')
        await random_delay(2.3, 3)
        await page.click('.VfPpkd-LgbsSe')
        await random_delay(2.3, 3)
        await page.click('xpath=/html/body/div[1]/div[1]/div[2]/c-wiz/div/div[3]/div/div[1]/div/div/button')
        await random_delay(2.3, 3)

        cookies = await context.cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
        cookie_list = [cookie_dict]
        while True:
            gmail = f'{gmail}@gmail.ru'
            res = await send_acc(GMAIL_KIND_ID, phone_jd['phone'], password, first_name, last_name, f'{day}.{month}.{year}', humanoid_id,
                                 cookie_list, gmail)
            if res.status == 200:
                break
        url = 'http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?'
        await standart_request('post', url, data={'service': 'gmail'})

        return AccountCreation(
            phone=phone_jd['phone'],
            password=password,
            humanoid_id=humanoid_id,
            last_cookies=cookie_list
        )
    except Exception as e:
        add_loggs(f'Ошибка:   {e}', 1)
        return e


@APP.get("/mailru-register")
async def mailru_register(count: Optional[int] = None):
    """регистрация одного или пачки учётных записей EMail"""
    accounts = []
    count_acc = 0
    proxy_list = await standart_get_proxies(kind=2)
    proxy_index = 0
    if len(proxy_list) == 0:
        standart_finish('There Are No Proxies Found! Waiting 1000 Seconds Before Exit.')
    logging.critical(len(proxy_list))
    while count is None or len(accounts) < count:
        if proxy_index >= len(proxy_list):
            proxy_list = await standart_get_proxies(kind=2)
            proxy_index = 0
        pr = proxy_list[proxy_index].split('://')[1].split('@')
        username, password = pr[0].split(':')
        host, port = pr[1].split(':')
        if " " in host:
            host = host.replace(" ", "")
        proxy = {
            'server': f'http://{host}:{port}',
            'username': username,
            'password': password
        }
        user = json.loads(
            await standart_request('get', f'https://accman.ad.dev.arbat.dev/get-innocent-humanoid?kind_id={MAIL_KIND_ID}'))

        async with async_playwright() as playwright:
            chromium = playwright.chromium
            browser = await chromium.launch()
            context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0', proxy=proxy)
            page = await context.new_page()
            account = await email_account_registration(context, page, user)
            await browser.close()
            add_loggs(f'Ответ: {account}', 1)
            accounts.append(account)
            add_loggs('------------------------------------', 1)

        proxy_index += 1
        count_acc += 1
        logging.critical(count_acc)
    return {'accounts': accounts}


async def email_account_registration(context, page, user):
    global sms, password, cookie_list
    humanoid_id = user['id']
    first_name = user['first_name']
    last_name = user['last_name']
    day = int(user['birth_date'].split('-')[2])
    month = int(user['birth_date'].split('-')[1])
    year = user['birth_date'].split('-')[0]
    if user['sex'] == 'female':
        gender = 'female'
    else:
        gender = 'male'
    email = generate_mail(first_name, last_name, year)
    phone_jd = json.loads(await standart_request('get', 'http://10.9.20.135:3000/phones/random?service=vk&bank=virtual'))

    phone_string = '+' + phone_jd['phone'][0] + ' ' + phone_jd['phone'][1:4] + ' ' + phone_jd['phone'][4:7] + '-' + \
                   phone_jd['phone'][7:9] + '-' + phone_jd['phone'][9:11]
    try:
        await page.goto("https://account.mail.ru/signup")
        await asyncio.sleep(2)
        add_loggs('Start Registration', 1)

        await page.wait_for_selector('.input-0-2-106', timeout=30000)
        elements = await page.query_selector_all('.input-0-2-106')
        try:
            await elements[0].fill(first_name, timeout=1000)
            await elements[1].fill(last_name, timeout=1000)
            await page.click('.daySelect-0-2-122', timeout=1000)
            await page.click(f'#react-select-2-option-{day - 1}', timeout=1000)
            await asyncio.sleep(1)
            await page.click('xpath=/html/body/div[1]/div[2]/div/div[3]/div[3]/div[1]/div/div[3]/div/form/div[4]/div[2]/div/div/div/div[3]', timeout=1000)
            await page.click(f'#react-select-3-option-{month - 1}', timeout=1000)
            await asyncio.sleep(1)
            await page.click('.yearSelect-0-2-123', timeout=1000)
            await page.click(f'[data-test-id="select-value:{year}"]', timeout=1000)
            if gender == 'male':
                await page.click('input[value="male"]', force=True)
            else:
                await page.click('input[value="female"]', force=True)
            await elements[2].fill(email, timeout=1000)
            await elements[3].fill(phone_string, timeout=1000)
            await asyncio.sleep(5)
            await page.click('xpath=//*[@id="root"]/div/div[3]/div[3]/div[1]/div/div[3]/div/form/div[21]/button')
            logging.critical('sms')
            element = await page.query_selector('body')
            elem = await element.text_content()
            if "Номер уже используется другим пользователем" in elem.strip():
                return {'Error': 'this phone is already in use'}
            await asyncio.sleep(10)
            for r in range(10):
                url = 'http://10.9.20.135:3000/phones/messages/' + str(phone_jd['phone']) + '?fromTs=0' + str(
                    phone_jd['listenFromTimestamp'])
                sms = await standart_request('get', url)
                if sms != '{"messages":[]}':
                    break
                await asyncio.sleep(0.2)
            pattern = r'\d+'
            sms = re.findall(pattern, sms)
            sms = ' '.join(sms)
            logging.critical(sms)
            await page.fill('input', sms, timeout=1000)
            # await page.click('button[type="submit"]', timeout=1000)
            await asyncio.sleep(5)
            phone = phone_jd['phone']
            # logging.critical(phone)
            # await asyncio.sleep(10)
            element = await page.query_selector('body')
            elem = await element.text_content()
            if "Информация о себе" in elem.strip():
                logging.critical('Информация о себе')
                await asyncio.sleep(2)
                await page.click('button[form="signupForm"]', timeout=1000)
                await asyncio.sleep(5)
            elif "Завершение регистрации" in elem.strip():
                logging.critical('Завершение регистрации')
                vk_user = await standart_execute_sql(f"SELECT password FROM accounts WHERE phone = '{phone}'")
                logging.critical(vk_user)
                await page.fill('input', vk_user[0][0], timeout=1000)
                await asyncio.sleep(5)
                await page.click('xpath=/html/body/div[1]/div/div/div/div/div[1]/div[1]/div/div/div/div/form/div[4]/button[1]')
            # elif "Письмо первое — с чего начать" in elem.strip():
            #     logging.critical('Письмо первое — с чего начать')
            #     cookies = await context.cookies()
            #     cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            #     cookie_list = [cookie_dict]
            #     add_loggs('Finish registration', 1)
            #     while True:
            #         email = f'{email}@mail.ru'
            #         password = ''
            #         res = await send_acc(20, phone, password, first_name, last_name,
            #                              f'{day}.{month}.{year}', humanoid_id, cookie_list, email)
            #         url = 'http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?'
            #         await standart_request('post', url, data={'service': 'mail'})
            #         if res.status == 200:
            #             break
            #         await asyncio.sleep(60)
            #     add_loggs('Created', 1)
            #     return AccountCreation(
            #         phone=phone,
            #         password=password,
            #         humanoid_id=humanoid_id,
            #         last_cookies=cookie_list
            #     )
            # else:
            #     logging.critical('Иначееееееее')
            #     await asyncio.sleep(10)

            await asyncio.sleep(20)
            element = await page.query_selector('body')
            elem = await element.text_content()
            if "Письмо первое — с чего начать" in elem.strip():
                cookies = await context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                cookie_list = [cookie_dict]
                add_loggs('Finish registration', 1)
                while True:
                    email = f'{email}@mail.ru'
                    password = ''
                    res = await send_acc(20, phone, password, first_name, last_name,
                                         f'{day}.{month}.{year}', humanoid_id, cookie_list, email)
                    url = 'http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?'
                    await standart_request('post', url, data={'service': 'mail'})
                    if res.status == 200:
                        break
                    await asyncio.sleep(60)
                add_loggs('Created', 1)
            return AccountCreation(
                phone=phone,
                password=password,
                humanoid_id=humanoid_id,
                last_cookies=cookie_list
            )
        except Exception as e:
            logging.critical(e)
            return f"Ошибка при заполнении: {e}"
    except Exception as e:
        return e


@APP.get("/@vk-mail-ru-register")
async def vk_mail_ru(count: Optional[int] = None):
    """регистрация одного или пачки учётных записей VKMail """
    accounts = []
    count_acc = 0
    proxy_list = await standart_get_proxies(kind=2)
    proxy_index = 0
    if len(proxy_list) == 0:
        standart_finish('There Are No Proxies Found! Waiting 1000 Seconds Before Exit.')
    logging.critical(len(proxy_list))
    users = await standart_execute_sql('select * from accounts where kind_id = 2 and block = false and phone not in (select phone from accounts where kind_id = 35) order by id desc')
    logging.critical(len(users))
    while count is None or len(accounts) < count:
        if len(accounts) == count:
            standart_finish('MISSION ACCOMPLISHED!')
        if proxy_index >= len(proxy_list):
            proxy_list = await standart_get_proxies(kind=2)
            proxy_index = 0
        pr = proxy_list[proxy_index].split('://')[1].split('@')
        username, password = pr[0].split(':')
        host, port = pr[1].split(':')
        if " " in host:
            host = host.replace(" ", "")
        proxy = {
            'server': f'http://{host}:{port}',
            'username': username,
            'password': password
        }
        async with async_playwright() as playwright:
            chromium = playwright.chromium
            browser = await chromium.launch()
            context = await browser.new_context(proxy=proxy)
            page = await context.new_page()
            account = await vk_mail_ru_registration(context, page, users[count_acc])
            await browser.close()
            add_loggs(f'Ответ: {account}', 1)
            accounts.append(account)
            add_loggs('------------------------------------', 1)

        proxy_index += 1
        count_acc += 1
        logging.critical(count_acc)
    standart_finish('MISSION ACCOMPLISHED!')
    return {'accounts': accounts}


async def vk_mail_ru_registration(context, page, user):
    # -----params-----
    global sms
    humanoid_id = user[7]
    phone = user[2]
    password = user[3]
    humanoid_first_name = user[4]['first_name']
    humanoid_last_name = user[4]['last_name']
    humanoid_birth_date = user[4]['birth_date']
    try:
        await page.goto("https://id.vk.com/")
        await random_delay(1, 1.5)
        add_loggs('Start Registration', 1)
        await page.click('xpath=//*[@id="about_section"]/section/div[1]/div/div[1]/button')
        await random_delay(2, 3.5)
        await page.type('input[name="login"]', phone[1:], delay=random.uniform(0.1, 0.3))
        await random_delay(2, 3.5)
        await page.click('button[type="submit"]')
        await random_delay(5, 6.5)
        element = await page.query_selector('body')
        elem = await element.text_content()
        if "Войти при помощи пароля" in elem.strip() or "Sign in using password" in elem.strip():
            await page.click('.vkc__Bottom__switchToPassword')
            await random_delay(2, 3.5)
            await page.type('input[name="password"]', password, delay=random.uniform(0.1, 0.3))
            await random_delay(2, 3.5)
            await page.click('button[type="submit"]')
            await random_delay(2, 3.5)
        else:
            await page.click('button[data-test-id="other-verification-methods"]')
            await random_delay(2, 3.5)
            await page.click('xpath=/html/body/div[1]/div/div/div/div/div[2]/div/div[2]/div/div/div/div/div[2]/div[1]/div/div/div[3]')
            await random_delay(2, 3.5)
            await page.type('input[name="password"]', password, delay=random.uniform(0.1, 0.3))
            await random_delay(2, 3.5)
            await page.click('button[type="submit"]')
            await random_delay(2, 3.5)

            # await page.type('input[name="password"]', password, delay=random.uniform(0.1, 0.3))
            # await random_delay(2, 3.5)
            # await page.click('button[type="submit"]')
        await random_delay(9, 11.5)

        # if humanoid_id is None:
        #     await asyncio.sleep(5)
        #     await page.goto("https://id.vk.com/account/#/main")
        #     await asyncio.sleep(2)
        #     await page.goto("https://id.vk.com/account/#/personal")
        #     await asyncio.sleep(2)
        #     humanoid = json.loads(
        #         await standart_request('get',
        #                                'https://accman.ad.dev.arbat.dev/get-innocent-humanoid?kind_id=35'))
        #     humanoid_first_name = humanoid['first_name']
        #
        #     humanoid_last_name = humanoid['last_name']
        #     humanoid_sex = humanoid['sex']
        #     humanoid_day = int(humanoid['birth_date'].split('-')[2])
        #     humanoid_month = int(humanoid['birth_date'].split('-')[1])
        #     humanoid_year = humanoid['birth_date'].split('-')[0]
        #     await asyncio.sleep(1)
        #     await page.fill('input[name="first_name"]', humanoid_first_name)
        #     await page.fill('input[name="last_name"]', humanoid_last_name)
        #     await asyncio.sleep(1)
        #     await page.click(
        #         'xpath=//*[@id="personal"]/div/div[3]/div/div[1]/div/section/form/div[2]/div[1]/div/div')
        #     await asyncio.sleep(1)
        #     await page.click(f'div[title="{humanoid_sex.title()}"]')
        #     await asyncio.sleep(1)
        #     await page.click('.vkuiDatePicker__year')
        #     await asyncio.sleep(1)
        #     if int(humanoid_year) > 2010:
        #         return {'Error': 'birthday year > 2010'}
        #     await page.click(f'div[title="{humanoid_year}"]')
        #     await page.click('.vkuiDatePicker__month')
        #     await asyncio.sleep(1)
        #     months = {
        #         1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        #         7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
        #     }
        #     month = months.get(humanoid_month)
        #     await page.click(f'div[title="{month}"]')
        #     await page.click('.vkuiDatePicker__day')
        #     await asyncio.sleep(1)
        #     await page.click(f'div[title="{humanoid_day}"]')
        #     await page.click('button[data-test-id="personal-form-submit"]')
        #     new_info = {
        #         "mid": user[4]['mid'],
        #         "first_name": humanoid_first_name,
        #         "last_name": humanoid_last_name,
        #         "birth_date": humanoid['birth_date'],
        #         "access_token": user[4]['access_token']
        #     }
        #     await standart_request('put', f'https://accman.ad.dev.arbat.dev/change-info?account_id={user_id}',
        #                            json=new_info)
        #     DBC.execute(f'update accounts set humanoid_id = {humanoid["id"]} where id = {user_id}')
        #     await asyncio.sleep(2)
        await page.goto("https://vk.mail.ru")
        await random_delay(5, 7.5)
        await page.click('button[type="submit"]')

        await random_delay(10, 12.5)
        element = await page.query_selector('body')
        elem = await element.text_content()
        if "Verify it's you" in elem.strip():
            for r in range(30):
                url = 'http://10.9.20.135:3000/phones/messages/' + user[2] + '?fromTs=0'
                sms = await standart_request('get', url)
                if sms != '{"messages":[]}':
                    break
                await asyncio.sleep(0.2)
            pattern = r"MailRu: \d+"
            sms = re.findall(pattern, sms)
            sms = ' '.join(sms)
            await page.fill('input', sms)
        elif "Привет от VK Почты!" in elem.strip():
            email = await page.locator('img.ph-avatar-img').get_attribute('alt')
            while True:
                cookies = await context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                cookie_list = [cookie_dict]
                res = await send_acc(VK_MAIL_RU, user[2], user[3], humanoid_first_name,
                                     humanoid_last_name, humanoid_birth_date, humanoid_id,
                                     cookie_list, email)
                if res.status == 200:
                    break
                return AccountCreation(
                    kind_id=VK_MAIL_RU,
                    phone=user[2],
                    password=user[3],
                    info=user[4],
                    humanoid_id=humanoid_id,
                    last_cookies=cookie_list
                )
        input_element = await page.query_selector('input')
        input_value = await input_element.input_value()
        if input_value:
            await page.click('button[type="submit"]')
            await asyncio.sleep(10)
            while True:
                cookies = await context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                cookie_list = [cookie_dict]
                email = input_value + '@vk.com'
                res = await send_acc(VK_MAIL_RU, user[2], user[3], humanoid_first_name,
                                     humanoid_last_name, humanoid_birth_date, humanoid_id,
                                     cookie_list, email)
                if res.status == 200:
                    break
            return AccountCreation(
                kind_id=VK_MAIL_RU,
                phone=user[2],
                password=user[3],
                info=user[4],
                humanoid_id=humanoid_id,
                last_cookies=cookie_list
            )
        else:
            add_loggs('Ошибка: No email', 1)
            return {'Error': 'No email'}
    except Exception as e:
        add_loggs(f'Ошибка: {e}', 1)
        return e


# @APP.get("/@ya-mail-ru-register")
# async def ya_mail_ru(count: Optional[int] = None):
#     """регистрация одного или пачки учётных записей YAmail"""
#     accounts = []
#     count_acc = 0
#     proxy_list = await standart_get_proxies(kind=2)
#     proxy_index = 0
#     if len(proxy_list) == 0:
#         standart_finish('There Are No Proxies Found! Waiting 1000 Seconds Before Exit.')
#     logging.critical(len(proxy_list))
#     while count is None or len(accounts) < count:
#         if proxy_index >= len(proxy_list):
#             proxy_list = await standart_get_proxies(kind=2)
#             proxy_index = 0
#         pr = proxy_list[proxy_index].split('://')[1].split('@')
#         username, password = pr[0].split(':')
#         host, port = pr[1].split(':')
#         if " " in host:
#             host = host.replace(" ", "")
#         proxy = {
#             'server': f'http://{host}:{port}',
#             'username': username,
#             'password': password
#         }
#         user = json.loads(
#             await standart_request('get', f'https://accman-odata.arbat.dev/get-innocent-humanoid?kind_id={YANDEX_KIND_ID}'))
#         async with async_playwright() as playwright:
#             chromium = playwright.chromium
#             browser = await chromium.launch()
#             context = await browser.new_context(proxy=proxy)
#             page = await context.new_page()
#             account = await ya_mail_ru_registration(context, page, user)
#             logging.critical(account)
#             await browser.close()
#             add_loggs(f'Ответ: {account}', 1)
#             accounts.append(account)
#             add_loggs('------------------------------------', 1)
#
#         proxy_index += 1
#         count_acc += 1
#         logging.critical(count_acc)
#     return {'accounts': accounts}
#
#
# async def ya_mail_ru_registration(context, page, user):
#     # -----params-----
#     humanoid_id = user['id']
#     first_name = user['first_name']
#     last_name = user['last_name']
#     year = user['birth_date'].split('-')[0]
#     password = generate_pass(random.randint(15, 20))
#     ya_mail = generate_mail(first_name, last_name, year)
#     phone_jd = json.loads(await standart_request('get', 'http://10.9.20.135:3000/phones/random?service=gmail&bank=virtual'))
#     phone_string = phone_jd['phone'][1:4] + ' ' + phone_jd['phone'][4:7] + '-' + phone_jd['phone'][7:9] + '-' + phone_jd['phone'][9:11]
#     try:
#         await page.goto("https://passport.yandex.ru/registration/mail?from=mail&require_hint=1&origin=hostroot_homer_reg_ru&retpath=https%3A%2F%2Fmail.yandex.ru&backpath=https%3A%2F%2Fmail.yandex.ru%3Fnoretpath%3D1")
#         await asyncio.sleep(2)
#         add_loggs('Start Registration', 1)
#         await page.fill('input[name="firstname"]', first_name)
#         await page.fill('input[name="lastname"]', last_name)
#         await page.fill('input[name="login"]', ya_mail)
#         await page.fill('input[name="password"]', password)
#         await page.fill('input[name="password_confirm"]', password)
#         await page.fill('input[name="phone"]', phone_string)
#         await asyncio.sleep(2)
#         await page.click('button[type="submit"]')
#         await asyncio.sleep(2)
#         for r in range(30):
#             url = 'http://10.9.20.135:3000/phones/messages/' + phone_jd['phone'] + '?fromTs=0' + str(
#                 phone_jd['listenFromTimestamp'])
#             sms = await standart_request('get', url)
#             if sms != '{"messages":[]}':
#                 break
#             await asyncio.sleep(0.2)
#         pattern = r'(\d{3}-\d{3})'
#         match = re.search(pattern, sms)
#         if match:
#             code = match.group(1)
#         else:
#             code = ""
#         await asyncio.sleep(2)
#         await page.fill('input[name="phoneCode"]', code)
#         await asyncio.sleep(2)
#         await page.click('button[type="submit"]')
#         await asyncio.sleep(5)
#         await page.click('xpath=//*[@id="root"]/div/div[1]/div[2]/main/div/div/div/div[3]/div/span/a')
#         await asyncio.sleep(5)
#         cookies = await context.cookies()
#         cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
#         cookie_list = [cookie_dict]
#         element = await page.query_selector('body')
#         elem = await element.text_content()
#         if "В папке «Входящие» нет писем" in elem.strip():
#             while True:
#                 mail = ya_mail + '@yandex.ru'
#                 res = await send_acc(YANDEX_KIND_ID, phone_jd['phone'], password, first_name, last_name, user['birth_date'], humanoid_id,
#                                      cookie_list, mail)
#                 if res.status == 200:
#                     break
#             url = 'http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?'
#             await standart_request('post', url, data={'service': 'yandex'})
#         # await page.goto('https://id.yandex.ru/security/enter-methods')
#         # await page.click('div[data-testid="password-only-list-item"]')
#         await asyncio.sleep(3)
#         return AccountCreation(
#             kind_id=YANDEX_KIND_ID,
#             phone=phone_jd['phone'],
#             password=password,
#             humanoid_id=humanoid_id,
#             last_cookies=cookie_list
#         )
#     except Exception as e:
#         add_loggs(f'Ошибка:   {e}', 1)
#         return e


@APP.get("/@vk-register-new")
async def vk_register_new(count: Optional[int] = None):
    """регистрация одного или пачки учётных записей VKMail  """
    accounts = []
    count_acc = 0
    proxy_list = await standart_get_proxies(kind=5)
    logging.critical(proxy_list)
    proxy_index = 0
    if len(proxy_list) == 0:
        standart_finish('There Are No Proxies Found! Waiting 1000 Seconds Before Exit.')
    logging.critical(len(proxy_list))
    while count is None or len(accounts) < count:
        if len(accounts) == count:
            standart_finish('MISSION ACCOMPLISHED!')
        if proxy_index >= len(proxy_list):
            proxy_list = await standart_get_proxies(kind=5)
            proxy_index = 0
        pr = proxy_list[proxy_index].split('://')[1].split('@')
        username, password = pr[0].split(':')
        host, port = pr[1].split(':')
        if " " in host:
            host = host.replace(" ", "")
        proxy = {
            "server": f"http://{host}:{port}",
            "username": username,
            "password": password
        }

        logging.critical(proxy)
        async with async_playwright() as playwright:
            chromium = playwright.chromium
            browser = await chromium.launch(headless=False)
            context = await browser.new_context(proxy=proxy, java_script_enabled=True, is_mobile=True)
            page = await context.new_page()
            account = await vk_registeration_new(context, page)
            await browser.close()
            accounts.append(account)
        proxy_index += 1
        count_acc += 1
        logging.critical(count_acc)
    standart_finish('MISSION ACCOMPLISHED!')
    return {'accounts': accounts}


async def vk_registeration_new(context, page):
    humanoid = json.loads(await standart_request('get', 'https://accman.ad.dev.arbat.dev/get-innocent-humanoid?kind_id=2'))
    logging.critical(humanoid)
    day = humanoid['birth_date'].split('-')[2]
    month = humanoid['birth_date'].split('-')[1]
    year = humanoid['birth_date'].split('-')[0]
    logging.critical(f'{day}{month}{year}')
    phone_jd = json.loads(
        await standart_request('get', 'http://10.9.20.135:3000/phones/random?service=vk&bank=virtual'))
    password = generate_pass(15)

    try:
        await page.goto("https://vk.com/")
        await asyncio.sleep(10)

        element = await page.query_selector('body')
        elem = await element.text_content()
        if "Вход ВКонтакте" in elem.strip():
            await page.click('button[data-testid="signup"]')
            await random_delay(3, 5)
            await page.type('input[name="phone"]', phone_jd['phone'][1:], delay=random.uniform(0.1, 0.3))
            await random_delay(1, 3)
            await page.click('button[type="submit"]')
            await random_delay(3, 5)

            for r in range(15):
                url = f'http://10.9.20.135:3000/phones/messages/{phone_jd["phone"]}?fromTs=0{phone_jd["listenFromTimestamp"]}'
                sms = await standart_request('get', url)
                logging.critical(sms)

                try:
                    sms_data = json.loads(sms)
                except json.JSONDecodeError:
                    logging.error("Не удалось декодировать JSON из sms")
                    sms_data = {}

                if sms_data.get("messages"):
                    break

                await asyncio.sleep(1)

            if not sms_data.get("messages"):
                logging.critical("Смс не пришло")
                return "Смс не пришло"

            pattern = r"\d+"
            sms_text = json.dumps(sms_data)
            digits = re.findall(pattern, sms_text)
            sms_code = ' '.join(digits)

            await page.type('input[name="otp"]', sms_code, delay=random.uniform(0.1, 0.3))
            await asyncio.sleep(1)

            await page.click('button[type="submit"]')
            await asyncio.sleep(15)

            element = await page.query_selector('body')
            elem = await element.text_content()
            if "Отвязать номер от аккаунта?" in elem.strip():
                return 'Аккаунт уже есть'

            await page.type('input[name="first_name"]', humanoid['first_name'], delay=random.uniform(0.1, 0.3))
            await random_delay(1, 3)
            await page.type('input[name="last_name"]', humanoid['last_name'], delay=random.uniform(0.1, 0.3))
            await random_delay(1, 3)
            if humanoid['sex'] == 'female':
                await page.click('input[data-test-id="signup-sex-female"]', force=True)
            else:
                await page.click('input[data-test-id="signup-sex-male"]', force=True)

            await random_delay(2, 3)
            await page.click('span.vkuiDateInput__input')
            await random_delay(2, 3)

            await page.type('span.vkuiDateInput__input', str(day), delay=random.uniform(0.3, 0.6))
            await random_delay(2, 3)
            await page.type('span.vkuiDateInput__input', str(month), delay=random.uniform(0.3, 0.6))
            await random_delay(2, 3)
            await page.type('span.vkuiDateInput__input', str(year), delay=random.uniform(0.3, 0.6))
            await random_delay(2, 3)
            await page.click('button[form="signupForm"]')

            await random_delay(5, 10)
            await page.click('xpath=//*[@id="content"]/div[5]/a')
            await random_delay(2, 5)
            await page.click('xpath=//*[@id="content"]/div[5]/a')
            await random_delay(2, 5)
            await page.click('xpath=//*[@id="content"]/div[5]/a')
            await random_delay(2, 5)
            await page.click('xpath=//*[@id="react_rootJoinAvatar"]/div/section/div[4]/div/a')
            await random_delay(5, 10)

            await page.goto('https://id.vk.com/account/#/personal')
            await asyncio.sleep(10)

            id_value = await page.inner_text('.CopyId-id-u0mkt3 span')
            mid = re.findall(r'\d+', id_value)[0]
            await random_delay(1, 3)

            await page.goto('https://id.vk.com/account/#/otp-settings')
            await asyncio.sleep(10)

            await page.click('div[data-test-id="otp-cell-app"]')
            await random_delay(3, 6)
            await page.click('button[data-test-id="reset_sessions_modal_continue_button"]')
            await random_delay(5, 10)

            for r in range(15):
                url = 'http://10.9.20.135:3000/phones/messages/' + str(phone_jd['phone']) + '?fromTs=0' + str(phone_jd['listenFromTimestamp'])
                sms = await standart_request('get', url)
                if sms != '{"messages":[]}':
                    break
                await asyncio.sleep(1)
            pattern = r"\d+"
            sms = re.findall(pattern, sms)
            sms = ' '.join(sms)
            if sms == '{"messages":[]}':
                return 'Смс не пришло'
            try:
                for i, digit in enumerate(sms):
                    input_selector = f'input[data-test-id="cua_codebase_input_enter_code_{i}"]'
                    await page.fill(input_selector, digit)
            except Exception as e:
                logging.critical(e)
                pass
            await asyncio.sleep(5)
            await page.type('input[data-test-id="cua_set_password_input"]', password, delay=random.uniform(0.1, 0.3))
            await random_delay(3, 6)
            await page.type('input[data-test-id="cua_set_password_confirm_input"]', password, delay=random.uniform(0.1, 0.3))
            await random_delay(3, 6)
            await page.click('button[data-test-id="cua_set_password_button_submit"]')
            await random_delay(20, 60)
            rr = get_access_token(phone_jd['phone'], password)
            token = json.loads(rr.text)

            await page.goto('https://vk.com/feed')

            await random_delay(10, 20)
            element = await page.query_selector('body')
            elem = await element.text_content()
            if "Лента" in elem.strip():
                while True:
                    cookies = await context.cookies()
                    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                    cookie_list = [cookie_dict]
                    res = await send_acc_vk(phone_jd['phone'], password, mid, humanoid['first_name'], humanoid['last_name'], f'{day}.{month}.{year}', humanoid['id'], cookie_list, token['access_token'])
                    await asyncio.sleep(5)
                    if res.status == 200:
                        break

        return AccountCreation(
            kind_id=2,
            phone=phone_jd['phone'],
            password=password,
            info={
                "mid": mid,
                "first_name": humanoid['first_name'],
                "last_name": humanoid['last_name'],
                "birth_date": humanoid['birth_date'],
                "access_token": token['access_token']
            },
            humanoid_id=humanoid['id'],
            last_cookies=cookie_list
        )
    except Exception as e:
        return e


@APP.get("/@vk-register-mobile-new")
async def vk_register_mobile_new(count: Optional[int] = None):
    """регистрация одного или пачки учётных записей VK mobile  """
    accounts = []
    count_acc = 0
    proxy_list = await standart_get_proxies(kind=5)
    proxy_index = 0
    if len(proxy_list) == 0:
        standart_finish('There Are No Proxies Found! Waiting 1000 Seconds Before Exit.')
    while count is None or len(accounts) < count:
        if len(accounts) == count:
            standart_finish('MISSION ACCOMPLISHED!')
        if proxy_index >= len(proxy_list):
            proxy_list = await standart_get_proxies(kind=5)
            proxy_index = 0
        pr = proxy_list[proxy_index].split('://')[1].split('@')
        username, password = pr[0].split(':')
        host, port = pr[1].split(':')
        if " " in host:
            host = host.replace(" ", "")
        proxy = {
            "server": f"http://{host}:{port}",
            "username": username,
            "password": password
        }

        async with async_playwright() as playwright:
            iphone_13 = playwright.devices['iPhone 13']
            chromium = playwright.chromium
            browser = await chromium.launch(headless=True)
            context = await browser.new_context(**iphone_13, proxy=proxy)
            page = await context.new_page()
            account = await vk_registeration_mobile_new(context, page)
            await browser.close()
            accounts.append(account)
        proxy_index += 1
        count_acc += 1
        logging.critical(count_acc)
    standart_finish('MISSION ACCOMPLISHED!')
    return {'accounts': accounts}


async def vk_registeration_mobile_new(context, page):
    humanoid = json.loads(await standart_request('get', 'https://accman.ad.dev.arbat.dev/get-innocent-humanoid?kind_id=2'))
    day = humanoid['birth_date'].split('-')[2]
    month = humanoid['birth_date'].split('-')[1]
    year = humanoid['birth_date'].split('-')[0]
    phone_jd = json.loads(
        await standart_request('get', 'http://10.9.20.135:3000/phones/random?service=vk&bank=virtual'))
    password = generate_pass(15)
    try:
        await page.goto("https://vk.com/")
        await asyncio.sleep(10)
        await page.screenshot(path="screen.png", full_page=True)
        screen(id_user=74, message="vk_reg_page", id_screen=1)
        await page.click('xpath=/html/body/div[4]/div[2]/div[2]/div/div[3]/div[1]/div/div/div/div/div[1]/div/div/div[2]/div/div/div/div[1]/div/div[2]/div[2]/div/div[3]/div/button')
        await asyncio.sleep(2)
        await page.screenshot(path="screen.png", full_page=True)
        screen(id_user=74, message="vk_reg_vhod", id_screen=1)
        element = await page.query_selector('body')
        elem = await element.text_content()
        if "Вход ВКонтакте" in elem.strip():
            await page.click('button[data-test-id="registration_btn"]')
            await random_delay(3, 5)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_phone", id_screen=1)
            await page.type('input[name="phone"]', phone_jd['phone'][1:], delay=random.uniform(0.1, 0.3))
            await random_delay(1, 3)
            await page.click('button[type="submit"]')
            await random_delay(3, 5)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=1, message="vk_reg_sms", id_screen=1)

            for r in range(15):
                url = f'http://10.9.20.135:3000/phones/messages/{phone_jd["phone"]}?fromTs=0{phone_jd["listenFromTimestamp"]}'
                sms_raw = await standart_request('get', url)
                logging.critical(sms_raw)
                if sms_raw != '{"messages":[]}':
                    try:
                        sms_data = json.loads(sms_raw)
                        break
                    except json.JSONDecodeError:
                        return "Ошибка декодирования JSON"

            messages = sms_data.get("messages", [])
            if not messages:
                logging.critical("Смс не пришло")
                return "Смс не пришло"

            msg_text = messages[0]

            match = re.search(r"\b\d{4,8}\b", msg_text)
            if not match:
                return "Код не найден в СМС"

            otp_code = match.group()

            await page.type('input[name="otp"]', otp_code, delay=random.uniform(0.1, 0.3))
            await asyncio.sleep(1)

            await page.click('button[type="submit"]')
            await asyncio.sleep(15)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_cred", id_screen=1)

            element = await page.query_selector('body')
            elem = await element.text_content()
            logging.critical(elem)
            if "отвязать номер от аккаунта" in elem.lower():
                url = 'http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?'
                await standart_request('post', url, data={'service': 'vk'})
                return 'Аккаунт уже есть'

            await page.type('input[name="first_name"]', humanoid['first_name'], delay=random.uniform(0.1, 0.3))
            await random_delay(1, 3)
            await page.type('input[name="last_name"]', humanoid['last_name'], delay=random.uniform(0.1, 0.3))
            await random_delay(1, 3)
            if humanoid['sex'] == 'female':
                await page.click('input[data-test-id="signup-sex-female"]', force=True)
            else:
                await page.click('input[data-test-id="signup-sex-male"]', force=True)

            await random_delay(2, 3)
            await page.click('span.vkuiDateInput__input')
            await random_delay(2, 3)

            await page.type('span.vkuiDateInput__input', str(day), delay=random.uniform(0.3, 0.6))
            await random_delay(2, 3)
            await page.type('span.vkuiDateInput__input', str(month), delay=random.uniform(0.3, 0.6))
            await random_delay(2, 3)
            await page.type('span.vkuiDateInput__input', str(year), delay=random.uniform(0.3, 0.6))
            await random_delay(2, 3)
            await page.click('button[form="signupForm"]')
            await random_delay(5, 10)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_podtv", id_screen=1)
            await page.click('xpath=/html/body/div[4]/div[2]/div[2]/div/div[1]/a')
            await random_delay(2, 3)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_podtv", id_screen=1)
            await page.click('xpath=/html/body/div[4]/div[2]/div[2]/div/div[1]/a')
            await random_delay(2, 3)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_podtv", id_screen=1)
            await page.click('xpath=/html/body/div[4]/div[2]/div[2]/div/div[1]/a')
            await random_delay(2, 3)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_podtv", id_screen=1)
            await page.click('xpath=/html/body/div[4]/div[2]/div[2]/div/div[1]/a')
            await random_delay(2, 3)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_podtv", id_screen=1)
            await page.click('xpath=/html/body/div[4]/div[2]/div[2]/div/div[1]/a')
            await random_delay(2, 3)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_podtv", id_screen=1)
            await page.click('xpath=/html/body/div[4]/div[2]/div[2]/div/div[3]/div[1]/div/div/div/div/div/section/div/div/div/div/div/div[2]/div/div/div[3]/button')

            await page.goto('https://id.vk.com/account/#/personal')
            await asyncio.sleep(10)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_mid", id_screen=1)
            id_value = await page.inner_text('.CopyId-id-u0mkt3 span')
            mid = re.findall(r'\d+', id_value)[0]
            await random_delay(1, 3)

            await page.goto('https://id.vk.com/account/#/otp-settings')
            await asyncio.sleep(10)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_opt", id_screen=1)
            await page.click('div[data-test-id="otp-cell-app"]')
            await random_delay(3, 6)
            await page.click('button[data-test-id="reset_sessions_modal_continue_button"]')
            await random_delay(5, 10)
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_sms", id_screen=1)
            for r in range(15):
                url = 'http://10.9.20.135:3000/phones/messages/' + str(phone_jd['phone']) + '?fromTs=0' + str(phone_jd['listenFromTimestamp'])
                sms = await standart_request('get', url)
                logging.critical(sms)
                if sms != '{"messages":[]}':
                    break
                await asyncio.sleep(1)
            pattern = r"\d+"
            sms = re.findall(pattern, sms)
            sms = ' '.join(sms)
            if sms == '{"messages":[]}':
                return 'Смс не пришло'
            try:
                for i, digit in enumerate(sms):
                    input_selector = f'input[data-test-id="cua_codebase_input_enter_code_{i}"]'
                    await page.fill(input_selector, digit)
            except Exception as e:
                logging.critical(e)
                pass
            await page.screenshot(path="screen.png", full_page=True)
            screen(id_user=74, message="vk_reg_posle_sms", id_screen=1)

            await asyncio.sleep(5)
            await page.type('input[data-test-id="cua_set_password_input"]', password, delay=random.uniform(0.1, 0.3))
            await random_delay(3, 6)
            await page.type('input[data-test-id="cua_set_password_confirm_input"]', password, delay=random.uniform(0.1, 0.3))
            await random_delay(5, 7)
            await page.click('button[data-test-id="cua_set_password_button_submit"]')
            await random_delay(20, 60)
            rr = get_access_token(phone_jd['phone'], password)
            token = json.loads(rr.text)

            await page.goto('https://vk.com/feed')

            await random_delay(10, 20)
            element = await page.query_selector('body')
            elem = await element.text_content()
            if "Лента" in elem.strip():
                url = 'http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?'
                await standart_request('post', url, data={'service': 'vk'})
                while True:
                    cookies = await context.cookies()
                    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                    cookie_list = [cookie_dict]
                    res = await send_acc_vk(phone_jd['phone'], password, mid, humanoid['first_name'], humanoid['last_name'], f'{day}.{month}.{year}', humanoid['id'], cookie_list, token['access_token'])
                    await asyncio.sleep(5)
                    if res.status == 200:
                        break

        return AccountCreation(
            kind_id=2,
            phone=phone_jd['phone'],
            password=password,
            info={
                "mid": mid,
                "first_name": humanoid['first_name'],
                "last_name": humanoid['last_name'],
                "birth_date": humanoid['birth_date'],
                "access_token": token['access_token']
            },
            humanoid_id=humanoid['id'],
            last_cookies=cookie_list
        )
    except Exception as e:
        return e


@APP.get("/check-vk-api")
def check_vk_api():
    try:
        if CONTAINER_NAME == 'UniReger1':
            result = asyncio.run(vkapi.run(return_json=True))
            return JSONResponse(content=result)
        else:
            return 'не первый контейнер'
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


APP.mount("/", StaticFiles(directory="ui", html=True), name="ui")

if __name__ == "__main__":
    if CONTAINER_NAME == 'UniReger1':
        logging.critical("Скрипт запущен. Будет выполняться каждый день в 10:00 по Москве...")
        asyncio.run(vkapi.scheduler())
    uvicorn.run(APP, host="0.0.0.0", port=5000)
