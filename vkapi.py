import os
import json
import random
import logging
import asyncio
import configs
import aiohttp
import psycopg
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from twocaptcha import TwoCaptcha
from playwright.async_api import async_playwright
from configs import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logging.basicConfig(level=logging.CRITICAL, format="%(message)s")
DB = psycopg.connect(**configs.db_config())
DBC = DB.cursor()

CC = {
    'server': 'rucaptcha.com',
    'apiKey': 'b7daa375616afc09a250286108ea037d',
    'softId': '',
    'callback': '',
    'defaultTimeout': 120,
    'recaptchaTimeout': 600,
    'pollingInterval': 10}
SOLVER = TwoCaptcha(**CC)


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
        params = {'pool_id': '9f687b07-b5f5-4227-9d04-4888ac5be496', 'limit': 10000, 'sla': '0.0'}
        async with aiohttp.ClientSession() as session:
            response = await session.get('https://proxy-manager.ad.dev.arbat.dev/pools/9f687b07-b5f5-4227-9d04-4888ac5be496/proxies', params=params)
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
            response = await session.get('https://proxy-manager.ad.dev.arbat.dev/pools/b4485d4d-d678-4b5f-9ada-b972db01764b/proxies', params=params)
            jd = json.loads(await response.text(errors='replace'))
            for proxy in jd:
                if proxy['proxy']['proxy_type'] == ptype and proxy['proxy']['country_code'] == country:
                    proxy_list.append(f"{pt}{proxy['proxy']['login']}:{proxy['proxy']['password']}@{proxy['proxy']['host']}:{proxy['proxy']['port']}")
    # Быстрое получение одной платной https или socks5 прокси указанной страны из объединения proxy6_net_pool сайта [https://proxy-manager.arbat.dev], которая дольше всех не использовалась.
    if kind == 5 and ptype in [2, 3]:
        params = {'pool_id': '9f687b07-b5f5-4227-9d04-4888ac5be496', 'sla': '0.7', "country": country}
        async with aiohttp.ClientSession() as session:
            response = await session.get('https://proxy-manager.ad.dev.arbat.dev/proxies/use', params=params)
            jd = json.loads(await response.text(errors='replace'))
            proxy = jd['proxy']
            proxy_list.append(f"{pt}{proxy['login']}:{proxy['password']}@{proxy['host']}:{proxy['port']}")
    random.shuffle(proxy_list)
    return proxy_list[:max_amount]

method_urls = [
    "https://dev.vk.com/ru/method/users.get",
    "https://dev.vk.com/ru/method/users.getFollowers",
    "https://dev.vk.com/ru/method/users.getSubscriptions",
    "https://dev.vk.com/ru/method/users.report",
    "https://dev.vk.com/ru/method/users.search",
    "https://dev.vk.com/ru/method/account.ban",
    "https://dev.vk.com/ru/method/account.changePassword",
    "https://dev.vk.com/ru/method/account.getActiveOffers",
    "https://dev.vk.com/ru/method/account.getAppPermissions",
    "https://dev.vk.com/ru/method/account.getBanned",
    "https://dev.vk.com/ru/method/account.getCounters",
    "https://dev.vk.com/ru/method/account.getInfo",
    "https://dev.vk.com/ru/method/account.getProfileInfo",
    "https://dev.vk.com/ru/method/account.getPushSettings",
    "https://dev.vk.com/ru/method/account.registerDevice",
    "https://dev.vk.com/ru/method/account.saveProfileInfo",
    "https://dev.vk.com/ru/method/account.setInfo",
    "https://dev.vk.com/ru/method/account.setOffline",
    "https://dev.vk.com/ru/method/account.setOnline",
    "https://dev.vk.com/ru/method/account.setPushSettings",
    "https://dev.vk.com/ru/method/account.setSilenceMode",
    "https://dev.vk.com/ru/method/account.unban",
    "https://dev.vk.com/ru/method/account.unregisterDevice",
    "https://dev.vk.com/ru/method/ads.addOfficeUsers",
    "https://dev.vk.com/ru/method/ads.checkLink",
    "https://dev.vk.com/ru/method/ads.createAds",
    "https://dev.vk.com/ru/method/ads.createCampaigns",
    "https://dev.vk.com/ru/method/ads.createClients",
    "https://dev.vk.com/ru/method/ads.createLookalikeRequest",
    "https://dev.vk.com/ru/method/ads.createTargetGroup",
    "https://dev.vk.com/ru/method/ads.createTargetPixel",
    "https://dev.vk.com/ru/method/ads.deleteAds",
    "https://dev.vk.com/ru/method/ads.deleteCampaigns",
    "https://dev.vk.com/ru/method/ads.deleteClients",
    "https://dev.vk.com/ru/method/ads.deleteTargetGroup",
    "https://dev.vk.com/ru/method/ads.deleteTargetPixel",
    "https://dev.vk.com/ru/method/ads.getAccounts",
    "https://dev.vk.com/ru/method/ads.getAds",
    "https://dev.vk.com/ru/method/ads.getAdsLayout",
    "https://dev.vk.com/ru/method/ads.getAdsTargeting",
    "https://dev.vk.com/ru/method/ads.getBudget",
    "https://dev.vk.com/ru/method/ads.getCampaigns",
    "https://dev.vk.com/ru/method/ads.getCategories",
    "https://dev.vk.com/ru/method/ads.getClients",
    "https://dev.vk.com/ru/method/ads.getDemographics",
    "https://dev.vk.com/ru/method/ads.getFloodStats",
    "https://dev.vk.com/ru/method/ads.getLookalikeRequests",
    "https://dev.vk.com/ru/method/ads.getMusicians",
    "https://dev.vk.com/ru/method/ads.getMusiciansByIds",
    "https://dev.vk.com/ru/method/ads.getOfficeUsers",
    "https://dev.vk.com/ru/method/ads.getPostsReach",
    "https://dev.vk.com/ru/method/ads.getRejectionReason",
    "https://dev.vk.com/ru/method/ads.getStatistics",
    "https://dev.vk.com/ru/method/ads.getSuggestions",
    "https://dev.vk.com/ru/method/ads.getTargetGroups",
    "https://dev.vk.com/ru/method/ads.getTargetPixels",
    "https://dev.vk.com/ru/method/ads.getTargetingStats",
    "https://dev.vk.com/ru/method/ads.getUploadURL",
    "https://dev.vk.com/ru/method/ads.getVideoUploadURL",
    "https://dev.vk.com/ru/method/ads.importTargetContacts",
    "https://dev.vk.com/ru/method/ads.removeOfficeUsers",
    "https://dev.vk.com/ru/method/ads.removeTargetContacts",
    "https://dev.vk.com/ru/method/ads.saveLookalikeRequestResult",
    "https://dev.vk.com/ru/method/ads.shareTargetGroup",
    "https://dev.vk.com/ru/method/ads.updateAds",
    "https://dev.vk.com/ru/method/ads.updateCampaigns",
    "https://dev.vk.com/ru/method/ads.updateClients",
    "https://dev.vk.com/ru/method/ads.updateOfficeUsers",
    "https://dev.vk.com/ru/method/ads.updateTargetGroup",
    "https://dev.vk.com/ru/method/ads.updateTargetPixel",
    "https://dev.vk.com/ru/method/appWidgets.getAppImageUploadServer",
    "https://dev.vk.com/ru/method/appWidgets.getAppImages",
    "https://dev.vk.com/ru/method/appWidgets.getGroupImageUploadServer",
    "https://dev.vk.com/ru/method/appWidgets.getGroupImages",
    "https://dev.vk.com/ru/method/appWidgets.getImagesById",
    "https://dev.vk.com/ru/method/appWidgets.saveAppImage",
    "https://dev.vk.com/ru/method/appWidgets.saveGroupImage",
    "https://dev.vk.com/ru/method/appWidgets.update",
    "https://dev.vk.com/ru/method/apps.addSnippet",
    "https://dev.vk.com/ru/method/apps.addUsersToTestingGroup",
    "https://dev.vk.com/ru/method/apps.deleteAppRequests",
    "https://dev.vk.com/ru/method/apps.deleteSnippet",
    "https://dev.vk.com/ru/method/apps.get",
    "https://dev.vk.com/ru/method/apps.getCatalog",
    "https://dev.vk.com/ru/method/apps.getFriendsList",
    "https://dev.vk.com/ru/method/apps.getLeaderboard",
    "https://dev.vk.com/ru/method/apps.getMiniAppPolicies",
    "https://dev.vk.com/ru/method/apps.getScopes",
    "https://dev.vk.com/ru/method/apps.getScore",
    "https://dev.vk.com/ru/method/apps.getSnippets",
    "https://dev.vk.com/ru/method/apps.getTestingGroups",
    "https://dev.vk.com/ru/method/apps.isNotificationsAllowed",
    "https://dev.vk.com/ru/method/apps.promoHasActiveGift",
    "https://dev.vk.com/ru/method/apps.promoUseGift",
    "https://dev.vk.com/ru/method/apps.removeTestingGroup",
    "https://dev.vk.com/ru/method/apps.removeUsersFromTestingGroups",
    "https://dev.vk.com/ru/method/apps.sendRequest",
    "https://dev.vk.com/ru/method/apps.updateMetaForTestingGroup",
    "https://dev.vk.com/ru/method/auth.restore",
    "https://dev.vk.com/ru/method/board.addTopic",
    "https://dev.vk.com/ru/method/board.closeTopic",
    "https://dev.vk.com/ru/method/board.createComment",
    "https://dev.vk.com/ru/method/board.deleteComment",
    "https://dev.vk.com/ru/method/board.deleteTopic",
    "https://dev.vk.com/ru/method/board.editComment",
    "https://dev.vk.com/ru/method/board.editTopic",
    "https://dev.vk.com/ru/method/board.fixTopic",
    "https://dev.vk.com/ru/method/board.getComments",
    "https://dev.vk.com/ru/method/board.getTopics",
    "https://dev.vk.com/ru/method/board.openTopic",
    "https://dev.vk.com/ru/method/board.restoreComment",
    "https://dev.vk.com/ru/method/board.unfixTopic",
    "https://dev.vk.com/ru/method/bugtracker.addCompanyGroupsMembers",
    "https://dev.vk.com/ru/method/bugtracker.addCompanyMembers",
    "https://dev.vk.com/ru/method/bugtracker.changeBugreportStatus",
    "https://dev.vk.com/ru/method/bugtracker.createComment",
    "https://dev.vk.com/ru/method/bugtracker.getBugreportById",
    "https://dev.vk.com/ru/method/bugtracker.getCompanyGroupMembers",
    "https://dev.vk.com/ru/method/bugtracker.getCompanyMembers",
    "https://dev.vk.com/ru/method/bugtracker.getDownloadVersionUrl",
    "https://dev.vk.com/ru/method/bugtracker.getProductBuildUploadServer",
    "https://dev.vk.com/ru/method/bugtracker.removeCompanyGroupMember",
    "https://dev.vk.com/ru/method/bugtracker.removeCompanyMember",
    "https://dev.vk.com/ru/method/bugtracker.saveProductVersion",
    "https://dev.vk.com/ru/method/bugtracker.setCompanyMemberRole",
    "https://dev.vk.com/ru/method/bugtracker.setProductIsOver",
    "https://dev.vk.com/ru/method/calls.forceFinish",
    "https://dev.vk.com/ru/method/calls.start",
    "https://dev.vk.com/ru/method/database.getChairs",
    "https://dev.vk.com/ru/method/database.getCities",
    "https://dev.vk.com/ru/method/database.getCitiesById",
    "https://dev.vk.com/ru/method/database.getCountries",
    "https://dev.vk.com/ru/method/database.getCountriesById",
    "https://dev.vk.com/ru/method/database.getFaculties",
    "https://dev.vk.com/ru/method/database.getMetroStations",
    "https://dev.vk.com/ru/method/database.getMetroStationsById",
    "https://dev.vk.com/ru/method/database.getRegions",
    "https://dev.vk.com/ru/method/database.getSchoolClasses",
    "https://dev.vk.com/ru/method/database.getSchools",
    "https://dev.vk.com/ru/method/database.getUniversities",
    "https://dev.vk.com/ru/method/docs.add",
    "https://dev.vk.com/ru/method/docs.delete",
    "https://dev.vk.com/ru/method/docs.edit",
    "https://dev.vk.com/ru/method/docs.get",
    "https://dev.vk.com/ru/method/docs.getById",
    "https://dev.vk.com/ru/method/docs.getMessagesUploadServer",
    "https://dev.vk.com/ru/method/docs.getTypes",
    "https://dev.vk.com/ru/method/docs.getUploadServer",
    "https://dev.vk.com/ru/method/docs.getWallUploadServer",
    "https://dev.vk.com/ru/method/docs.save",
    "https://dev.vk.com/ru/method/docs.search",
    "https://dev.vk.com/ru/method/donut.getFriends",
    "https://dev.vk.com/ru/method/donut.getSubscription",
    "https://dev.vk.com/ru/method/donut.getSubscriptions",
    "https://dev.vk.com/ru/method/donut.isDon",
    "https://dev.vk.com/ru/method/downloadedGames.getPaidStatus",
    "https://dev.vk.com/ru/method/execute",
    "https://dev.vk.com/ru/method/fave.addArticle",
    "https://dev.vk.com/ru/method/fave.addLink",
    "https://dev.vk.com/ru/method/fave.addPage",
    "https://dev.vk.com/ru/method/fave.addPost",
    "https://dev.vk.com/ru/method/fave.addProduct",
    "https://dev.vk.com/ru/method/fave.addTag",
    "https://dev.vk.com/ru/method/fave.addVideo",
    "https://dev.vk.com/ru/method/fave.editTag",
    "https://dev.vk.com/ru/method/fave.get",
    "https://dev.vk.com/ru/method/fave.getPages",
    "https://dev.vk.com/ru/method/fave.getTags",
    "https://dev.vk.com/ru/method/fave.markSeen",
    "https://dev.vk.com/ru/method/fave.removeArticle",
    "https://dev.vk.com/ru/method/fave.removeLink",
    "https://dev.vk.com/ru/method/fave.removePage",
    "https://dev.vk.com/ru/method/fave.removePost",
    "https://dev.vk.com/ru/method/fave.removeProduct",
    "https://dev.vk.com/ru/method/fave.removeTag",
    "https://dev.vk.com/ru/method/fave.removeVideo",
    "https://dev.vk.com/ru/method/fave.reorderTags",
    "https://dev.vk.com/ru/method/fave.setPageTags",
    "https://dev.vk.com/ru/method/fave.setTags",
    "https://dev.vk.com/ru/method/fave.trackPageInteraction",
    "https://dev.vk.com/ru/method/friends.add",
    "https://dev.vk.com/ru/method/friends.addList",
    "https://dev.vk.com/ru/method/friends.areFriends",
    "https://dev.vk.com/ru/method/friends.delete",
    "https://dev.vk.com/ru/method/friends.deleteAllRequests",
    "https://dev.vk.com/ru/method/friends.deleteList",
    "https://dev.vk.com/ru/method/friends.edit",
    "https://dev.vk.com/ru/method/friends.editList",
    "https://dev.vk.com/ru/method/friends.get",
    "https://dev.vk.com/ru/method/friends.getAppUsers",
    "https://dev.vk.com/ru/method/friends.getLists",
    "https://dev.vk.com/ru/method/friends.getMutual",
    "https://dev.vk.com/ru/method/friends.getOnline",
    "https://dev.vk.com/ru/method/friends.getRecent",
    "https://dev.vk.com/ru/method/friends.getRequests",
    "https://dev.vk.com/ru/method/friends.getSuggestions",
    "https://dev.vk.com/ru/method/friends.search",
    "https://dev.vk.com/ru/method/gifts.get",
    "https://dev.vk.com/ru/method/groups.addAddress",
    "https://dev.vk.com/ru/method/groups.addCallbackServer",
    "https://dev.vk.com/ru/method/groups.addLink",
    "https://dev.vk.com/ru/method/groups.approveRequest",
    "https://dev.vk.com/ru/method/groups.ban",
    "https://dev.vk.com/ru/method/groups.create",
    "https://dev.vk.com/ru/method/groups.deleteAddress",
    "https://dev.vk.com/ru/method/groups.deleteCallbackServer",
    "https://dev.vk.com/ru/method/groups.deleteLink",
    "https://dev.vk.com/ru/method/groups.disableOnline",
    "https://dev.vk.com/ru/method/groups.edit",
    "https://dev.vk.com/ru/method/groups.editAddress",
    "https://dev.vk.com/ru/method/groups.editCallbackServer",
    "https://dev.vk.com/ru/method/groups.editLink",
    "https://dev.vk.com/ru/method/groups.editManager",
    "https://dev.vk.com/ru/method/groups.enableOnline",
    "https://dev.vk.com/ru/method/groups.get",
    "https://dev.vk.com/ru/method/groups.getAddresses",
    "https://dev.vk.com/ru/method/groups.getBanned",
    "https://dev.vk.com/ru/method/groups.getById",
    "https://dev.vk.com/ru/method/groups.getCallbackConfirmationCode",
    "https://dev.vk.com/ru/method/groups.getCallbackServers",
    "https://dev.vk.com/ru/method/groups.getCallbackSettings",
    "https://dev.vk.com/ru/method/groups.getCatalogInfo",
    "https://dev.vk.com/ru/method/groups.getInvitedUsers",
    "https://dev.vk.com/ru/method/groups.getInvites",
    "https://dev.vk.com/ru/method/groups.getLongPollServer",
    "https://dev.vk.com/ru/method/groups.getLongPollSettings",
    "https://dev.vk.com/ru/method/groups.getMembers",
    "https://dev.vk.com/ru/method/groups.getOnlineStatus",
    "https://dev.vk.com/ru/method/groups.getRequests",
    "https://dev.vk.com/ru/method/groups.getSettings",
    "https://dev.vk.com/ru/method/groups.getTagList",
    "https://dev.vk.com/ru/method/groups.getTokenPermissions",
    "https://dev.vk.com/ru/method/groups.invite",
    "https://dev.vk.com/ru/method/groups.isMember",
    "https://dev.vk.com/ru/method/groups.join",
    "https://dev.vk.com/ru/method/groups.leave",
    "https://dev.vk.com/ru/method/groups.removeUser",
    "https://dev.vk.com/ru/method/groups.reorderLink",
    "https://dev.vk.com/ru/method/groups.search",
    "https://dev.vk.com/ru/method/groups.setCallbackSettings",
    "https://dev.vk.com/ru/method/groups.setLongPollSettings",
    "https://dev.vk.com/ru/method/groups.setSettings",
    "https://dev.vk.com/ru/method/groups.setUserNote",
    "https://dev.vk.com/ru/method/groups.tagAdd",
    "https://dev.vk.com/ru/method/groups.tagBind",
    "https://dev.vk.com/ru/method/groups.tagDelete",
    "https://dev.vk.com/ru/method/groups.tagUpdate",
    "https://dev.vk.com/ru/method/groups.toggleMarket",
    "https://dev.vk.com/ru/method/groups.unban",
    "https://dev.vk.com/ru/method/leadForms.create",
    "https://dev.vk.com/ru/method/leadForms.delete",
    "https://dev.vk.com/ru/method/leadForms.get",
    "https://dev.vk.com/ru/method/leadForms.getLeads",
    "https://dev.vk.com/ru/method/leadForms.getUploadURL",
    "https://dev.vk.com/ru/method/leadForms.list",
    "https://dev.vk.com/ru/method/leadForms.update",
    "https://dev.vk.com/ru/method/likes.add",
    "https://dev.vk.com/ru/method/likes.delete",
    "https://dev.vk.com/ru/method/likes.getList",
    "https://dev.vk.com/ru/method/likes.isLiked",
    "https://dev.vk.com/ru/method/market.add",
    "https://dev.vk.com/ru/method/market.addAlbum",
    "https://dev.vk.com/ru/method/market.addProperty",
    "https://dev.vk.com/ru/method/market.addPropertyVariant",
    "https://dev.vk.com/ru/method/market.addToAlbum",
    "https://dev.vk.com/ru/method/market.createComment",
    "https://dev.vk.com/ru/method/market.delete",
    "https://dev.vk.com/ru/method/market.deleteAlbum",
    "https://dev.vk.com/ru/method/market.deleteComment",
    "https://dev.vk.com/ru/method/market.deleteProperty",
    "https://dev.vk.com/ru/method/market.deletePropertyVariant",
    "https://dev.vk.com/ru/method/market.edit",
    "https://dev.vk.com/ru/method/market.editAlbum",
    "https://dev.vk.com/ru/method/market.editComment",
    "https://dev.vk.com/ru/method/market.editOrder",
    "https://dev.vk.com/ru/method/market.editProperty",
    "https://dev.vk.com/ru/method/market.editPropertyVariant",
    "https://dev.vk.com/ru/method/market.filterCategories",
    "https://dev.vk.com/ru/method/market.get",
    "https://dev.vk.com/ru/method/market.getAlbumById",
    "https://dev.vk.com/ru/method/market.getAlbums",
    "https://dev.vk.com/ru/method/market.getById",
    "https://dev.vk.com/ru/method/market.getComments",
    "https://dev.vk.com/ru/method/market.getGroupOrders",
    "https://dev.vk.com/ru/method/market.getOrderById",
    "https://dev.vk.com/ru/method/market.getOrderItems",
    "https://dev.vk.com/ru/method/market.getOrders",
    "https://dev.vk.com/ru/method/market.getProductPhotoUploadServer",
    "https://dev.vk.com/ru/method/market.getProperties",
    "https://dev.vk.com/ru/method/market.groupItems",
    "https://dev.vk.com/ru/method/market.removeFromAlbum",
    "https://dev.vk.com/ru/method/market.reorderAlbums",
    "https://dev.vk.com/ru/method/market.reorderItems",
    "https://dev.vk.com/ru/method/market.report",
    "https://dev.vk.com/ru/method/market.reportComment",
    "https://dev.vk.com/ru/method/market.restore",
    "https://dev.vk.com/ru/method/market.restoreComment",
    "https://dev.vk.com/ru/method/market.saveProductPhoto",
    "https://dev.vk.com/ru/method/market.saveProductPhotoBulk",
    "https://dev.vk.com/ru/method/market.search",
    "https://dev.vk.com/ru/method/market.searchItems",
    "https://dev.vk.com/ru/method/market.searchItemsBasic",
    "https://dev.vk.com/ru/method/market.ungroupItems",
    "https://dev.vk.com/ru/method/messages.addChatUser",
    "https://dev.vk.com/ru/method/messages.allowMessagesFromGroup",
    "https://dev.vk.com/ru/method/messages.createChat",
    "https://dev.vk.com/ru/method/messages.delete",
    "https://dev.vk.com/ru/method/messages.deleteChatPhoto",
    "https://dev.vk.com/ru/method/messages.deleteConversation",
    "https://dev.vk.com/ru/method/messages.deleteReaction",
    "https://dev.vk.com/ru/method/messages.denyMessagesFromGroup",
    "https://dev.vk.com/ru/method/messages.editChat",
    "https://dev.vk.com/ru/method/messages.getByConversationMessageId",
    "https://dev.vk.com/ru/method/messages.getById",
    "https://dev.vk.com/ru/method/messages.getChat",
    "https://dev.vk.com/ru/method/messages.getChatPreview",
    "https://dev.vk.com/ru/method/messages.getConversationMembers",
    "https://dev.vk.com/ru/method/messages.getConversations",
    "https://dev.vk.com/ru/method/messages.getConversationsById",
    "https://dev.vk.com/ru/method/messages.getHistory",
    "https://dev.vk.com/ru/method/messages.getHistoryAttachments",
    "https://dev.vk.com/ru/method/messages.getImportantMessages",
    "https://dev.vk.com/ru/method/messages.getIntentUsers",
    "https://dev.vk.com/ru/method/messages.getInviteLink",
    "https://dev.vk.com/ru/method/messages.getLastActivity",
    "https://dev.vk.com/ru/method/messages.getLongPollHistory",
    "https://dev.vk.com/ru/method/messages.getLongPollServer",
    "https://dev.vk.com/ru/method/messages.getMessagesReactions",
    "https://dev.vk.com/ru/method/messages.getReactedPeers",
    "https://dev.vk.com/ru/method/messages.getReactionsAssets",
    "https://dev.vk.com/ru/method/messages.isMessagesFromGroupAllowed",
    "https://dev.vk.com/ru/method/messages.joinChatByInviteLink",
    "https://dev.vk.com/ru/method/messages.markAsAnsweredConversation",
    "https://dev.vk.com/ru/method/messages.markAsImportant",
    "https://dev.vk.com/ru/method/messages.markAsImportantConversation",
    "https://dev.vk.com/ru/method/messages.markAsRead",
    "https://dev.vk.com/ru/method/messages.markReactionsAsRead",
    "https://dev.vk.com/ru/method/messages.pin",
    "https://dev.vk.com/ru/method/messages.removeChatUser",
    "https://dev.vk.com/ru/method/messages.restore",
    "https://dev.vk.com/ru/method/messages.search",
    "https://dev.vk.com/ru/method/messages.searchConversations",
    "https://dev.vk.com/ru/method/messages.send",
    "https://dev.vk.com/ru/method/messages.sendMessageEventAnswer",
    "https://dev.vk.com/ru/method/messages.sendReaction",
    "https://dev.vk.com/ru/method/messages.setActivity",
    "https://dev.vk.com/ru/method/messages.setChatPhoto",
    "https://dev.vk.com/ru/method/messages.unpin",
    "https://dev.vk.com/ru/method/newsfeed.addBan",
    "https://dev.vk.com/ru/method/newsfeed.deleteBan",
    "https://dev.vk.com/ru/method/newsfeed.deleteList",
    "https://dev.vk.com/ru/method/newsfeed.get",
    "https://dev.vk.com/ru/method/newsfeed.getBanned",
    "https://dev.vk.com/ru/method/newsfeed.getComments",
    "https://dev.vk.com/ru/method/newsfeed.getLists",
    "https://dev.vk.com/ru/method/newsfeed.getMentions",
    "https://dev.vk.com/ru/method/newsfeed.getRecommended",
    "https://dev.vk.com/ru/method/newsfeed.getSuggestedSources",
    "https://dev.vk.com/ru/method/newsfeed.ignoreItem",
    "https://dev.vk.com/ru/method/newsfeed.saveList",
    "https://dev.vk.com/ru/method/newsfeed.search",
    "https://dev.vk.com/ru/method/newsfeed.unignoreItem",
    "https://dev.vk.com/ru/method/newsfeed.unsubscribe",
    "https://dev.vk.com/ru/method/notes.add",
    "https://dev.vk.com/ru/method/notes.createComment",
    "https://dev.vk.com/ru/method/notes.delete",
    "https://dev.vk.com/ru/method/notes.deleteComment",
    "https://dev.vk.com/ru/method/notes.edit",
    "https://dev.vk.com/ru/method/notes.editComment",
    "https://dev.vk.com/ru/method/notes.get",
    "https://dev.vk.com/ru/method/notes.getById",
    "https://dev.vk.com/ru/method/notes.getComments",
    "https://dev.vk.com/ru/method/notes.restoreComment",
    "https://dev.vk.com/ru/method/notifications.get",
    "https://dev.vk.com/ru/method/notifications.markAsViewed",
    "https://dev.vk.com/ru/method/notifications.sendMessage",
    "https://dev.vk.com/ru/method/orders.cancelSubscription",
    "https://dev.vk.com/ru/method/orders.changeState",
    "https://dev.vk.com/ru/method/orders.get",
    "https://dev.vk.com/ru/method/orders.getAmount",
    "https://dev.vk.com/ru/method/orders.getById",
    "https://dev.vk.com/ru/method/orders.getUserSubscriptionById",
    "https://dev.vk.com/ru/method/orders.getUserSubscriptions",
    "https://dev.vk.com/ru/method/pages.clearCache",
    "https://dev.vk.com/ru/method/pages.get",
    "https://dev.vk.com/ru/method/pages.getHistory",
    "https://dev.vk.com/ru/method/pages.getTitles",
    "https://dev.vk.com/ru/method/pages.getVersion",
    "https://dev.vk.com/ru/method/pages.parseWiki",
    "https://dev.vk.com/ru/method/pages.save",
    "https://dev.vk.com/ru/method/pages.saveAccess",
    "https://dev.vk.com/ru/method/photos.confirmTag",
    "https://dev.vk.com/ru/method/photos.copy",
    "https://dev.vk.com/ru/method/photos.createAlbum",
    "https://dev.vk.com/ru/method/photos.createComment",
    "https://dev.vk.com/ru/method/photos.delete",
    "https://dev.vk.com/ru/method/photos.deleteAlbum",
    "https://dev.vk.com/ru/method/photos.deleteComment",
    "https://dev.vk.com/ru/method/photos.edit",
    "https://dev.vk.com/ru/method/photos.editAlbum",
    "https://dev.vk.com/ru/method/photos.editComment",
    "https://dev.vk.com/ru/method/photos.get",
    "https://dev.vk.com/ru/method/photos.getAlbums",
    "https://dev.vk.com/ru/method/photos.getAlbumsCount",
    "https://dev.vk.com/ru/method/photos.getAll",
    "https://dev.vk.com/ru/method/photos.getAllComments",
    "https://dev.vk.com/ru/method/photos.getById",
    "https://dev.vk.com/ru/method/photos.getChatUploadServer",
    "https://dev.vk.com/ru/method/photos.getComments",
    "https://dev.vk.com/ru/method/photos.getMarketAlbumUploadServer",
    "https://dev.vk.com/ru/method/photos.getMessagesUploadServer",
    "https://dev.vk.com/ru/method/photos.getNewTags",
    "https://dev.vk.com/ru/method/photos.getOwnerCoverPhotoUploadServer",
    "https://dev.vk.com/ru/method/photos.getOwnerPhotoUploadServer",
    "https://dev.vk.com/ru/method/photos.getTags",
    "https://dev.vk.com/ru/method/photos.getUploadServer",
    "https://dev.vk.com/ru/method/photos.getUserPhotos",
    "https://dev.vk.com/ru/method/photos.getWallUploadServer",
    "https://dev.vk.com/ru/method/photos.makeCover",
    "https://dev.vk.com/ru/method/photos.move",
    "https://dev.vk.com/ru/method/photos.putTag",
    "https://dev.vk.com/ru/method/photos.removeTag",
    "https://dev.vk.com/ru/method/photos.reorderAlbums",
    "https://dev.vk.com/ru/method/photos.reorderPhotos",
    "https://dev.vk.com/ru/method/photos.report",
    "https://dev.vk.com/ru/method/photos.reportComment",
    "https://dev.vk.com/ru/method/photos.restore",
    "https://dev.vk.com/ru/method/photos.restoreComment",
    "https://dev.vk.com/ru/method/photos.save",
    "https://dev.vk.com/ru/method/photos.saveMarketAlbumPhoto",
    "https://dev.vk.com/ru/method/photos.saveMessagesPhoto",
    "https://dev.vk.com/ru/method/photos.saveOwnerCoverPhoto",
    "https://dev.vk.com/ru/method/photos.saveOwnerPhoto",
    "https://dev.vk.com/ru/method/photos.saveWallPhoto",
    "https://dev.vk.com/ru/method/photos.search",
    "https://dev.vk.com/ru/method/podcasts.searchPodcast",
    "https://dev.vk.com/ru/method/polls.addVote",
    "https://dev.vk.com/ru/method/polls.create",
    "https://dev.vk.com/ru/method/polls.deleteVote",
    "https://dev.vk.com/ru/method/polls.edit",
    "https://dev.vk.com/ru/method/polls.getBackgrounds",
    "https://dev.vk.com/ru/method/polls.getById",
    "https://dev.vk.com/ru/method/polls.getPhotoUploadServer",
    "https://dev.vk.com/ru/method/polls.getVoters",
    "https://dev.vk.com/ru/method/polls.savePhoto",
    "https://dev.vk.com/ru/method/prettyCards.create",
    "https://dev.vk.com/ru/method/prettyCards.delete",
    "https://dev.vk.com/ru/method/prettyCards.edit",
    "https://dev.vk.com/ru/method/prettyCards.get",
    "https://dev.vk.com/ru/method/prettyCards.getById",
    "https://dev.vk.com/ru/method/prettyCards.getUploadURL",
    "https://dev.vk.com/ru/method/search.getHints",
    "https://dev.vk.com/ru/method/secure.addAppEvent",
    "https://dev.vk.com/ru/method/secure.checkToken",
    "https://dev.vk.com/ru/method/secure.getAppBalance",
    "https://dev.vk.com/ru/method/secure.getSMSHistory",
    "https://dev.vk.com/ru/method/secure.getTransactionsHistory",
    "https://dev.vk.com/ru/method/secure.getUserLevel",
    "https://dev.vk.com/ru/method/secure.giveEventSticker",
    "https://dev.vk.com/ru/method/secure.sendNotification",
    "https://dev.vk.com/ru/method/secure.sendSMSNotification",
    "https://dev.vk.com/ru/method/secure.setCounter",
    "https://dev.vk.com/ru/method/stats.get",
    "https://dev.vk.com/ru/method/stats.getPostReach",
    "https://dev.vk.com/ru/method/stats.trackVisitor",
    "https://dev.vk.com/ru/method/status.get",
    "https://dev.vk.com/ru/method/status.set",
    "https://dev.vk.com/ru/method/storage.get",
    "https://dev.vk.com/ru/method/storage.getKeys",
    "https://dev.vk.com/ru/method/storage.set",
    "https://dev.vk.com/ru/method/store.addStickersToFavorite",
    "https://dev.vk.com/ru/method/store.getFavoriteStickers",
    "https://dev.vk.com/ru/method/store.getProducts",
    "https://dev.vk.com/ru/method/store.getStickersKeywords",
    "https://dev.vk.com/ru/method/store.removeStickersFromFavorite",
    "https://dev.vk.com/ru/method/stories.banOwner",
    "https://dev.vk.com/ru/method/stories.delete",
    "https://dev.vk.com/ru/method/stories.get",
    "https://dev.vk.com/ru/method/stories.getBanned",
    "https://dev.vk.com/ru/method/stories.getById",
    "https://dev.vk.com/ru/method/stories.getPhotoUploadServer",
    "https://dev.vk.com/ru/method/stories.getReplies",
    "https://dev.vk.com/ru/method/stories.getStats",
    "https://dev.vk.com/ru/method/stories.getVideoUploadServer",
    "https://dev.vk.com/ru/method/stories.getViewers",
    "https://dev.vk.com/ru/method/stories.hideAllReplies",
    "https://dev.vk.com/ru/method/stories.hideReply",
    "https://dev.vk.com/ru/method/stories.save",
    "https://dev.vk.com/ru/method/stories.search",
    "https://dev.vk.com/ru/method/stories.sendInteraction",
    "https://dev.vk.com/ru/method/stories.unbanOwner",
    "https://dev.vk.com/ru/method/translations.translate",
    "https://dev.vk.com/ru/method/utils.checkLink",
    "https://dev.vk.com/ru/method/utils.deleteFromLastShortened",
    "https://dev.vk.com/ru/method/utils.getLastShortenedLinks",
    "https://dev.vk.com/ru/method/utils.getLinkStats",
    "https://dev.vk.com/ru/method/utils.getServerTime",
    "https://dev.vk.com/ru/method/utils.getShortLink",
    "https://dev.vk.com/ru/method/utils.resolveScreenName",
    "https://dev.vk.com/ru/method/video.add",
    "https://dev.vk.com/ru/method/video.addAlbum",
    "https://dev.vk.com/ru/method/video.addToAlbum",
    "https://dev.vk.com/ru/method/video.createComment",
    "https://dev.vk.com/ru/method/video.delete",
    "https://dev.vk.com/ru/method/video.deleteAlbum",
    "https://dev.vk.com/ru/method/video.deleteComment",
    "https://dev.vk.com/ru/method/video.edit",
    "https://dev.vk.com/ru/method/video.editAlbum",
    "https://dev.vk.com/ru/method/video.editComment",
    "https://dev.vk.com/ru/method/video.get",
    "https://dev.vk.com/ru/method/video.getAlbumById",
    "https://dev.vk.com/ru/method/video.getAlbums",
    "https://dev.vk.com/ru/method/video.getAlbumsByVideo",
    "https://dev.vk.com/ru/method/video.getComments",
    "https://dev.vk.com/ru/method/video.getLongPollServer",
    "https://dev.vk.com/ru/method/video.getOembed",
    "https://dev.vk.com/ru/method/video.getThumbUploadUrl",
    "https://dev.vk.com/ru/method/video.liveGetCategories",
    "https://dev.vk.com/ru/method/video.removeFromAlbum",
    "https://dev.vk.com/ru/method/video.reorderAlbums",
    "https://dev.vk.com/ru/method/video.reorderVideos",
    "https://dev.vk.com/ru/method/video.report",
    "https://dev.vk.com/ru/method/video.reportComment",
    "https://dev.vk.com/ru/method/video.restore",
    "https://dev.vk.com/ru/method/video.restoreComment",
    "https://dev.vk.com/ru/method/video.save",
    "https://dev.vk.com/ru/method/video.saveUploadedThumb",
    "https://dev.vk.com/ru/method/video.search",
    "https://dev.vk.com/ru/method/video.startStreaming",
    "https://dev.vk.com/ru/method/video.stopStreaming",
    "https://dev.vk.com/ru/method/wall.checkCopyrightLink",
    "https://dev.vk.com/ru/method/wall.closeComments",
    "https://dev.vk.com/ru/method/wall.createComment",
    "https://dev.vk.com/ru/method/wall.delete",
    "https://dev.vk.com/ru/method/wall.deleteComment",
    "https://dev.vk.com/ru/method/wall.edit",
    "https://dev.vk.com/ru/method/wall.editAdsStealth",
    "https://dev.vk.com/ru/method/wall.editComment",
    "https://dev.vk.com/ru/method/wall.get",
    "https://dev.vk.com/ru/method/wall.getById",
    "https://dev.vk.com/ru/method/wall.getComment",
    "https://dev.vk.com/ru/method/wall.getComments",
    "https://dev.vk.com/ru/method/wall.getReposts",
    "https://dev.vk.com/ru/method/wall.openComments",
    "https://dev.vk.com/ru/method/wall.parseAttachedLink",
    "https://dev.vk.com/ru/method/wall.pin",
    "https://dev.vk.com/ru/method/wall.post",
    "https://dev.vk.com/ru/method/wall.postAdsStealth",
    "https://dev.vk.com/ru/method/wall.reportComment",
    "https://dev.vk.com/ru/method/wall.reportPost",
    "https://dev.vk.com/ru/method/wall.repost",
    "https://dev.vk.com/ru/method/wall.restore",
    "https://dev.vk.com/ru/method/wall.restoreComment",
    "https://dev.vk.com/ru/method/wall.search",
    "https://dev.vk.com/ru/method/wall.unpin",
    "https://dev.vk.com/ru/method/widgets.getComments",
    "https://dev.vk.com/ru/method/widgets.getPages",
]


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})


async def parse_method_page(page, url):
    try:
        await page.goto(url, timeout=20000)
        await page.wait_for_selector("section.sc-fwQFQH.cYVjhi", timeout=7000)
        section = await page.query_selector("section.sc-fwQFQH.cYVjhi >> nth=-1")
        if not section:
            return None

        divs = await section.query_selector_all("div.sc-uJiQo.gAyWti")
        method_data = {}
        index = 1
        for div in divs:
            label = await div.query_selector("label.sc-engKbd.kQgoNP")
            if label:
                text = (await label.text_content()).strip()
                method_data[str(index)] = text
                index += 1

        method_name = url.strip().split("/")[-1]
        return {method_name: method_data} if method_data else None
    except Exception as e:
        logging.warning(f"Ошибка при парсинге {url}: {e}")
        return None


async def parse_all_methods(page, urls):
    tasks = [parse_method_page(page, url) for url in urls]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r]


# 🔍 Сравнение изменений
def compare_data(old, new):
    changes = []
    old_dict = {list(x.keys())[0]: list(x.values())[0] for x in old}
    new_dict = {list(x.keys())[0]: list(x.values())[0] for x in new}

    for method in new_dict:
        if method not in old_dict:
            changes.append(f"🆕 Новый метод: {method}")
            continue
        old_fields = old_dict[method]
        new_fields = new_dict[method]

        for key in new_fields:
            if key not in old_fields:
                changes.append(f"➕ {method}: добавлено поле '{new_fields[key]}'")
            elif new_fields[key] != old_fields[key]:
                changes.append(f"✏️ {method}: '{old_fields[key]}' → '{new_fields[key]}'")

        for key in old_fields:
            if key not in new_fields:
                changes.append(f"➖ {method}: удалено поле '{old_fields[key]}'")

    return changes


async def run():
    DBC.execute(
        "SELECT id, phone, password, info, humanoid_id FROM accounts_old where kind_id = 2 and creation_time > '2025-06-18' and block is false")
    result = DBC.fetchall()
    random.shuffle(result)
    error_count = 0
    phone = result[0][1]
    password = result[0][2]
    logging.critical(phone)
    proxy_list = await standart_get_proxies(kind=2, ptype=3)
    proxy_index = 0
    if proxy_index >= len(proxy_list):
        proxy_list = await standart_get_proxies(kind=2, ptype=3)
        proxy_index = 0

    logging.critical(len(proxy_list))
    pr = proxy_list[proxy_index].split('://')[1].split('@')
    username_proxy, password_proxy = pr[0].split(':')
    host, port = pr[1].split(':')
    if " " in host:
        host = host.replace(" ", "")
    proxy = {
        'server': f'http://{host}:{port}',
        'username': username_proxy,
        'password': password_proxy
    }

    logging.critical(f"\n🕒 Запуск: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0', proxy=proxy)
        page = await context.new_page()

        await page.goto("https://vk.com/login", timeout=600000)
        print("🔐 Подожди 20 секунд на авторизацию...")
        await page.wait_for_timeout(2000)
        element = await page.query_selector('body')
        elem = await element.text_content()
        if 'Наведите камеру устройства' in elem:
            await page.locator('text=Войти другим способом').click()
            await page.fill('input[name="login"]', phone)
            await page.screenshot(path="screen.png", full_page=True)
            logging.critical('message="login"')
            await page.click('button[data-test-id="submit_btn"]')
            await page.wait_for_timeout(2000)
        else:
            await page.fill('input[id="index_email"]', phone)
            await page.click(
                'button[class="FlatButton FlatButton--primary FlatButton--size-l FlatButton--wide VkIdForm__button VkIdForm__signInButton"]')
            await page.wait_for_timeout(2000)

        await asyncio.sleep(30)

        await page.screenshot(path="screen.png", full_page=True)
        logging.critical('message="afer_email"')

        element = await page.query_selector('body')
        elem = await element.text_content()
        # -----captcha-----
        try:
            # Ожидание появления локатора
            await page.wait_for_selector('#captcha-text')
            element_exists = True
        except Exception:
            element_exists = False
        if element_exists:
            error_count = error_count + 1
            await page.screenshot(path="screen.png", full_page=True)
            logging.critical(f"error_count   element_exists: {error_count}")
        elif 'Введите код из' in elem.strip() or 'Enter SMS' in elem.strip():
            response = requests.get(f'http://10.9.20.135:3000/phones/messages/{phone}?fromTs=0').json()
            logging.critical(f'{response["messages"][0][0:30]}')
            if 'VK' in response['messages'][0][0:30]:
                kod = response['messages'][0][0:6]
            await page.screenshot(path="screen.png", full_page=True)
            logging.critical('message="before_email_after_kod"')
            try:
                await page.wait_for_selector('input[name="otp-cell"]')
                element_exists = True
            except Exception:
                element_exists = False
            if element_exists:
                await page.fill('input[name="otp-cell"]', kod)
            else:
                await page.fill('input[id="otp"]', kod)
                await page.press('input[id="otp"]', 'Enter')
            # -----captcha-----
            try:
                # Ожидание появления локатора
                await page.wait_for_selector('#captcha-text')
                element_exists = True
            except Exception:
                element_exists = False
            if element_exists:
                await page.locator('img.vkc__CaptchaPopup__image').screenshot(path='LastCaptcha.jpg')
                cid = SOLVER.send(file="LastCaptcha.jpg")
                await asyncio.sleep(5)
                while True:
                    r = requests.get(
                        f"https://rucaptcha.com/res.php?key=b7daa375616afc09a250286108ea037d&action=get&id={cid}")
                    if 'OK' in r.text:
                        break
                await page.fill('input[id="captcha-text"]', r.text.split("|")[1])

                await page.screenshot(path="screen.png", full_page=True)
                logging.critical('message="captcha"')
                # await page.click('span[class="vkuiButton__content"]')
                await page.press('input[id="captcha-text"]', 'Enter')

                await page.screenshot(path="screen.png", full_page=True)
                logging.critical('message="after_captcha"')

            await asyncio.sleep(10)
            await page.wait_for_timeout(5000)
        elif 'Введите пароль' in elem.strip():
            await page.fill('input[name="password"]', password)
            await page.click('xpath=/html/body/div/div/div/div/div/div[1]/div/div/div/div/div/form/div[2]/button')

        element = await page.query_selector('body')
        elem = await element.text_content()
        if 'Account blocked' in elem.strip():
            logging.critical('acc block')

        parsed_methods = await parse_all_methods(page, method_urls)
        await browser.close()

    prev_file = "labels_data_prev.json"
    previous = []
    if os.path.exists(prev_file):
        with open(prev_file, "r", encoding="utf-8") as f:
            previous = json.load(f)

    changes = compare_data(previous, parsed_methods)

    if changes:
        msg = "📢 Обнаружены изменения в VK API:\n" + "\n".join(changes)
        send_telegram_message(msg)
        logging.info(msg)
    else:
        logging.info("✅ Изменений не обнаружено.")

    with open(prev_file, "w", encoding="utf-8") as f:
        json.dump(parsed_methods, f, ensure_ascii=False, indent=2)


async def scheduler():
    while True:
        await run()
        await asyncio.sleep(12 * 60 * 60)

# if __name__ == "__main__":
#     print("🔁 Скрипт запущен. Ожидаем расписание каждые 12 часов...")
#     asyncio.run(scheduler())
