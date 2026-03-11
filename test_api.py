import urllib.parse, base64, urllib.request

url = 'https://1drv.ms/i/c/1bcf807d12f8740a/IQBGCGfhukmfQ4kuzZTM8Cj7AVkC4goPuyrKrWThAndEZAU'
encoded = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')
api_url = f'https://api.onedrive.com/v1.0/shares/u!{encoded}/root/content'
print(api_url)

try:
    req = urllib.request.Request(api_url)
    resp = urllib.request.urlopen(req)
    print(resp.status)
except Exception as e:
    print(e)
