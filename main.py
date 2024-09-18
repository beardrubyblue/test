import logging
import shutil
import re
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
from twocaptcha import TwoCaptcha
import psycopg
import configs
from models import AccountCreation
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
GMAIL_KIND_ID = 3
MAIL_KIND_ID = 19
VK_MAIL_RU = 35
YANDEX_KIND_ID = 50
RAMBLER_KIND_ID = 31
REGISTRATION_STARTED = False
random.seed()


def standart_finish(reason: str, timeout: int = 100000000):
    """Стандартная финализация работы контейнера."""
    logging.critical(reason)
    logging.critical('Finished At: ' + str(datetime.datetime.now()) + ' Waiting For: ' + str(timeout) + ' Seconds Before Exit.')
    time.sleep(timeout)
    exit(666)


async def standart_request(method: str, url: str, proxy_url: str = None, timeout: int = 60, params: dict = None, headers: dict = None, cookies: dict = None, data: dict = None, json: dict = None):
    """Стандартный запрос с возвратом текста его ответа."""
    pc = None
    if proxy_url:
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
    if json:
        request += ',json=json'
    async with aiohttp.ClientSession(connector=pc) as session:
        async with eval(f"session.{method}(url,timeout=timeout,params=params,headers=headers,cookies=cookies,data=data,json=json)") as resp:
            response = await resp.text(errors='replace')
            await session.close()
    return response


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
    # Получение бесплатных https прокси случайных стран с сайтов [https://free-proxy-list.net  или https://www.sslproxies.org].
    if kind == 1 and ptype == 3:
        async with aiohttp.ClientSession() as session:
            response = await session.get('https://www.sslproxies.org')
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
        jd = json.loads(requests.get('https://proxy-manager.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params).text)
        # jd = json.loads(asyncio.run(make_request('get', 'https://proxy-manager.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params)))
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


def vkr_auth(proxy_session, uuid, cookies, captcha_key='', captcha_sid='', captcha_ts='', captcha_attempt=''):
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


@app.get("/vk-revive-access-token")
def vk_revive_access_token(phone_string: str, password: str, credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """Воскрешение доступа к учётной записи ВК."""
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!', status_code=200)
    html = get_access_token(phone_string, password).content
    return HTMLResponse(content=html, status_code=200)


@app.get("/vk-execute-api-method")
def vk_execute_api_method(account_id: int = 51, api_method: str = 'https://api.vk.com/method/groups.getById', v: str = '5.154', ids: str = '1,2,3,4,5,6,7,8,9,10', offset: int = 0, credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """Выполнение API методов ВК."""
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!', status_code=200)
    at = asyncio.run(standart_execute_sql(f"select info->>'access_token' from accounts where id={account_id}"))
    html = 'Try Another Method please. A ha Ha ha ha HAAAA !!! :)'
    if api_method == 'https://api.vk.com/method/groups.getById':
        html = asyncio.run(standart_request('post', api_method, data={'group_ids': ids, 'access_token': at[0], 'v': v}))
    if api_method == 'https://api.vk.com/method/users.getSubscriptions':
        html = asyncio.run(standart_request('post', api_method, data={'user_id': int(ids), 'offset': offset, 'extended': True, 'count': 1, 'access_token': at[0], 'v': v}))
    return HTMLResponse(content=html, status_code=200)


@app.get("/vk-register")
def vk_register(kind='1', credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """регистрация одного или пачки учётных записей ВК"""
    global REGISTRATION_STARTED
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!', status_code=200)
    if REGISTRATION_STARTED:
        return HTMLResponse(content='ERROR! Only One Registration Process Allowed!', status_code=404)
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
                hrr = requests.get('https://accman.ad.dev.arbat.dev/get-innocent-humanoid?kind_id=7')
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
                        return HTMLResponse(content=html_response, status_code=200)
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
    return HTMLResponse(content=html_response, status_code=200)


@app.get("/rucaptcha-balance")
def rucaptcha_balance(credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """Проверка баланса рукапчи."""
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!', status_code=200)
    html = str(SOLVER.balance())
    return HTMLResponse(content=html, status_code=200)


@app.get("/")
def main():
    """Версия проекта."""
    return JSONResponse(content=json.loads(json.dumps({'project': 'UniReger', 'version': '30.05.2024 14:00'})), status_code=200)


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


async def send_acc(kind_id, phone_jd: str, password, first_name, last_name, birthday, humanoid_id, last_cookies, email):
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


@app.get("/gmail-register")
async def gmail_register(count: Optional[int] = None):
    """регистрация одного или пачки учётных записей GMail"""
    accounts = []
    count_acc = 0
    proxy_list = await standart_get_proxies(kind=2, ptype=3)
    proxy_index = 0
    if len(proxy_list) == 0:
        standart_finish('There Are No Proxies Found! Waiting 1000 Seconds Before Exit.')
    logging.critical(len(proxy_list))
    while count is None or len(accounts) < count:
        if proxy_index >= len(proxy_list):
            proxy_list = await standart_get_proxies(kind=2, ptype=3)
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

        add_loggs(f'proxy: {proxy}', 1)
        add_loggs(f'proxy: {pr}', 1)

        users = json.loads(
            await standart_request('get', f'https://accman.ad.dev.arbat.dev/get-innocent-humanoid?kind_id={GMAIL_KIND_ID}'))

        async with async_playwright() as playwright:
            chromium = playwright.firefox
            browser = await chromium.launch()
            context = await browser.new_context(proxy=proxy)
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

    # -----params-----
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

    # -----mining-----
    try:
        await page.goto('https://google.com')
        await asyncio.sleep(4)
        await page.click('xpath=/html/body/div[1]/div[1]/div/div/div/div/div[2]/a')
        await asyncio.sleep(4)
        await page.locator('xpath=//*[@id="yDmH0d"]/c-wiz/div/div[3]/div/div[2]/div/div/div[1]/div/button').click()
        await asyncio.sleep(2)
        await page.locator('xpath=//*[@id="yDmH0d"]/c-wiz/div/div[3]/div/div[2]/div/div/div[2]/div/ul/li[1]').click()
        await asyncio.sleep(2)

        # -----fullName-----
        await page.fill('#firstName', first_name)
        await asyncio.sleep(0.1)
        await page.fill('#lastName', last_name)
        await asyncio.sleep(0.1)
        add_loggs(f'name: {first_name}, {last_name}', 1)
        await page.click('.VfPpkd-LgbsSe')
        await page.wait_for_timeout(2000)

        # -----birthday-----
        await page.fill('#day', day)
        await asyncio.sleep(0.1)
        await page.select_option('#month', index=int(month))
        await asyncio.sleep(0.1)
        await page.fill('#year', year)
        await asyncio.sleep(0.1)
        add_loggs(f'date: {users["birth_date"]}', 1)

        # -----gender-----
        await page.select_option('#gender', index=gender)
        await asyncio.sleep(0.1)
        add_loggs(f'gender: {users["sex"]}', 1)
        await page.click('.VfPpkd-LgbsSe')
        await asyncio.sleep(4)

        # -----gmail-----
        element = await page.query_selector('body')
        elem = await element.text_content()
        if 'Создать собственный адрес Gmail' in elem.strip():
            await asyncio.sleep(1)
            await page.click(
                'xpath=/html/body/div[1]/div[1]/div[2]/c-wiz/div/div[2]/div/div/div/form/span/section/div/div/div[1]/div[1]/div/span/div[3]/div/div[1]/div/div[3]/div')
            await asyncio.sleep(2)
            await page.fill('input[name="Username"]', gmail)
            await asyncio.sleep(0.2)
            add_loggs(f'gmail: {gmail}', 1)
            await page.click('#next')
            await asyncio.sleep(4)
        else:
            await page.fill('input[name="Username"]', gmail, timeout=500)
            await asyncio.sleep(0.1)
            await page.click('#next', timeout=100)
            add_loggs(f'gmail: {gmail}', 1)

        # -----password-----
        await page.fill('input[name="Passwd"]', password)
        await asyncio.sleep(0.2)
        await page.fill('input[name="PasswdAgain"]', password)
        await asyncio.sleep(0.2)
        add_loggs(f'pass   {password}', 1)
        await page.click('.VfPpkd-LgbsSe')
        await asyncio.sleep(5)

        # -----phone-----
        element = await page.query_selector('body')
        elem = await element.text_content()
        if 'wants to access your Google Account' in elem.strip() or 'Не удалось создать аккаунт Google.' in elem.strip():
            add_loggs('Не удалось создать аккаунт Google.', 1)
            return {'Ошибка': 'Не удалось создать аккаунт Google.'}

        await page.fill('#phoneNumberId', phone_string, timeout=10000)
        await asyncio.sleep(0.2)
        add_loggs(f'phone: {phone_string}', 1)
        await page.click('.VfPpkd-LgbsSe')
        await asyncio.sleep(2)

        # -----sms-----
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

        await page.fill('#code', sms, timeout=3000)
        add_loggs(f'sms  {sms}', 1)
        await asyncio.sleep(0.2)
        await page.click('.VfPpkd-LgbsSe')
        await asyncio.sleep(3)

        # -----politic-----
        await page.click('xpath=/html/body/div[1]/div[1]/div[2]/div/div/div[3]/div/div[1]/div[2]/div/div/button')
        await asyncio.sleep(3)
        await page.click('.VfPpkd-LgbsSe')
        await asyncio.sleep(3)
        await page.click('xpath=/html/body/div[1]/div[1]/div[2]/c-wiz/div/div[3]/div/div[1]/div/div/button')
        await asyncio.sleep(3)

        cookies = await context.cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
        cookie_list = [cookie_dict]
        while True:
            gmail = f'{gmail}@gmail.ru'
            res = await send_acc(GMAIL_KIND_ID, phone_jd['phone'], password, first_name, last_name, f'{day}.{month}.{year}', humanoid_id,
                                 cookie_list, gmail)
            if res.status == 200:
                break
        add_loggs('Created', 1)
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


@app.get("/mailru-register")
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
            proxy_list = await standart_get_proxies(kind=2, ptype=3)
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
            context = await browser.new_context(proxy=proxy)
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

    # -----params-----
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
    password = generate_pass(random.randint(15, 20))
    phone_jd = json.loads(await standart_request('get', 'http://10.9.20.135:3000/phones/random?service=gmail&bank=virtual'))
    phone_string = '+' + phone_jd['phone'][0] + ' ' + phone_jd['phone'][1:4] + ' ' + phone_jd['phone'][4:7] + '-' + \
                   phone_jd['phone'][7:9] + '-' + phone_jd['phone'][9:11]
    try:
        await page.goto("https://account.mail.ru/signup")
        await asyncio.sleep(2)
        add_loggs('Start Registration', 1)

        element = await page.query_selector('body')
        elem = await element.text_content()
        if "Сгенерировать надёжный пароль" in elem.strip() or "Generate a strong password" in elem.strip():
            await page.wait_for_selector('.input-0-2-119', timeout=30000)
            elements = await page.query_selector_all('.input-0-2-119')
            try:
                await elements[0].fill(first_name, timeout=1000)
                await elements[1].fill(last_name, timeout=1000)

                await page.click('.daySelect-0-2-135', timeout=1000)
                await page.click(f'#react-select-2-option-{day - 1}', timeout=1000)
                await asyncio.sleep(1)
                await page.click('xpath=/html/body/div[1]/div[3]/div/div[4]/div[4]/div/div/div/div/form/div[6]/div[2]/div/div/div/div[3]', timeout=1000)
                await page.click(f'#react-select-3-option-{month - 1}', timeout=1000)
                await asyncio.sleep(1)
                await page.click('.yearSelect-0-2-136', timeout=1000)
                await page.click(f'[data-test-id="select-value:{year}"]', timeout=1000)

                if gender == 'male':
                    await page.click('input[value="male"]', force=True)
                else:
                    await page.click('input[value="female"]', force=True)
                await elements[2].fill(email, timeout=1000)
                await elements[3].fill(password, timeout=1000)
                await page.click('.passwordEye-0-2-126')
                await page.click('xpath=//*[@id="root"]/div/div[4]/div[4]/div/div/div/div/form/button')
                # -----captcha-----
                await page.locator('img.sHzh3T69FUE-dkHh1-lzl').screenshot(path='LastCaptcha.jpg')
                await asyncio.sleep(3)
                captcha = json.loads(requests.post("https://captcher.ad.dev.arbat.dev/solve_text_captcha_file",
                                                   params={'service': 'rucaptcha'},
                                                   files={'file': open('LastCaptcha.jpg', 'rb')}).text)
                element = await page.query_selector('body')
                elem = await element.text_content()
                if "Please enter code" in elem.strip():
                    await page.fill('input[placeholder="Code"]', captcha['solution'])
                else:
                    await page.fill('input[placeholder="Код"]', captcha['solution'])

                await page.click('button[type="submit"]')
                await asyncio.sleep(10)
                element = await page.query_selector('body')
                elem = await element.text_content()
                cookies = await context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                cookie_list = [cookie_dict]
                if "Добро пожаловать в Mail.ru!" in elem.strip():
                    add_loggs('Finish registration', 1)
                    while True:
                        email = f'{email}@mail.ru'
                        ids = str(standart_execute_sql("SELECT max(id) + 1 FROM accounts"))
                        pattern = r'\d+'
                        ids = re.findall(pattern, ids)
                        phone_jd = ' '.join(ids)
                        res = await send_acc(MAIL_KIND_ID, phone_jd, password, first_name, last_name,
                                             f'{day}.{month}.{year}', humanoid_id, cookie_list, email)
                        add_loggs('Created', 1)
                        if res.status == 200:
                            break
                elif "Укажите телефон" in elem.strip():
                    return {'Error': 'Registration with phone!!!!!!!!!!'}
                else:
                    return 'Error'
                return AccountCreation(
                    phone=phone_jd,
                    password=password,
                    humanoid_id=humanoid_id,
                    last_cookies=cookie_list
                )
            except Exception as e:
                return f"Ошибка при заполнении: {e}"
        else:
            add_loggs('Registration with phone', 1)
            await page.wait_for_selector('.input-0-2-119', timeout=30000)
            elements = await page.query_selector_all('.input-0-2-119')
            try:
                await elements[0].fill(first_name, timeout=1000)
                await elements[1].fill(last_name, timeout=1000)

                await page.click('.daySelect-0-2-135', timeout=1000)
                await page.click(f'#react-select-2-option-{day - 1}', timeout=1000)
                await asyncio.sleep(1)
                await page.click(
                    'xpath=/html/body/div[1]/div[3]/div/div[4]/div[4]/div/div/div/div/form/div[6]/div[2]/div/div/div/div[3]',
                    timeout=1000)
                await page.click(f'#react-select-3-option-{month - 1}', timeout=1000)
                await asyncio.sleep(1)
                await page.click('.yearSelect-0-2-136', timeout=1000)
                await page.click(f'[data-test-id="select-value:{year}"]', timeout=1000)

                if gender == 'male':
                    await page.click('input[value="male"]', force=True)
                else:
                    await page.click('input[value="female"]', force=True)
                await elements[2].fill(email, timeout=1000)
                await elements[3].fill(phone_string, timeout=1000)
                await page.click('xpath=//*[@id="root"]/div/div[4]/div[4]/div/div/div/div/form/button')
                element = await page.query_selector('body')
                elem = await element.text_content()
                if "Номер уже используется другим пользователем" in elem.strip():
                    return {'Error': 'this phone is already in use'}
                await asyncio.sleep(10)
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
                await page.fill('input', sms, timeout=1000)
                # await page.click('button[type="submit"]')
                await asyncio.sleep(10)
                phone = phone_jd['phone']
                element = await page.query_selector('body')
                elem = await element.text_content()
                if "This VK ID is linked to your phone number." in elem.strip() or "Забыли пароль?" in elem.strip():
                    vk_user = await standart_execute_sql(f"SELECT password FROM accounts WHERE phone = '{phone}'")
                    await page.fill('input', vk_user[0][0], timeout=1000)
                    await asyncio.sleep(1)
                else:
                    if user['sex'] == 'female':
                        await page.click('xpath=//*[@id="signupForm"]/div[1]/div[2]/div/label[2]')
                    await asyncio.sleep(1)
                    await page.click('button[type="submit"]')
                    await asyncio.sleep(10)

                    # -----finish-----
                    element = await page.query_selector('body')
                    elem = await element.text_content()
                cookies = await context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                cookie_list = [cookie_dict]
                if "Добро пожаловать в Mail.ru!" in elem.strip():
                    add_loggs('Finish registration', 1)
                    while True:
                        email = f'{email}@mail.ru'
                        password = ''
                        res = await send_acc(MAIL_KIND_ID, phone, password, first_name, last_name,
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
                return f"Ошибка при заполнении: {e}"
    except Exception as e:
        return e


@app.get("/@vk-mail-ru-register")
async def vk_mail_ru(count: Optional[int] = None):
    """регистрация одного или пачки учётных записей VKMail"""
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
            proxy_list = await standart_get_proxies(kind=2, ptype=3)
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
    # user_id = user[0]
    humanoid_id = user[7]
    phone = user[2]
    password = user[3]
    humanoid_first_name = user[4]['first_name']
    humanoid_last_name = user[4]['last_name']
    humanoid_birth_date = user[4]['birth_date']
    try:
        await page.goto("https://id.vk.com/")
        await asyncio.sleep(2)
        add_loggs('Start Registration', 1)
        await page.click('xpath=//*[@id="about_section"]/section/div[1]/div/div[1]/button')
        await asyncio.sleep(2)
        await page.fill('input', phone)
        await page.click('button[type="submit"]')
        await asyncio.sleep(1)
        element = await page.query_selector('body')
        elem = await element.text_content()
        if "Войти при помощи пароля" in elem.strip() or "Sign in using password" in elem.strip():
            await page.click('.vkc__Bottom__switchToPassword')
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
        else:
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
        await asyncio.sleep(10)

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
        await asyncio.sleep(5)
        await page.click('button[type="submit"]')

        await asyncio.sleep(10)
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


@app.get("/@ya-mail-ru-register")
async def ya_mail_ru(count: Optional[int] = None):
    """регистрация одного или пачки учётных записей YAmail"""
    accounts = []
    count_acc = 0
    proxy_list = await standart_get_proxies(kind=2)
    proxy_index = 0
    if len(proxy_list) == 0:
        standart_finish('There Are No Proxies Found! Waiting 1000 Seconds Before Exit.')
    logging.critical(len(proxy_list))
    while count is None or len(accounts) < count:
        if proxy_index >= len(proxy_list):
            proxy_list = await standart_get_proxies(kind=2, ptype=3)
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
            await standart_request('get', f'https://accman-odata.arbat.dev/get-innocent-humanoid?kind_id={YANDEX_KIND_ID}'))
        async with async_playwright() as playwright:
            chromium = playwright.chromium
            browser = await chromium.launch()
            context = await browser.new_context(proxy=proxy)
            page = await context.new_page()
            account = await ya_mail_ru_registration(context, page, user)
            logging.critical(account)
            await browser.close()
            add_loggs(f'Ответ: {account}', 1)
            accounts.append(account)
            add_loggs('------------------------------------', 1)

        proxy_index += 1
        count_acc += 1
        logging.critical(count_acc)
    return {'accounts': accounts}


async def ya_mail_ru_registration(context, page, user):
    # -----params-----
    humanoid_id = user['id']
    first_name = user['first_name']
    last_name = user['last_name']
    year = user['birth_date'].split('-')[0]
    password = generate_pass(random.randint(15, 20))
    ya_mail = generate_mail(first_name, last_name, year)
    phone_jd = json.loads(await standart_request('get', 'http://10.9.20.135:3000/phones/random?service=gmail&bank=virtual'))
    phone_string = phone_jd['phone'][1:4] + ' ' + phone_jd['phone'][4:7] + '-' + phone_jd['phone'][7:9] + '-' + phone_jd['phone'][9:11]
    try:
        await page.goto("https://passport.yandex.ru/registration/mail?from=mail&require_hint=1&origin=hostroot_homer_reg_ru&retpath=https%3A%2F%2Fmail.yandex.ru&backpath=https%3A%2F%2Fmail.yandex.ru%3Fnoretpath%3D1")
        await asyncio.sleep(2)
        add_loggs('Start Registration', 1)
        await page.fill('input[name="firstname"]', first_name)
        await page.fill('input[name="lastname"]', last_name)
        await page.fill('input[name="login"]', ya_mail)
        await page.fill('input[name="password"]', password)
        await page.fill('input[name="password_confirm"]', password)
        await page.fill('input[name="phone"]', phone_string)
        await asyncio.sleep(2)
        await page.click('button[type="submit"]')
        await asyncio.sleep(2)
        for r in range(30):
            url = 'http://10.9.20.135:3000/phones/messages/' + phone_jd['phone'] + '?fromTs=0' + str(
                phone_jd['listenFromTimestamp'])
            sms = await standart_request('get', url)
            if sms != '{"messages":[]}':
                break
            await asyncio.sleep(0.2)
        pattern = r'(\d{3}-\d{3})'
        match = re.search(pattern, sms)
        if match:
            code = match.group(1)
        else:
            code = ""
        await asyncio.sleep(2)
        await page.fill('input[name="phoneCode"]', code)
        await asyncio.sleep(2)
        await page.click('button[type="submit"]')
        await asyncio.sleep(5)
        await page.click('xpath=//*[@id="root"]/div/div[1]/div[2]/main/div/div/div/div[3]/div/span/a')
        await asyncio.sleep(5)
        cookies = await context.cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
        cookie_list = [cookie_dict]
        element = await page.query_selector('body')
        elem = await element.text_content()
        if "В папке «Входящие» нет писем" in elem.strip():
            while True:
                mail = ya_mail + '@yandex.ru'
                res = await send_acc(YANDEX_KIND_ID, phone_jd['phone'], password, first_name, last_name, user['birth_date'], humanoid_id,
                                     cookie_list, mail)
                if res.status == 200:
                    break
            url = 'http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?'
            await standart_request('post', url, data={'service': 'yandex'})
        # await page.goto('https://id.yandex.ru/security/enter-methods')
        # await page.click('div[data-testid="password-only-list-item"]')
        await asyncio.sleep(3)
        return AccountCreation(
            kind_id=YANDEX_KIND_ID,
            phone=phone_jd['phone'],
            password=password,
            humanoid_id=humanoid_id,
            last_cookies=cookie_list
        )
    except Exception as e:
        add_loggs(f'Ошибка:   {e}', 1)
        return e


@app.get("/@rambler-mail-ru-register")
async def rambler_mail_ru(count: Optional[int] = None):
    """регистрация одного или пачки учётных записей YAmail"""
    accounts = []
    count_acc = 0
    proxy_list = await standart_get_proxies(kind=2)
    proxy_index = 0
    if len(proxy_list) == 0:
        standart_finish('There Are No Proxies Found! Waiting 1000 Seconds Before Exit.')
    logging.critical(len(proxy_list))

    path_to_extension = "./Captcha-Solver-Chrome"
    user_data_dir = "./tmp/test-user-data-dir"

    while count is None or len(accounts) < count:
        if proxy_index >= len(proxy_list):
            proxy_list = await standart_get_proxies(kind=2, ptype=3)
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
            await standart_request('get', f'https://accman.ad.dev.arbat.dev/get-innocent-humanoid?kind_id={RAMBLER_KIND_ID}'))

        async with async_playwright() as playwright:
            chromium = playwright.chromium
            context = await chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                args=[
                    f"--disable-extensions-except={path_to_extension}",
                    f"--load-extension={path_to_extension}",
                ],
                http_credentials={"username": username, "password": password},
                proxy=proxy
            )
            page = await context.new_page()
            account = await rambler_mail_ru_registration(context, page, user)
            logging.critical(account)
            await context.close()
            shutil.rmtree(user_data_dir)
            add_loggs(f'Ответ: {account}', 1)
            accounts.append(account)
            add_loggs('------------------------------------', 1)

        proxy_index += 1
        count_acc += 1
        logging.critical(count_acc)
    return {'accounts': accounts}


async def rambler_mail_ru_registration(context, page, user):
    # -----params-----
    humanoid_id = user['id']
    first_name = user['first_name']
    last_name = user['last_name']
    day = int(user['birth_date'].split('-')[2])
    month = int(user['birth_date'].split('-')[1])
    year = user['birth_date'].split('-')[0]
    if user['sex'] == 'female':
        gender = 2
    else:
        gender = 1
    password = generate_pass(random.randint(15, 20))
    rambler_mail = generate_mail(first_name, last_name, year)
    phone_jd = json.loads(await standart_request('get', 'http://10.9.20.135:3000/phones/random?service=gmail&bank=virtual'))
    phone_string = phone_jd['phone'][1:11]
    try:
        await page.goto('chrome://extensions/')
        await page.goto('https://2captcha.com/res.php?action=userinfo&key=b7daa375616afc09a250286108ea037d&header_acao=1&json=1')
        page.on("dialog", lambda dialog: dialog.accept(prompt_text="your_username:your_password"))
        await page.goto(
            'chrome-extension://ngnebjnkjhkljjjhhhpjljfiipoggnbh/options/options.html')
        await asyncio.sleep(2)
        await page.fill('input[name="apiKey"]', 'b7daa375616afc09a250286108ea037d')
        await asyncio.sleep(1)
        for i in range(1):
            await page.click('button[id="connect"]')
            await asyncio.sleep(0.5)
        await asyncio.sleep(3)

        await page.goto("https://id.rambler.ru/login-20/mail-registration")
        await page.wait_for_selector('.rui-Input-input', timeout=30000)
        elements = await page.query_selector_all('.rui-Input-input')
        await elements[0].fill(rambler_mail)
        await elements[2].fill(password)
        await elements[3].fill(password)
        await elements[5].fill(phone_string)
        add_loggs('Start Registration', 1)
        await page.click('xpath=//*[@id="__next"]/div/div/div/div/div/div/div[1]/form/div/div/div[2]/button')
        await asyncio.sleep(5)
        await page.click('.captcha-solver')
        await asyncio.sleep(30)
        await page.click('xpath=//*[@id="__next"]/div/div/div/div/div/div/div[1]/form/div/div/div[2]/button')
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
        await page.fill('#sms', sms, timeout=1000)
        await page.click('xpath=//*[@id="__next"]/div/div/div/div/div/div/div[1]/form/button')
        await asyncio.sleep(5)
        await page.click('xpath=/html/body/div/div/div/div/footer/div/a')
        await asyncio.sleep(10)
        await page.click('xpath=/html/body/div[3]/div/div/button')

        await page.click('xpath=//*[@id="root"]/div/div[2]/div/div/section[2]/div[2]/section[1]/div/h5/button')
        await asyncio.sleep(1)
        await page.fill('input[id="firstname"]', first_name)
        await asyncio.sleep(1)
        await page.fill('input[id="lastname"]', last_name)
        await asyncio.sleep(1)
        await page.click('xpath=//*[@id="root"]/div/div[2]/div/div/section[2]/div[2]/form/span[1]/button')
        await asyncio.sleep(1)
        await page.click('xpath=//*[@id="root"]/div/div[2]/div/div/section[2]/div[2]/section[2]/div/span/button')
        await asyncio.sleep(1)
        await page.click('#birthday')
        await asyncio.sleep(1)
        await page.click(f'xpath=/html/body/div[1]/div/div[2]/div/div/section[2]/div[2]/form/section/div/div/div/div[1]/div/div[2]/div/div/div[1]/div/div/div[{day + 1}]')
        await asyncio.sleep(1)
        await page.click('xpath=//*[@id="root"]/div/div[2]/div/div/section[2]/div[2]/form/section/div/div/div/div[2]/div/div[1]/div/input')
        await asyncio.sleep(1)

        await page.click(f'xpath=/html/body/div[1]/div/div[2]/div/div/section[2]/div[2]/form/section/div/div/div/div[2]/div/div[2]/div/div/div[1]/div/div/div[{month + 1}]')
        await asyncio.sleep(1)
        await page.click(
            'xpath=//*[@id="root"]/div/div[2]/div/div/section[2]/div[2]/form/section/div/div/div/div[3]/div/div/div/input')
        await asyncio.sleep(1)
        await page.locator('div.rui-Select-menuItem', has_text=f'{year}').click()
        await asyncio.sleep(1)
        await page.click('xpath=//*[@id="root"]/div/div[2]/div/div/section[2]/div[2]/form/span[1]/button')
        await asyncio.sleep(1)
        await page.click('xpath=//*[@id="root"]/div/div[2]/div/div/section[2]/div[2]/section[3]/div/span/button')
        await asyncio.sleep(1)
        await page.click('xpath=//*[@id="gender"]')
        await asyncio.sleep(1)
        await page.click(f'xpath=//*[@id="root"]/div/div[2]/div/div/section[2]/div[2]/form/section/div/div/div/div/div/div[2]/div/div/div[1]/div/div/div[{gender + 1}]')
        await asyncio.sleep(1)
        await page.click('xpath=//*[@id="root"]/div/div[2]/div/div/section[2]/div[2]/form/span[1]/button')
        await asyncio.sleep(1)
        cookies = await context.cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
        cookie_list = [cookie_dict]
        while True:
            email = f'{rambler_mail}@rambler.ru'
            res = await send_acc(RAMBLER_KIND_ID, phone_jd['phone'], password, first_name, last_name,
                                 f'{day}.{month}.{year}', humanoid_id, cookie_list, email)
            add_loggs('Created', 1)
            if res.status == 200:
                break
        return AccountCreation(
            kind_id=RAMBLER_KIND_ID,
            phone=phone_jd['phone'],
            password=password,
            humanoid_id=humanoid_id,
            last_cookies=cookie_list
        )
    except Exception as e:
        add_loggs(f'Ошибка:   {e}', 1)
        return e

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
