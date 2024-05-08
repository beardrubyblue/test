import requests


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
    'username': '79858902970',
    'password': 'KX0P_yjymMQzWtN7YIzJr',
    'scope': 'notify,friends,photos,audio,video,docs,status,notes,pages,wall,groups,messages,offline,notifications,stories'
    }

rr = requests.get('https://oauth.vk.com/token', params=params, headers=headers)
print(rr.text)