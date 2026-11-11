"""Read the live title of each page in the sitemaps and save them to data/titles.json.

Run by the GitHub Action after fetch_sitemap.py and fetch_connect.py.
- Daily: only pages that are new, or whose sitemap "last updated" date has changed since their title was read.
- Monthly (the 1st, Sydney time) or when FULL_TITLE_CHECK=1: every page.
Requests are spaced DELAY seconds apart so a full check takes about 30 minutes.

The title used is the page's main heading (<h1>). If there is none, the browser tab title (<title>)
is used with the site name removed. Pages that return an error or redirect elsewhere are recorded.
"""
import datetime
import json
import os
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

DELAY = 1.6
OUT = "data/titles.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CCA-sitemap-explorer; +https://cca-experiments.github.io/sitemap-explorer/)"}
SUFFIXES = [" | Cancer Council Australia", " | Cancer Council", " | Cancer Connect", " - Cancer Council Australia"]


class TitleParser(HTMLParser):
    """Collect the <title> and the first <h1> that is not inside a navigation menu."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = self.in_h1 = False
        self.nav = 0
        self.title, self.h1, self.done_h1 = "", "", False

    def handle_starttag(self, tag, attrs):
        if tag == "nav":
            self.nav += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "h1" and not self.done_h1 and not self.nav:
            self.in_h1 = True

    def handle_endtag(self, tag):
        if tag == "nav" and self.nav:
            self.nav -= 1
        elif tag == "title":
            self.in_title = False
        elif tag == "h1" and self.in_h1:
            self.in_h1 = False
            self.done_h1 = bool(tidy(self.h1))

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_h1:
            self.h1 += data


def tidy(text):
    return " ".join((text or "").split())


def clean_title(title):
    t = tidy(title)
    for s in SUFFIXES:
        if t.endswith(s):
            t = t[: -len(s)]
    return t.strip()


def read_page(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            final = r.geturl()
            html = r.read(600_000).decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        return {"status": e.code, "problem": f"HTTP {e.code}"}
    except Exception as e:  # network errors, timeouts
        return {"status": None, "problem": f"Could not load ({type(e).__name__})"}
    p = TitleParser()
    p.feed(html)
    h1, tab = tidy(p.h1), clean_title(p.title)
    out = {"status": status, "title": h1 if len(h1) > 2 else tab, "tab_title": tab}
    if final.rstrip("/") != url.rstrip("/"):
        out["problem"] = "Redirects"
        out["redirects_to"] = final
    return out


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main():
    pages = {p["url"]: p.get("lastmod") for p in load("data/sitemap.json", {"pages": []})["pages"]}
    for link in load("data/connect.json", {"links": []})["links"]:
        for p in link["pages"]:
            pages[p["url"]] = p.get("lastmod")
    cache = load(OUT, {"pages": {}}).get("pages", {})

    sydney_today = datetime.datetime.now(ZoneInfo("Australia/Sydney")).date()
    full = os.environ.get("FULL_TITLE_CHECK") == "1" or sydney_today.day == 1
    todo = [u for u in pages if full or u not in cache or cache[u].get("lastmod_seen") != pages[u]]
    print(f"{'Full' if full else 'Daily'} title check: {len(todo)} of {len(pages)} pages")

    def save():
        kept = {u: cache[u] for u in pages if u in cache}  # drop pages no longer in any sitemap
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump({"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                       "pages": kept}, f, ensure_ascii=False, indent=0, sort_keys=True)

    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    for i, url in enumerate(todo, 1):
        result = read_page(url)
        old = cache.get(url, {})
        if "title" not in result and old.get("title"):
            result["title"] = old["title"]  # keep the last good title if the page could not be read
        result.update({"checked": now, "lastmod_seen": pages[url]})
        cache[url] = result
        if i % 50 == 0:
            save()
            print(f"  {i}/{len(todo)}")
        time.sleep(DELAY)
    save()
    problems = sum(1 for u in pages if cache.get(u, {}).get("problem"))
    print(f"Done. {problems} pages with a problem (error or redirect).")


if __name__ == "__main__":
    main()
