# Sitemap Explorer

An interactive tree of every page in the cancer.org.au XML sitemap, coloured by when each page was last updated.

- Live tool: https://cca-experiments.github.io/sitemap-explorer/
- Everything comes from the XML sitemaps and the live pages. No spreadsheet is needed.

## How the data updates

The "Update sitemap data" GitHub Action runs every morning at about 6am Sydney time:

1. `scripts/fetch_sitemap.py` downloads the cancer.org.au XML sitemap into `data/sitemap.json`.
2. `scripts/fetch_connect.py` finds links from the Types of Cancer page to Cancer Connect, and saves the linked Connect pages into `data/connect.json`.
3. `scripts/fetch_titles.py` reads each page's main heading into `data/titles.json`:
   - daily: only new pages, and pages whose sitemap date has changed
   - on the 1st of each month: every page
   - requests are 1.6 seconds apart, so a full check takes about 30 minutes
   - requests identify themselves as "CCA-sitemap-explorer"

To run it now, open the Actions tab, choose "Update sitemap data" and click "Run workflow". Tick "Re-read every page title" for a full title check.

Companion tool built from the IA spreadsheet: https://cca-experiments.github.io/ia-explorer/
