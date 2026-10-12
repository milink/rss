#!/usr/bin/env python3
"""Generuje RSS 2.0 feed z neoficiálního Sreality API.

Adresu API lze přepsat proměnnou prostředí SREALITY_API_URL
(zkopírovanou ze záložky Network v prohlížeči). Výstup: docs/feed.xml
"""
import os
import sys
import json
import hashlib
from xml.sax.saxutils import escape

import requests

# !! Neověřeno: parametry a kód kraje je potřeba zkontrolovat (viz README).
DEFAULT_API_URL = (
    "https://www.sreality.cz/api/cs/v2/estates"
    "?category_main_cb=2"          # 1 byty, 2 domy, 3 pozemky
    "&category_type_cb=1"          # 1 prodej, 2 pronájem
    "&locality_region_id=19"       # kraj - OVĚŘIT (Zlínský)
    "&czk_price_summary_order2=100000%7C2510000"  # cena od|do
    "&per_page=60&sort=0"
)
API_URL = os.environ.get("SREALITY_API_URL", DEFAULT_API_URL)
OUT_FILE = os.environ.get("OUT_FILE", "docs/feed.xml")
FEED_TITLE = os.environ.get("FEED_TITLE", "Sreality – domy na prodej, Zlínský kraj")
SEARCH_URL = os.environ.get("SEARCH_URL", "https://www.sreality.cz/hledani/prodej/domy/zlinsky-kraj")

TYPE = {1: "prodej", 2: "pronajem", 3: "drazby"}
MAIN = {1: "byt", 2: "dum", 3: "pozemek", 4: "komercni", 5: "ostatni"}


def detail_url(e):
    seo = e.get("seo") or {}
    t = TYPE.get(seo.get("category_type_cb"), "prodej")
    m = MAIN.get(seo.get("category_main_cb"), "dum")
    loc = seo.get("locality") or "x"
    return f"https://www.sreality.cz/detail/{t}/{m}/x/{loc}/{e['hash_id']}"


def image_of(e):
    links = (e.get("_links") or {}).get("images") or []
    if links and isinstance(links[0], dict) and links[0].get("href"):
        href = links[0]["href"]
        return ("https:" + href) if href.startswith("//") else href
    return None


def fetch():
    r = requests.get(
        API_URL,
        headers={"User-Agent": "Mozilla/5.0 (rss-bot)", "Accept": "application/json"},
        timeout=30,
    )
    if r.status_code != 200:
        sys.exit(f"API vrátilo HTTP {r.status_code}. Začátek odpovědi:\n{r.text[:500]}")
    try:
        data = r.json()
    except ValueError:
        sys.exit(f"Odpověď není JSON (možná blokace). Začátek:\n{r.text[:500]}")
    estates = (data.get("_embedded") or {}).get("estates")
    if not estates:
        sys.exit("V odpovědi chybí _embedded.estates - API se asi změnilo. "
                 f"Klíče nejvyšší úrovně: {list(data.keys())}")
    return estates


def build(estates):
    items = []
    for e in estates:
        price = e.get("price")
        price_txt = f"{price:,}".replace(",", " ") + " Kč" if isinstance(price, int) and price else "cena v RK"
        link = detail_url(e)
        img = image_of(e)
        desc = f"{e.get('locality', '')} – {price_txt}"
        if img:
            desc = f'<img src="{img}"/><br/>' + desc
        items.append(
            "  <item>\n"
            f"    <title>{escape(str(e.get('name', '')))} – {escape(price_txt)}</title>\n"
            f"    <link>{escape(link)}</link>\n"
            f'    <guid isPermaLink="false">sreality-{e["hash_id"]}</guid>\n'
            f"    <description><![CDATA[{desc}]]></description>\n"
            "  </item>"
        )
    # bez lastBuildDate, aby se soubor neměnil, dokud nepřibude/neubude inzerát
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>\n'
        f"  <title>{escape(FEED_TITLE)}</title>\n"
        f"  <link>{escape(SEARCH_URL)}</link>\n"
        "  <description>Inzeráty ze Sreality.cz</description>\n"
        + "\n".join(items)
        + "\n</channel></rss>\n"
    )


def main():
    estates = fetch()
    print(f"Nalezeno inzerátů: {len(estates)}")
    for e in estates[:3]:  # kontrola, že filtr (kraj, cena) sedí
        print(" -", e.get("name"), "|", e.get("locality"), "|", e.get("price"))
    xml = build(estates)
    os.makedirs(os.path.dirname(OUT_FILE) or ".", exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(xml)
    print("Zapsáno:", OUT_FILE)


if __name__ == "__main__":
    main()
