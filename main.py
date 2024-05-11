import logging
import configs
import datetime
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
from playwright.sync_api import sync_playwright
import psycopg
logging.basicConfig(level=logging.CRITICAL, format="%(message)s")
DB = psycopg.connect(**configs.db_config())
DBC = DB.cursor()
app = FastAPI()
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
PROXYKIND = 1
with open('Names.txt', 'r') as F:
    Names = F.readlines()
    F.close()
with open('UserAgents.txt', 'r') as F:
    UserAgents = F.readlines()
    F.close()
STATISTICS = []
REGISTRATION_STARTED = False
random.seed()


def get_proxies(kind: int, amount: int = 1000):
    """функция возвращает список полученных проксей с сайта https://free-proxy-list.net или из https://proxy-manager.arbat.dev/"""
    proxies = []
    if kind == 1:
        soup = BeautifulSoup(requests.get('https://www.sslproxies.org').content, 'html.parser')
        for row in soup.find('table', attrs={'class': 'table table-striped table-bordered'}).find_all('tr')[1:]:
            tds = row.find_all('td')
            if tds[2].text.strip() != 'RU' and tds[6].text.strip() == 'yes':
                proxies.append(f'{tds[0].text.strip()}:{tds[1].text.strip()}|{tds[2].text.strip()} 0')
    if kind == 2:
        params = {'limit': amount, 'offset': '0', 'sla': '0.7', "proxy_type": 2}
        jd = json.loads(requests.get('https://proxy-manager.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params).text)
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


def save_account(phone_jd, password, info):
    """Отправка нового пользователя в БД"""
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
    }
    json_data = {
        "id": 451,
        "kind_id": 2,
        "phone": phone_jd,
        "password": password,
        "info": info,
        "last_rent_time": "2023-10-09 20:14:40.70"
    }
    return requests.post('https://accman-dev.tgbank.dev/add', headers=headers, json=json_data)


async def get_access_token(phone_string: str, password: str):
    """запрос к https://oauth.vk.com/token возвращает access_token"""
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


@app.get("/work-supremacy")
def supremacy():

    for i in range(0, 25):
        with sync_playwright() as p:
            DBC.execute('SELECT phone, passw, id_last, proxi FROM "Elizaveta".news_ids')
            result = DBC.fetchall()
            phone = result[i][0]
            password = result[i][1]
            if result[i][2] is None:
                id = 1
            else:
                id = result[i][2] + 1
            proxi = result[i][3]

            logging.critical(f"Login {phone}")
            logging.critical(f"Passw {password}")
            logging.critical(f"id {id}")

            server = proxi[0]
            username = proxi[1]
            passw = proxi[2]
            logging.critical(f"proxi {server, username, passw}")

            browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"], proxy={'server': server, 'username': username, 'password': passw})
            context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0')
            page = context.new_page()
            logging.critical("Browser is open!")

            page.goto(f"https://supremacy.info/news/{id}")
            logging.critical("Went to the site to login")
            page.click('#plusButton')
            logging.critical("Let's start authorization")
            page.wait_for_timeout(2000)
            page.click('#authButton')
            page.fill('input[name="identifier"]', phone)
            logging.critical("Login entered")

            page.screenshot(path="screenshot0.png", full_page=True)
            with open("screenshot0.png", "rb") as f:
                image_data = f.read()
            DBC.execute('INSERT INTO "Elizaveta".screenshot(photo, name) VALUES (%s, %s)', (image_data, "identifierNext"))
            DB.commit()

            page.click('#identifierNext')
            logging.critical("Next")
            page.fill('input[name="Passwd"]', password)

            page.screenshot(path="screenshot1.png", full_page=True)
            with open("screenshot1.png", "rb") as f:
                image_data = f.read()
            DBC.execute('INSERT INTO "Elizaveta".screenshot(photo, name) VALUES (%s, %s)', (image_data, "passwordNext"))
            DB.commit()

            page.click('#passwordNext')
            logging.critical("Next")
            page.wait_for_timeout(2000)

            client = page.context.new_cdp_session(page)
            mhtml = client.send("Page.captureSnapshot")['data']
            with open('example.mhtml', mode='w', encoding='UTF-8', newline='\n') as f:
                f.write(mhtml)
            with open('example.mhtml', 'r') as f:
                html_kod = f.read()

            page.screenshot(path="screenshot2.png", full_page=True)
            with open("screenshot2.png", "rb") as f:
                image_data = f.read()

            DBC.execute('INSERT INTO "Elizaveta".screenshot(photo, name, html) VALUES (%s, %s, %s)', (image_data, "After passw", html_kod))
            DB.commit()

            element = page.query_selector('body')
            if "This browser or app may not be secure. Learn more" in element.text_content().strip():
                time.sleep(60)
                page.wait_for_timeout(2000)
                logging.critical("Next1")
                page.click('button[name="action"]')  # ?????????????????????

            elif "Choose how you want to sign in:" in element.text_content().strip():
                page.wait_for_timeout(2000)
                logging.critical("Next2")
                page.click('button[value="5,SMS"]')

            elif "Your recovery phone recently changed" in element.text_content().strip():
                page.wait_for_timeout(2000)
                logging.critical("Next3")
                page.click('button[name="action"]')

            elif "Выберите способ входа:" in element.text_content().strip():
                page.wait_for_timeout(2000)
                logging.critical("Next4")
                page.click('button[value="5,SMS"]')

            elif "Подтвердите свою личность" in element.text_content().strip():
                page.wait_for_timeout(2000)
                logging.critical("Next5")
                page.click('button[name="action"]')

            elif "Verify it’s you" in element.text_content().strip():
                page.wait_for_timeout(2000)
                logging.critical("Next6")
                page.click('button[class="JnOM6e TrZEUc rDisVe"]')

            page.wait_for_timeout(2000)

            time.sleep(30)

            page.screenshot(path="screenshot3.png", full_page=True)
            with open("screenshot3.png", "rb") as f:
                image_data = f.read()
            DBC.execute('INSERT INTO "Elizaveta".screenshot(photo, name) VALUES (%s, %s)', (image_data, "Kod"))
            DB.commit()

            response = requests.get(f'http://10.9.20.135:3000/phones/messages/{phone}?fromTs=0').json()
            if 'G-' in response['messages'][0]:
                kod = response['messages'][0][2:8]

            page.fill('input[name="Pin"]', kod)
            logging.critical("Kod entered")

            page.screenshot(path="screenshot4.png", full_page=True)
            with open("screenshot4.png", "rb") as f:
                image_data = f.read()
            DBC.execute('INSERT INTO "Elizaveta".screenshot(photo, name) VALUES (%s, %s)', (image_data, "Kod entered"))
            DB.commit()

            element = page.query_selector('body')
            if 'Вход в сервис "supremacy.info"' in element.text_content().strip():
                page.click('button[class="VfPpkd-LgbsSe VfPpkd-LgbsSe-OWXEXe-INsAgc VfPpkd-LgbsSe-OWXEXe-dgl2Hf Rj2Mlf OLiIxf PDpWxe P62QJc LQeN7 BqKGqe pIzcPc TrZEUc lw1w4b"]')
                logging.critical("Next")
            else:
                page.click('#idvPreregisteredPhoneNext')
                logging.critical("Next")

            page.wait_for_timeout(2000)
            client = page.context.new_cdp_session(page)
            html = client.send("Page.captureSnapshot")['data']
            with open('example1.mhtml', mode='w', encoding='UTF-8', newline='\n') as f:
                f.write(html)
            with open('example1.mhtml', 'r') as f:
                html_kod = f.read()

            page.wait_for_timeout(2000)
            page.screenshot(path="screenshot5.png", full_page=True)
            with open("screenshot5.png", "rb") as f:
                image_data = f.read()
            DBC.execute('INSERT INTO "Elizaveta".screenshot(photo, name, html) VALUES (%s, %s, %s)', (image_data, "After kod", html_kod))
            DB.commit()

            element = page.query_selector('body')
            if 'wants to access your Google Account' in element.text_content().strip():
                page.click('button[class="JIE42b"]')
                logging.critical("Next")
                time.sleep(20)
            elif 'запрашивает разрешение на доступ к вашему аккаунту' in element.text_content().strip():
                page.click('button[class="JIE42b"]')
                logging.critical("Next")
                time.sleep(20)

            page.wait_for_timeout(2000)
            page.screenshot(path="screenshot7.png", full_page=True)
            with open("screenshot7.png", "rb") as f:
                image_data = f.read()
            DBC.execute('INSERT INTO "Elizaveta".screenshot(photo, name) VALUES (%s, %s)', (image_data, "Authorization"))
            DB.commit()

            logging.critical("Authorization completed!")

            while True:
                logging.critical(f"Went to the article page with ID {id}")
                page.goto(f"https://supremacy.info/news/{id}")
                page.wait_for_timeout(2000)

                page.screenshot(path="screenshot6.png", full_page=True)
                with open("screenshot6.png", "rb") as f:
                    image_data = f.read()
                DBC.execute('INSERT INTO "Elizaveta".screenshot(photo, name) VALUES (%s, %s)', (image_data, "news"))
                DB.commit()

                element = page.query_selector('body')

                if "Your read-to-Earn opportunity:" in element.text_content().strip():
                    page.click('#plusButton')
                    page.wait_for_timeout(1000)
                    if "You have run out of Pluses for today." in element.text_content().strip():
                        logging.critical("The news limit has been reached")
                        break
                    else:
                        logging.critical("Article appreciated!")
                        id = id + 1
                else:
                    logging.critical("The article has already been rated or the link is broken!")
                    id = id + 1
            id = id - 1

            DBC.execute('UPDATE "Elizaveta".news_ids SET id_last = %s WHERE phone = %s', (id, phone))
            logging.critical("Id UPDATE")
            DB.commit()

            browser.close()
            logging.critical("Browser is closed!")


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
        pl = get_proxies(PROXYKIND)
        html_response += '<BR><BR>' + str(n + 1) + ' ---------------------------------------------------- Proxies Founded: ' + str(len(pl)) + '<BR>'
        proxy_session = create_new_proxy_session(PROXYKIND, None)
        for c, proxy in enumerate(pl):
            html_response += '<BR>' + str(c + 1) + ' ' + str(datetime.datetime.now()) + ' ----------------------------------------------------------------------------------'
            html_response += '<BR>Proxy: ' + proxy
            proxy_session.proxies.update(dict(http=proxy.split('|')[0], https=proxy.split('|')[0]))
            # logging.critical(proxy_session.get('https://icanhazip.com').text)
            phone_jd = json.loads(requests.get('http://10.9.20.135:3000/phones/random?service=vk&bank=virtual').text)
            logging.critical(phone_jd)
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
                access_token = s1[s1.find('"access_token":"') + 16:s1.find('","anonymous_token"')]
                html_response += '<BR>Access Token: ' + access_token
                rr = vkr_validate_phone(proxy_session, phone_string, access_token, device_id, cookies)
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
                        rr = vkr_validate_phone(proxy_session, phone_string, access_token, device_id, cookies, ck, jd['captcha_sid'], jd['captcha_ts'], jd['captcha_attempt'])
                        cookies = rr.cookies
                jd = json.loads(rr.text)['response']
                login_sid = jd['sid']
                logging.critical('SID: ' + str(login_sid))
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
                rr = vkr_validate_phone_confirm(proxy_session, phone_string, access_token, device_id, login_sid, str(jd).split(' ')[1], cookies)
                html_response += '<BR>Phone Validation Confirmation Response: ' + rr.text + '<BR>'
                cookies = rr.cookies
                jd = json.loads(rr.text)['response']
                sid = jd['sid']
                password = js_userandom_string(21)
                first_name = random.choice(Names).split(' ')[0]
                last_name = random.choice(Names).split(' ')[1]
                birthday = str(random.randint(10, 28)) + '.0' + str(random.randint(1, 9)) + '.' + str(random.randint(1980, 2004))
                rr = vkr_signup(proxy_session, phone_string, password, access_token, device_id, jd['sid'], birthday, first_name, last_name, cookies)
                html_response += '<BR>Signup Response: ' + rr.text + '<BR>'
                jd = json.loads(rr.text)
                if 'response' in jd:
                    jd = json.loads(rr.text)['response']
                    time.sleep(8)
                    rr = get_access_token(phone_string, password)
                    html_response += '<BR>Access Token Getting Response: ' + rr.text
                    access_token1 = rr.text.split('{"access_token":"')[1].split('","expires_in"')[0]
                    requests.post('http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?', data={'service': 'vk'})
                    info = json.dumps({'access_token': access_token1, 'MID': str(jd['mid']), 'CreationTime': str(datetime.datetime.now()), 'Proxy': proxy, 'UUID': uuid, "DeviceID": device_id, 'AuthToken': access_token, 'SID': sid, 'FirstName': first_name, 'LastName': last_name, 'Birthday': birthday}, ensure_ascii=False)
                    save_account(int(phone_jd['phone']), password, info)
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
                requests.post('http://10.9.20.135:3000/phones/' + str(phone_jd['phone']) + '/link?', json={'service': 'vk', 'broken': True})
                html_errors += '<BR>' + str(E) + '<BR>'
        time.sleep(random.randint(1, 180))
    logging.critical('Registration Finished At: ' + str(datetime.datetime.now()))
    html_response += '<BR>Registration Finished At: ' + str(datetime.datetime.now()) + '<BR><BR><BR>'
    html_response += '<BR>Errors List:<BR>' + html_errors
    REGISTRATION_STARTED = False
    return HTMLResponse(content=html_response, status_code=200)


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
