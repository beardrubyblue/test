import logging
import configs
import datetime
from typing import Dict
import requests
# import asyncio
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
KIND_ID = 3
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
        jd = json.loads(requests.get('https://proxy-manager.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params).text)
        # jd = json.loads(asyncio.run(make_request('get', 'https://proxy-manager.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params)))
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
    rr = requests.post('https://accman-odata.arbat.dev/create', headers=headers, json=json_data)
    # rr = asyncio.run(make_request('post', 'https://accman-odata.arbat.dev/create', headers=headers, params=json_data))
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


@app.get("/revive-vk-access-token")
def revive_vk_access_token(phone_string: str, password: str, credentials: HTTPBasicCredentials = Depends(SECURITY)):
    """Воскрешение доступа к учётной записи ВК."""
    if credentials.username != 'AlanD' or credentials.password != 'Bober666':
        return HTMLResponse(content='В доступе отказано!', status_code=200)
    html = get_access_token(phone_string, password).content
    return HTMLResponse(content=html, status_code=200)


@app.get("/register")
def register(kind='1', credentials: HTTPBasicCredentials = Depends(SECURITY)):
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
            # logging.critical(phone_jd)
            phone_string = '+' + phone_jd['phone'][0] + ' ' + phone_jd['phone'][1:4] + ' ' + phone_jd['phone'][4:7] + '-' + phone_jd['phone'][7:9] + '-' + phone_jd['phone'][9:11]
            html_response += '<BR>Phone: ' + phone_string
            cookies = {}
            uuid = js_userandom_string(21)
            device_id = js_userandom_string(21)
            try:
                rr = vkr_auth(proxy_session, uuid, cookies)
                cookies = rr.cookies
                soup = BeautifulSoup(rr.text, 'lxml')
                s1 = soup.head.findAll('script')[1].text
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
                sid = jd['sid']
                logging.critical('SID: ' + login_sid)
                password = js_userandom_string(21)
                first_name = random.choice(Names).split(' ')[0]
                last_name = random.choice(Names).split(' ')[1]
                birthday = str(random.randint(10, 28)) + '.0' + str(random.randint(1, 9)) + '.' + str(random.randint(1980, 2004))
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
                    info = json.dumps({'access_token': access_token, 'MID': str(jd['mid']), 'CreationTime': str(datetime.datetime.now()), 'Proxy': proxy, 'UUID': uuid, "DeviceID": device_id, 'AuthToken': access_token, 'SID': sid, 'FirstName': first_name, 'LastName': last_name, 'Birthday': birthday}, ensure_ascii=False)
                    save_account(phone_jd['phone'], password, info)
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


@app.get("/reg_acc")
async def reg_acc():
    users = await make_request('get', f'https://accman-odata.arbat.dev/get-innocent-humanoid?kind_id={KIND_ID}')
    users = json.loads(users)
    proxy_list = await create_proxy_list()
    if len(proxy_list) == 0:
        finish('There Are No Proxies Found! Waiting 1000 Seconds Before Exit.')
    logging.critical(len(proxy_list))
    pr = proxy_list[1]
    user_agent = UserAgent()
    user_agent = user_agent.random
    proxy = {
        'server': f'http://{pr["host"]}:{str(pr["port"])}',
        "username": pr['login'],
        "password": pr['password']
    }
    logging.critical(proxy)
    async with async_playwright() as playwright:
        chromium = playwright.firefox
        browser = await chromium.launch(headless=False)
        context = await browser.new_context(user_agent=user_agent, proxy=proxy)
        page = await context.new_page()
        response = await mine(context, page, users, pr)
        await browser.close()
        logging.critical(response)
    return response


async def create_proxy_list(kind: int = 5, ptype: str = 3, country: str = 'RU', max_amount: int = 10000):
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


async def make_request(method: str, url: str, params: Dict = None, headers: Dict = None, cookies: Dict = None,
                       timeout: int = 60):
    async with aiohttp.ClientSession() as session:
        if method == 'get':
            async with session.get(url, params=params, headers=headers, cookies=cookies, timeout=timeout) as resp:
                response = await resp.text(errors='replace')
        if method == 'put':
            async with session.put(url, params=params, headers=headers, cookies=cookies, timeout=timeout) as resp:
                response = await resp.text(errors='replace')
    return response


def finish(reason: str, timeout: int = 100000000):
    logging.critical(reason)
    logging.critical(
        'Finished At: ' + str(datetime.datetime.now()) + ' Waiting For: ' + str(timeout) + ' Seconds Before Exit.')
    time.sleep(timeout)
    exit(666)


async def get_sms(phone_jd):
    url = 'http://10.9.20.135:3000/phones/messages/' + str(phone_jd['phone']) + '?fromTs=0' + str(
        phone_jd['listenFromTimestamp'])
    response = await make_request('get', url)
    logging.critical(response)
    return response


def generate_gmail(first_name, last_name, year):
    first_name = translit(first_name, 'ru', reversed=True)
    last_name = translit(last_name, 'ru', reversed=True)
    gmail = f'{first_name.lower()}.{last_name.lower()}{year + str(random.randint(1, 999))}'
    gmail = gmail.replace('`', '')
    return gmail


def generate_pass(length):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(length))
    return password


async def send_acc(phone_jd, password, proxy, first_name, last_name, birthday, humanoid_id, last_cookies):
    proxy = proxy['host'] + ':' + str(proxy['port']) + '|' + proxy['country_code'] + ' ' + proxy['id']
    data = {
        'kind_id': KIND_ID,
        'phone': phone_jd['phone'],
        'password': password,
        'info': {
            'Proxy': proxy,
            'FieldName': first_name,
            'Surname': last_name,
            'Birthday': birthday
        },
        "humanoid_id": humanoid_id,
        "last_cookies": last_cookies
    }
    async with aiohttp.ClientSession() as session:
        async with session.post('https://accman-odata.arbat.dev/create', json=data) as response:
            rr = await response.text()
            logging.critical(rr)
            return rr


async def mine(context, page, users, proxy):
    humanoid_id = users['id']
    first_name = users['first_name']

    last_name = users['last_name']

    phone_jd = await make_request('get', 'http://10.9.20.135:3000/phones/random?service=gmail&bank=virtual')
    phone_jd = json.loads(phone_jd)
    phone_string = '+' + phone_jd['phone'][0] + ' ' + phone_jd['phone'][1:4] + ' ' + phone_jd['phone'][4:7] + '-' + \
                   phone_jd['phone'][7:9] + '-' + phone_jd['phone'][9:11]

    day = str(users['birth_date'].split('-')[2])
    month = int(users['birth_date'].split('-')[1])
    year = str(users['birth_date'].split('-')[0])

    if users['sex'] == 'female':
        sex = 1
    else:
        sex = 2

    gmail = generate_gmail(first_name, last_name, year)

    password = generate_pass(random.randint(10, 15))

    await page.goto('https://google.com/')
    await page.click('.gb_Ca')
    await page.wait_for_timeout(2000)
    await page.locator('xpath=//*[@id="yDmH0d"]/c-wiz/div/div[3]/div/div[2]/div/div/div[1]/div/button').click()
    await page.wait_for_timeout(200)
    await page.locator('xpath=//*[@id="yDmH0d"]/c-wiz/div/div[3]/div/div[2]/div/div/div[2]/div/ul/li[1]').click()
    await page.wait_for_timeout(200)
    add_loggs('name', 1)
    await page.fill('#firstName', first_name)
    await page.wait_for_timeout(200)
    await page.fill('#lastName', last_name)
    await page.wait_for_timeout(200)
    await page.click('.VfPpkd-LgbsSe')
    await page.wait_for_timeout(200)
    add_loggs('date', 1)
    await page.fill('#day', day)
    await page.wait_for_timeout(200)
    await page.select_option('#month', index=month)
    await page.wait_for_timeout(200)
    await page.fill('#year', year)
    await page.wait_for_timeout(200)
    await page.select_option('#gender', index=sex)
    await page.wait_for_timeout(200)
    await page.click('.VfPpkd-LgbsSe')
    await page.wait_for_timeout(4000)
    add_loggs('gmail', 1)
    try:
        await page.fill('input[name="Username"]', gmail, timeout=500)
        await page.wait_for_timeout(200)
        await page.click('#next', timeout=100)
    except PlaywrightTimeoutError as e:
        await asyncio.sleep(1)
        logging.critical(e)
        await page.click(
            'xpath=/html/body/div[1]/div[1]/div[2]/c-wiz/div/div[2]/div/div/div/form/span/section/div/div/div[1]/div[1]/div/span/div[3]/div/div[1]/div/div[3]/div')
        await page.wait_for_timeout(200)
        await page.fill('input[name="Username"]', gmail)
        await page.wait_for_timeout(200)
        await page.click('#next')
    add_loggs('pass', 1)
    await page.wait_for_timeout(2000)
    await page.fill('input[name="Passwd"]', password)
    await page.wait_for_timeout(200)
    await page.fill('input[name="PasswdAgain"]', password)
    await page.wait_for_timeout(200)
    await page.click('.VfPpkd-LgbsSe')
    await page.wait_for_timeout(5000)
    add_loggs('phone', 1)
    try:
        await page.fill('#phoneNumberId', phone_string, timeout=10000)
        await page.wait_for_timeout(200)
        await page.click('.VfPpkd-LgbsSe')
        await page.wait_for_timeout(200)
    except PlaywrightTimeoutError as e:
        logging.critical(e)
        return 0
    for r in range(150):
        sms = await get_sms(phone_jd)
        logging.critical(sms)
        if sms != '{"messages":[]}':
            break
        await asyncio.sleep(0.2)
    pattern = r'\d+'
    sms = re.findall(pattern, sms)
    sms = ' '.join(sms)
    logging.critical(sms)

    await page.wait_for_timeout(3000)
    await page.fill('#code', sms)
    await page.wait_for_timeout(3000)
    await page.click('.VfPpkd-LgbsSe')
    await page.wait_for_timeout(3000)
    await page.click('xpath=/html/body/div[1]/div[1]/div[2]/div/div/div[3]/div/div[1]/div[2]/div/div/button')
    await page.wait_for_timeout(5000)
    await page.click('.VfPpkd-LgbsSe')
    await page.wait_for_timeout(5000)
    await page.click('xpath=/html/body/div[1]/div[1]/div[2]/c-wiz/div/div[3]/div/div[1]/div/div/button')
    await page.wait_for_timeout(10000)
    cookies = await context.cookies()
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
    await page.screenshot(path="screenshot.png")
    birthday = users["birth_date"]
    acc = str(phone_jd) + ' ' + password + ' ' + proxy + first_name + last_name + str(birthday) + str(humanoid_id)
    add_loggs(acc, 1)
    response = await send_acc(phone_jd, password, proxy, first_name, last_name, birthday, humanoid_id, cookie_dict)
    url = 'http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?'
    data = {'service': 'gmail'}
    claim = await make_request('get', url, params=data)
    logging.critical(claim)
    return response

def add_loggs(message, id_log):
    DBC.execute('INSERT INTO "Testing".logs(log, id_log) VALUES (%s, %s)', (message, id_log))
    DB.commit()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
