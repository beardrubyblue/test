import  requests

res = requests.get('https://debank.com/profile/0xd3c3bd12d25973d5497397c93faac143fa2ce6ee')

print(res.content)