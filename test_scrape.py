import urllib.request
from html.parser import HTMLParser

class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og_image = None
    
    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            attrs_dict = dict(attrs)
            if attrs_dict.get("property") == "og:image" or attrs_dict.get("name") == "twitter:image":
                self.og_image = attrs_dict.get("content")

url = "https://1drv.ms/i/c/placeholder/example"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0 Safari/537.36'})
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        parser = MetaParser()
        parser.feed(html)
        print("Embed:", parser.og_image)
except Exception as e:
    print(e)
