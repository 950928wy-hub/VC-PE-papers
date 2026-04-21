#!/usr/bin/env python3
"""
SSRN 工作论文抓取脚本 — VC/PE 专注版
专门针对风险投资、创业投资、私募股权、引导基金领域
通过 CrossRef API + RSS feed 获取最新工作论文
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

# ==================== VC/PE 主题关键词配置 ====================
# SSRN 论文筛选关键词 - 专注风险投资/私募股权/引导基金

SSRN_VC_PE_KEYWORDS = {
    # 核心 VC/PE 术语
    "venture capital": [
        "venture capital", "vc fund", "vc investment", "vc backed",
        "venture capitalist", "vc deal", "vc financing", "vc industry",
        "startup funding", "early-stage investment", "seed investment",
        "seed capital", "angel investor", "angel investment",
        "pre-seed", "series a", "series b", "series c",
        "创业投资", "风险投资", "创投", "天使投资",
    ],
    "private equity": [
        "private equity", "pe fund", "pe investment", "pe deal",
        "pe buyout", "buyout", "leveraged buyout", "lbo",
        "management buyout", "mbo", "mbo", "secondary market",
        "growth equity", "mezzanine", "distressed debt",
        "私募股权", "PE", "杠杆收购", "并购基金",
    ],
    "government guided fund": [
        "government venture capital", "government guided fund",
        "guided fund", "policy fund", "policy-based fund",
        "government investment", "state-owned investment",
        "引导基金", "政府引导基金", "政府创业投资引导基金",
        "政府出资", "政策性基金", "产业基金",
    ],
    "fund structure": [
        "limited partner", "lp", "general partner", "gp",
        "fund manager", "fundraising", "capital commitment",
        "fund of funds", "fund performance", "fund returns",
        "carry", "j-curve", "capital call",
        "LP", "GP", "基金管理人", "募资",
    ],
    "exit strategy": [
        "ipo", "initial public offering", "exit strategy", "exit",
        "acquisition", "merger", "trade sale", "secondary sale",
        "ipo pricing", "ipo underpricing", "listing",
        "上市", "退出", "并购", "首次公开募股",
    ],
    "corporate venture": [
        "corporate venture capital", "cvc", "corporate vc",
        "strategic investment", "corporate entrepreneurship",
        "corporate innovation", "open innovation",
        "公司创业投资", "企业风险投资", "战略投资",
    ],
    "entrepreneurship": [
        "entrepreneurship", "entrepreneurial", "entrepreneur",
        "new venture", "technology startup", "high-tech venture",
        "spin-off", "spinout", "spinout",
        "innovation", "technological innovation",
        "创业", "企业家精神", "技术创新", "初创企业",
    ],
    "performance": [
        "fund performance", "investment performance", "portfolio performance",
        "irr", "internal rate of return", "npv", "net present value",
        "return on investment", "roi", "investment return",
        "carry", "performance attribution",
        "基金业绩", "投资回报", "收益率", "IRR",
    ],
}

# 合并所有关键词为列表
ALL_SSRN_KEYWORDS = []
for category, kws in SSRN_VC_PE_KEYWORDS.items():
    ALL_SSRN_KEYWORDS.extend(kws)

# 需要排除的非相关领域
EXCLUDE_KEYWORDS = [
    "medical", "medicine", "healthcare", "biology", "biochemistry",
    "physics", "chemistry", "engineering", "materials",
    "agriculture", "environmental science", "ecology", "climate",
    "genetics", "neuroscience", "bioinformatics", "psychology",
]

HEADERS = {
    "User-Agent": "VC-PE-Paper-Feed/4.0 (mailto:yanyan@example.com)",
    "Accept": "application/json",
}

MIN_DELAY = 1.0
MAX_DELAY = 2.0

# 抓取年份范围
START_YEAR = 2000


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
        return {p.get("ssrn_id") or p.get("doi") or p.get("title", ""): p for p in papers}
    return {}


def save_papers(papers_dict):
    papers_list = list(papers_dict.values())
    papers_list.sort(
        key=lambda p: (p.get("year", "0"), p.get("date", "")),
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


def is_vc_pe_related(title, abstract, keywords):
    """
    判断 SSRN 论文是否与 VC/PE 主题相关
    返回: (是否相关, 匹配的主题标签列表)
    """
    text = f"{title} {abstract} {' '.join(keywords) if keywords else ''}".lower()

    # 首先检查是否应该排除
    for excl in EXCLUDE_KEYWORDS:
        if excl in text:
            return False, []

    # 检查是否匹配 VC/PE 关键词
    matched_tags = []
    for category, kws in SSRN_VC_PE_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in text:
                if category not in matched_tags:
                    matched_tags.append(category)
                break  # 一个类别只需匹配一次

    return len(matched_tags) > 0, matched_tags


# ==================== CrossRef API ====================

def fetch_ssrn_by_crossref(days_back=365, max_papers=500):
    """
    通过 CrossRef API 获取 SSRN 上的预印本
    """
    all_papers = []

    publishers = [
        {"name": "Elsevier", "query": "SSRN"},
    ]

    # 计算日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    for pub in publishers:
        print(f"\n📡 获取 {pub['name']} 工作论文 (回溯 {days_back} 天)...")

        url = "https://api.crossref.org/works"
        params = {
            "query": "venture capital OR private equity OR entrepreneurship",
            "filter": f"publisher-name:{pub['name']},from-pub-date:{start_date.strftime('%Y-%m-%d')}",
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


def fetch_nber_papers(days_back=365, max_papers=300):
    """
    获取 NBER 工作论文（经济领域的重要预印本）
    """
    all_papers = []

    # NBER 是经济研究的重要来源
    print(f"\n📡 获取 NBER 工作论文 (回溯 {days_back} 天)...")

    url = "https://api.crossref.org/works"
    params = {
        "query": "venture capital OR private equity OR entrepreneurship OR startup",
        "filter": f"publisher-name:NBER,from-pub-date:{(datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')}",
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

    return all_papers


def parse_ssrn_item(item, source="SSRN"):
    """解析 SSRN/NBER 论文条目"""
    article = {
        "fetched_at": datetime.now().isoformat(),
        "source": source,
        "paper_type": "working_paper",
    }

    # DOI 处理
    doi = item.get("DOI", "")
    article["doi"] = doi

    # SSRN ID 提取
    if "ssrn" in doi.lower():
        ssrn_id = doi.replace("10.2139/ssrn.", "").replace("10.2139/ssrn", "")
        article["ssrn_id"] = ssrn_id
        article["url"] = f"https://dx.doi.org/{doi}"
    elif doi:
        article["ssrn_id"] = doi
        article["url"] = f"https://dx.doi.org/{doi}"
    else:
        article["url"] = item.get("URL", "")

    # 标题
    titles = item.get("title", [])
    article["title"] = clean_html(titles[0]) if titles else ""

    # 作者
    authors = []
    for author in item.get("author", []):
        given = author.get("given", "")
        family = author.get("family", "")
        name = " ".join(filter(None, [given, family])).strip()
        if name:
            authors.append(name)
    article["authors"] = authors

    # 发表日期
    date_parts = (
        item.get("published-print", {})
        or item.get("published-online", {})
        or item.get("created", {})
    ).get("date-parts", [[]])
    if date_parts and date_parts[0]:
        article["year"] = str(date_parts[0][0])
        if len(date_parts[0]) > 1:
            article["month"] = str(date_parts[0][1])
        if len(date_parts[0]) > 2:
            article["day"] = str(date_parts[0][2])
        article["date"] = "-".join(str(x) for x in date_parts[0][:3])

    # 摘要
    abstract = item.get("abstract", "")
    if abstract:
        article["abstract"] = clean_html(abstract)
    else:
        article["abstract"] = ""

    # 关键词
    keywords = []
    for kw_list in item.get("subject", []):
        if isinstance(kw_list, list):
            keywords.extend(kw_list)
        elif isinstance(kw_list, str):
            keywords.append(kw_list)
    article["keywords"] = [clean_html(k) for k in keywords[:10] if clean_html(k)]

    # 期刊/来源
    if item.get("container-title"):
        article["journal"] = item["container-title"][0]
    else:
        article["journal"] = source

    # 引用次数
    article["cited_by"] = item.get("is-referenced-by-count", 0)

    return article


# ==================== 主函数 ====================

def scrape_ssrn(days_back=365, max_papers=500):
    print("=" * 60)
    print("VC/PE SSRN 工作论文抓取")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"回溯: {days_back} 天")
    print("专注领域: 风险投资 | 创业投资 | 私募股权 | 引导基金")
    print("=" * 60)

    existing = load_existing()
    new_count = 0
    skip_count = 0
    filtered_count = 0

    # 方法 1: 通过 CrossRef API 获取 SSRN
    print("\n📡 方式一: CrossRef API - SSRN")
    ssrn_items = fetch_ssrn_by_crossref(days_back, max_papers)

    # 方法 2: 获取 NBER (补充)
    print("\n📡 方式二: CrossRef API - NBER")
    nber_items = fetch_nber_papers(days_back, max_papers // 2)

    all_items = ssrn_items + nber_items
    print(f"\n总计获取 {len(all_items)} 条原始记录，开始筛选...")

    for raw_item in all_items:
        article = parse_ssrn_item(raw_item, "SSRN/NBER")
        key = article.get("ssrn_id") or article.get("doi") or article.get("title", "")

        if not key:
            continue

        # 检查年份
        try:
            year = int(article.get("year", 0))
            if year < START_YEAR:
                filtered_count += 1
                continue
        except (ValueError, TypeError):
            pass

        # 检查是否已存在
        if key in existing:
            skip_count += 1
            continue

        if not article.get("title"):
            continue

        # 检查是否与 VC/PE 相关
        is_related, matched_tags = is_vc_pe_related(
            article.get("title", ""),
            article.get("abstract", ""),
            article.get("keywords", [])
        )

        if is_related:
            article["vc_pe_tags"] = matched_tags
            existing[key] = article
            new_count += 1
            print(f"    ✅ [{article.get('year', '?')}] {article['title'][:50]} | {', '.join(matched_tags[:2])}")
        else:
            filtered_count += 1

    print(f"\n{'=' * 60}")
    print(f"抓取完成！")
    print(f"  新增 VC/PE 相关: {new_count} 篇")
    print(f"  跳过已有: {skip_count} 篇")
    print(f"  过滤掉不相关: {filtered_count} 篇")
    print(f"  共 {len(existing)} 篇")
    print("=" * 60)

    save_papers(existing)

    return existing


# ==================== 入口 ====================

if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 365
    max_p = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    scrape_ssrn(days_back=days, max_papers=max_p)
