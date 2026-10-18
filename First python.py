import requests

response = requests.get('https://api.github.com/users/octocat')
data = response.json()
print(data['login'])
print(data['name'])