"""Download the site's XML sitemap and save it as data/sitemap.json.

Run by the GitHub Action in .github/workflows/update-sitemap.yml.
Handles a plain sitemap or a sitemap index (a sitemap that lists other sitemaps).
"""
import datetime
import json
import urllib.request
import xml.etree.ElementTree as ET

SITEMAP_URL = "https://www.cancer.org.au/sitemap.xml"
OUT = "data/sitemap.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CCA-sitemap-explorer; +https://cca-experiments.github.io/sitemap-explorer/)"}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def local(tag):
    return tag.rsplit("}", 1)[-1]


def read(url, pages, seen):
    if url in seen:
        return
    seen.add(url)
    root = ET.fromstring(fetch(url))
    if local(root.tag) == "sitemapindex":
        for sm in root:
            loc = next((c.text.strip() for c in sm if local(c.tag) == "loc" and c.text), None)
            if loc:
                read(loc, pages, seen)
        return
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
            pages[loc] = lastmod


def main():
    pages = {}
    read(SITEMAP_URL, pages, set())
    if not pages:
        raise SystemExit("No URLs found in the sitemap; keeping the previous data.")
    data = {
        "source": SITEMAP_URL,
        "fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "count": len(pages),
        "pages": [{"url": u, "lastmod": pages[u]} for u in sorted(pages)],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("{\n")
        f.write(f'"source": {json.dumps(data["source"])},\n"fetched": {json.dumps(data["fetched"])},\n"count": {data["count"]},\n"pages": [\n')
        f.write(",\n".join(json.dumps(p, ensure_ascii=False) for p in data["pages"]))
        f.write("\n]\n}\n")
    print(f"Saved {len(pages)} pages")


if __name__ == "__main__":
    main()
