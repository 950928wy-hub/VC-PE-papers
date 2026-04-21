#!/usr/bin/env python3
"""
SSRN 工作论文抓取脚本
通过 SSRN API 获取最新工作论文
SSRN 是免费平台，专注预印本和working papers
"""

import json
import os
import re
import time
import random
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== 配置区 ====================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(DATA_DIR, "ssrn_papers.json")

# SSRN 相关领域关键词（用于筛选相关工作论文）
SSRN_KEYWORDS = {
    "finance": [
        "venture capital", "private equity", "ipo", "initial public offering",
        "merger", "acquisition", "financing", "investment", "asset pricing",
        "corporate finance", "banking", "financial intermediation"
    ],
    "strategy": [
        "strategy", "strategic management", "competitive advantage",
        "innovation", "entrepreneurship", "startup", "technology"
    ],
    "accounting": [
        "accounting", "earnings", "financial reporting", "audit"
    ],
    "economics": [
        "economics", "economic growth", "development", "regulation", "antitrust"
    ]
}

HEADERS = {
    "User-Agent": "Academic-Paper-Feed/1.0 (mailto:yanyan@example.com)",
    "Accept": "application/json",
}

MIN_DELAY = 1.0
MAX_DELAY = 2.0


# ==================== SSL / 请求配置 ====================

def make_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=1, pool_maxsize=1)
    session.mount("https://", adapter)
    return session


_session = make_session()


def random_delay():
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    print(f"    ⏳ 等待 {delay:.1f}s ...")
    time.sleep(delay)


# ==================== 工具函数 ====================

def load_existing():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            papers = json.load(f)
        print(f"  📂 已加载 {len(papers)} 篇已有论文")
        return {p.get("ssrn_id") or p.get("title", ""): p for p in papers}
    return {}


def save_papers(papers_dict):
    papers_list = list(papers_dict.values())
    papers_list.sort(
        key=lambda p: (p.get("date", "")),
        reverse=True
    )
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(papers_list, f, ensure_ascii=False, indent=2)
    print(f"  💾 已保存 {len(papers_list)} 篇 SSRN 论文")


def clean_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_relevant_paper(title, abstract, keywords):
    """判断论文是否与目标领域相关"""
    text = f"{title} {abstract} {' '.join(keywords)}".lower()
    
    # 检查是否匹配任意关键词类别
    for category, kws in SSRN_KEYWORDS.items():
        if any(kw.lower() in text for kw in kws):
            return True, category
    return False, None


# ==================== SSRN API ====================

def fetch_ssrn_papers(days_back=30, max_papers=500):
    """
    通过 CrossRef API 获取 SSRN 上的预印本
    或者通过 RSS feed 获取最新论文
    """
    all_papers = []
    
    # CrossRef 有 SSRN 作为 publisher 的论文
    # 或者使用 NBER (National Bureau of Economic Research) 作为补充
    publishers = [
        {"name": "SSRN", "publisher": "Elsevier"},
        {"name": "NBER", "publisher": "NBER"},
    ]
    
    # 计算日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    for pub in publishers:
        print(f"\n📡 获取 {pub['name']} 工作论文...")
        
        # 使用 CrossRef 的 filter 功能
        url = "https://api.crossref.org/works"
        params = {
            "query": "working paper OR preprint",
            "filter": f"publisher-name:{pub['name']}",
            "rows": 100,
            "sort": "published-date",
            "order": "desc",
            "mailto": "yanyan@example.com",
        }
        
        try:
            resp = _session.get(url, params=params, headers=HEADERS, timeout=20)
            
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("message", {}).get("items", [])
                print(f"    获取到 {len(items)} 篇")
                all_papers.extend(items)
            else:
                print(f"    HTTP {resp.status_code}")
        except Exception as e:
            print(f"    ❌ 错误: {e}")
        
        random_delay()
    
    return all_papers


def fetch_ssrn_by_rss():
    """
    通过 SSRN 的 RSS feed 获取最新论文
    SSRN 提供多种 feed，涵盖不同领域
    """
    feeds = [
        "https://www.ssrn.com/rss/finance.xml",
        "https://www.ssrn.com/rss/mgmt.xml",
        "https://www.ssrn.com/rss/econ.xml",
    ]
    
    all_items = []
    
    for feed_url in feeds:
        print(f"\n📡 获取 RSS: {feed_url.split('/')[-1]}")
        
        try:
            resp = _session.get(feed_url, headers=HEADERS, timeout=20)
            
            if resp.status_code == 200:
                import feedparser
                feed = feedparser.parse(resp.text)
                
                for entry in feed.entries[:50]:  # 每类取最新 50 篇
                    all_items.append(entry)
                
                print(f"    获取到 {len(feed.entries)} 篇")
            else:
                print(f"    HTTP {resp.status_code}")
        except ImportError:
            print("    需要安装 feedparser: pip install feedparser")
            break
        except Exception as e:
            print(f"    ❌ 错误: {e}")
        
        random_delay()
    
    return all_items


def parse_ssrn_item(item, source="SSRN"):
    """解析 SSRN 论文条目"""
    article = {
        "fetched_at": datetime.now().isoformat(),
        "source": source,
        "paper_type": "working_paper",
    }
    
    # 尝试不同字段
    if hasattr(item, 'get'):  # dict 格式 (CrossRef)
        article["ssrn_id"] = item.get("DOI", "").replace("10.2139/ssrn.", "")
        article["doi"] = item.get("DOI", "")
        
        if item.get("DOI"):
            article["url"] = f"https://dx.doi.org/{item['DOI']}"
        else:
            article["url"] = item.get("URL", "")
        
        titles = item.get("title", [])
        article["title"] = clean_html(titles[0]) if titles else ""
        
        authors = []
        for author in item.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            name = " ".join(filter(None, [given, family])).strip()
            if name:
                authors.append(name)
        article["authors"] = authors
        
        date_parts = (
            item.get("published-print", {})
            or item.get("published-online", {})
            or item.get("created", {})
        ).get("date-parts", [[]])
        if date_parts and date_parts[0]:
            article["year"] = str(date_parts[0][0])
            if len(date_parts[0]) > 1:
                article["month"] = str(date_parts[0][1])
        
        abstract = item.get("abstract", "")
        if abstract:
            article["abstract"] = clean_html(abstract)
        else:
            article["abstract"] = ""
        
        keywords = []
        for kw_list in item.get("subject", []):
            if isinstance(kw_list, list):
                keywords.extend(kw_list)
            elif isinstance(kw_list, str):
                keywords.append(kw_list)
        article["keywords"] = [clean_html(k) for k in keywords[:10] if clean_html(k)]
        
        article["journal"] = item.get("container-title", [source])[0] if item.get("container-title") else source
        
    else:  # RSS feed 格式
        article["ssrn_id"] = re.search(r'id=(\d+)', str(item.get("id", ""))).group(1) if re.search(r'id=(\d+)', str(item.get("id", ""))) else ""
        article["title"] = clean_html(item.get("title", ""))
        article["abstract"] = clean_html(item.get("summary", item.get("description", "")))
        article["url"] = item.get("link", "")
        
        if hasattr(item, "author"):
            article["authors"] = [item.author]
        else:
            article["authors"] = []
        
        if hasattr(item, "published"):
            try:
                from email.utils import parsedate
                import time
                t = parsedate(item.published)
                if t:
                    article["year"] = str(t[0])
            except:
                pass
    
    return article


# ==================== 主函数 ====================

def scrape_ssrn(days_back=30, max_papers=500):
    print("=" * 60)
    print("SSRN 工作论文抓取")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"回溯: {days_back} 天")
    print("=" * 60)
    
    existing = load_existing()
    new_count = 0
    skip_count = 0
    
    # 方法 1: 通过 CrossRef API
    print("\n📡 方式一: CrossRef API")
    items = fetch_ssrn_papers(days_back, max_papers)
    
    for raw_item in items:
        article = parse_ssrn_item(raw_item, "CrossRef")
        key = article.get("ssrn_id") or article.get("doi") or article.get("title", "")
        
        if not key:
            continue
        
        if key in existing:
            skip_count += 1
            continue
        
        # 检查相关性
        is_relevant, category = is_relevant_paper(
            article.get("title", ""),
            article.get("abstract", ""),
            article.get("keywords", [])
        )
        
        if is_relevant:
            article["relevance_category"] = category
            existing[key] = article
            new_count += 1
            print(f"    ✅ [{category}] {article['title'][:50]}")
        else:
            skip_count += 1
    
    print(f"\n{'=' * 60}")
    print(f"抓取完成！新增 {new_count} 篇 | 跳过 {skip_count} 篇 | 共 {len(existing)} 篇")
    print("=" * 60)
    
    save_papers(existing)
    
    return existing


# ==================== 入口 ====================

if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    max_p = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    scrape_ssrn(days_back=days, max_papers=max_p)
