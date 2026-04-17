#!/usr/bin/env python3
"""小规模测试 CrossRef API 抓取"""
import json, os, re, time, random, ssl
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HEADERS = {"User-Agent": "VC-PE-Test/1.0 (mailto:test@example.com)", "Accept": "application/json"}
PER_PAGE = 20

def make_session():
    s = requests.Session()
    r = Retry(total=2, backoff_factor=0.5, allowed_methods=["GET"])
    s.mount("https://", HTTPAdapter(max_retries=r, pool_connections=1, pool_maxsize=1))
    return s
_s = make_session()

def clean_html(text):
    if not text: return ""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()

JOURNALS = [
    {"name": "Journal of Corporate Finance",        "issn": "0929-1199"},
    {"name": "Journal of Business Venturing",        "issn": "0883-9026"},
    {"name": "Journal of Banking & Finance",          "issn": "0378-4266"},
    {"name": "Journal of Development Economics",       "issn": "0304-3878"},
    {"name": "World Development",                      "issn": "0305-750X"},
]

for j in JOURNALS:
    issn = j["issn"]
    name = j["name"]
    print(f"\n📡 {name} ({issn})")
    url = f"https://api.crossref.org/journals/{issn}/works"
    params = {"rows": PER_PAGE, "sort": "created", "order": "desc"}
    try:
        resp = _s.get(url, params=params, headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"    ❌ 网络错误: {e}")
        continue
    print(f"    HTTP {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("message", {}).get("items", [])
        total = data.get("message", {}).get("total-results", 0)
        print(f"    总计 {total} 篇，获取 {len(items)} 条")
        for item in items[:3]:
            title = clean_html(item.get("title", [""])[0])[:60]
            doi = item.get("DOI", "")
            year = (item.get("published-print") or item.get("published-online") or {}).get("date-parts", [[None]])[0][0]
            authors = [" ".join(filter(None, [a.get("given",""), a.get("family","")])) for a in item.get("author",[])][:2]
            print(f"      [{year}] {title}")
            sep = ", "
            print(f"             {sep.join(authors)}")
    else:
        print(f"    失败: {resp.text[:150]}")
    time.sleep(random.uniform(1, 2))
