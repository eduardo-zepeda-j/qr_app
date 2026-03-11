import urllib.parse, base64, urllib.request, ssl
url = 'https://1drv.ms/i/c/1bcf807d12f8740a/IQBGCGfhukmfQ4kuzZTM8Cj7AVkC4goPuyrKrWThAndEZAU'
encoded = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')
api_url = f'https://api.onedrive.com/v1.0/shares/u!{encoded}/root/content'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    resp = urllib.request.urlopen(req, context=ctx)
    print(resp.status)
    print(resp.url)
except urllib.error.HTTPError as e:
    print(e.code, e.hdrs)
except Exception as e:
    print(e)
