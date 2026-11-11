"""Find links from cancer.org.au pages to Cancer Connect, and save the linked Connect pages.

Run daily by the GitHub Action, after fetch_sitemap.py.
1. Reads each page in LINK_SOURCES on cancer.org.au and collects links to connect.cancer.org.au
   from the page body (menus, header and footer are ignored).
2. Reads the Cancer Connect XML sitemap.
3. For each linked Connect page, keeps that page and every Connect page beneath it.
Output: data/connect.json
"""
import datetime
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

SITE = "https://www.cancer.org.au"
LINK_SOURCES = ["/types-of-cancer"]          # cancer.org.au pages to scan for Connect links
CONNECT_HOST = "connect.cancer.org.au"
CONNECT_SITEMAP = "https://connect.cancer.org.au/sitemap.xml"
OUT = "data/connect.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CCA-sitemap-explorer; +https://cca-experiments.github.io/sitemap-explorer/)"}
SKIP_TAGS = {"nav", "header", "footer"}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def clean_path(path):
    return "/" + path.strip("/") if path.strip("/") else "/"


class LinkFinder(HTMLParser):
    """Collect body links to Cancer Connect with the first piece of text inside each link."""

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.skip, self.links, self.current = base, 0, [], None

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        if tag == "a" and not self.skip:
            href = dict(attrs).get("href") or ""
            url = urlparse(urljoin(self.base, href))
            if url.hostname == CONNECT_HOST:
                self.current = {"target": clean_path(url.path), "parts": []}

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1
        if tag == "a" and self.current is not None:
            parts = [p for p in self.current["parts"] if p]
            self.links.append({"target": self.current["target"], "text": parts[0] if parts else ""})
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current["parts"].append(" ".join(data.split()))


def local(tag):
    return tag.rsplit("}", 1)[-1]


def connect_pages():
    root = ET.fromstring(fetch(CONNECT_SITEMAP))
    pages = {}
    for u in root:
        if local(u.tag) != "url":
            continue
        loc = lastmod = None
        for c in u:
            if local(c.tag) == "loc" and c.text:
                loc = c.text.strip()
            elif local(c.tag) == "lastmod" and c.text:
                lastmod = c.text.strip()
        if loc:
            pages[clean_path(urlparse(loc).path)] = {"url": loc, "lastmod": lastmod}
    return pages


def main():
    found = {}
    for source in LINK_SOURCES:
        finder = LinkFinder(SITE + source)
        finder.feed(fetch(SITE + source).decode("utf-8", "replace"))
        for link in finder.links:
            entry = found.setdefault(link["target"], {"source": source, "target": link["target"], "names": []})
            if link["text"] and link["text"] not in entry["names"]:
                entry["names"].append(link["text"])
    pages = connect_pages()
    links = []
    for target, entry in sorted(found.items()):
        below = sorted((p for p in pages if p == target or p.startswith(target + "/")))
        links.append({
            "source": entry["source"],
            "target": target,
            "url": f"https://{CONNECT_HOST}{target}",
            "names": entry["names"],
            "pages": [{"path": p, "url": pages[p]["url"], "lastmod": pages[p]["lastmod"]} for p in below],
        })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = {
        "fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "sources": LINK_SOURCES,
        "connect_sitemap": CONNECT_SITEMAP,
        "links": links,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"Saved {len(links)} Connect links covering {sum(len(l['pages']) for l in links)} pages")


if __name__ == "__main__":
    main()
