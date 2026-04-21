#!/usr/bin/env python3
"""
VC/PE 论文抓取脚本 v3 — 基于 CrossRef API
免费、无需密钥，通过 CrossRef 获取期刊最新论文元数据
"""

import json
import os
import re
import time
import random
import ssl
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== 配置区 ====================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(DATA_DIR, "elsevier_papers.json")
ARCHIVE_FILE = os.path.join(DATA_DIR, "elsevier_archive.json")

# 导师指定的权威期刊列表（按领域分类）
# Finance / Economic / Accounting / Strategy & Organization / Management

JOURNALS = {
    "Finance": [
        {"name": "Journal of Finance", "issn": "0022-1082"},
        {"name": "Journal of Financial and Quantitative Analysis", "issn": "0022-1099"},
        {"name": "Journal of Financial Economics", "issn": "0304-405X"},
        {"name": "Review of Financial Studies", "issn": "0893-9454"},
        {"name": "Review of Finance", "issn": "1573-7179"},
        {"name": "Journal of Banking and Finance", "issn": "0378-4266"},
        {"name": "Journal of Corporate Finance", "issn": "0929-1199"},
    ],
    "Economic": [
        {"name": "Journal of Economic Literature", "issn": "0022-0515"},
        {"name": "Journal of Economic Perspectives", "issn": "0895-3309"},
        {"name": "Journal of Economics and Management Strategy", "issn": "1058-6407"},
    ],
    "Accounting": [
        {"name": "Accounting Review", "issn": "0001-4826"},
        {"name": "Contemporary Accounting Research", "issn": "0829-3148"},
        {"name": "Journal of Accounting and Economics", "issn": "0165-4101"},
        {"name": "Journal of Accounting Research", "issn": "0021-8456"},
        {"name": "Review of Accounting Studies", "issn": "1380-6653"},
    ],
    "Strategy & Organization": [
        {"name": "Academy of Management Journal", "issn": "0001-4273"},
        {"name": "Academy of Management Review", "issn": "0363-7425"},
        {"name": "Strategic Management Journal", "issn": "0142-2303"},
        {"name": "Harvard Business Review", "issn": "0017-8012"},
        {"name": "Organization Science", "issn": "1047-7039"},
        {"name": "Journal of International Business Studies", "issn": "0047-2506"},
        {"name": "Journal of Business Venturing", "issn": "0883-9026"},
        {"name": "Journal of Management", "issn": "0149-2063"},
    ],
    "Management": [
        {"name": "Management Science", "issn": "0025-1909"},
    ],
}

# 扁平化期刊列表供抓取使用
VC_PE_JOURNALS = []
for category, journals in JOURNALS.items():
    for j in journals:
        VC_PE_JOURNALS.append({**j, "category": category})

# 请求头 — polite pool（更低的限速）
# ==================== VC/PE 主题关键词配置 ====================
# 用于在抓取时过滤出与"风险投资/创业投资/私募股权"相关的论文
# 中英文关键词全覆盖

VC_PE_KEYWORDS = [
    # 英文核心关键词
    "venture capital", "vc fund", "venture fund", "venture investment",
    "private equity", "pe fund", "buyout fund", "lbo fund",
    "entrepreneurial finance", "startup finance", "new venture",
    "angel investment", "angel investor", "angel fund",
    "corporate venture", "corporate venture capital", "cvc",
    "government venture", "government guidance fund",
    "guide fund", "guidance fund",
    "fund of funds", "fund-of-funds",
    "limited partner", "lp investor", "lp commitment",
    "general partner", "gp management",
    "pe buyout", "leveraged buyout", "lbo",
    "mezzanine financing", "growth equity",
    "portfolio company", "deal sourcing", "deal screening",
    "investment screening", "due diligence",
    "exit strategy", "ipo", "initial public offering",
    "venture exit", "pe exit", "acquisition exit",
    "investment performance", "fund performance", "irr", "return",
    "capital commitment", "capital call", "dry powder",
    "co-investment", "syndicate", "investment syndicate",
    "deal flow", "transaction", "m&a",
    "entrepreneurship", "entrepreneurial", "startup", "nascent venture",
    "innovation", "technological innovation",
    # 缩写/简称
    "vc", "pe", "cvc", "cve",
]

# 排除关键词（排除不相关的领域）
EXCLUDE_KEYWORDS = [
    "medical", "medicine", "healthcare", "biology", "biochemistry",
    "physics", "chemistry", "engineering", "materials",
    "agriculture", "environmental science", "ecology", "climate",
    "education", "psychology", "sociology",
    "agricultural economics", "health economics",
]

HEADERS = {
    "User-Agent": "VC-PE-Paper-Feed/3.0 (mailto:yanyan@example.com)",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 延迟配置（秒）
MIN_DELAY = 1.5
MAX_DELAY = 3.5

# CrossRef 每请求最多返回条数
PER_PAGE = 100

# 抓取年份范围
START_YEAR = 2000


# ==================== SSL / 请求配置 ====================

def make_session():
    """创建带重试的 HTTP Session"""
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
    """加载已有数据，避免重复抓取"""
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            papers = json.load(f)
        print(f"  📂 已加载 {len(papers)} 篇已有论文")
        return {p.get("doi") or p.get("title", ""): p for p in papers}
    return {}


def save_papers(papers_dict):
    papers_list = list(papers_dict.values())
    papers_list.sort(
        key=lambda p: (p.get("year", "0"), p.get("fetched_at", "")),
        reverse=True
    )
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(papers_list, f, ensure_ascii=False, indent=2)
    print(f"  💾 已保存 {len(papers_list)} 篇论文")


def clean_html(text):
    """移除 HTML 标签"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


# ==================== CrossRef API ====================

def fetch_journal_works(issn, journal_name, max_rows=200):
    """
    通过 CrossRef API 获取某期刊的最新论文
    每次请求 PER_PAGE 条，按发表日期降序，
    通过游标（cursor）或分页（offset）翻页
    只获取 START_YEAR 之后的论文
    """
    url = f"https://api.crossref.org/journals/{issn}/works"
    all_items = []
    fetched = 0

    params = {
        "rows": PER_PAGE,
        "sort": "published-date",
        "order": "desc",
        "mailto": "yanyan@example.com",
        # 只获取 2000 年之后的论文，减少无效请求
        "filter": f"from-pub-date:{START_YEAR}",
    }

    while fetched < max_rows:
        try:
            resp = _session.get(url, params=params, headers=HEADERS, timeout=20)
        except Exception as e:
            print(f"    ❌ 网络错误: {e}")
            break

        if resp.status_code == 400:
            # sort 参数不支持，尝试不用 sort
            params.pop("sort", None)
            params.pop("order", None)
            try:
                resp = _session.get(url, params=params, headers=HEADERS, timeout=20)
            except Exception as e:
                print(f"    ❌ 重试失败: {e}")
                break

        if resp.status_code != 200:
            print(f"    ❌ HTTP {resp.status_code}: {resp.text[:80]}")
            break

        try:
            data = resp.json()
        except Exception:
            print(f"    ❌ JSON 解析失败")
            break

        message = data.get("message", {})
        items = message.get("items", [])
        total = message.get("total-results", 0)

        if fetched == 0:
            print(f"    总计 {total} 篇 | 拉取中 ...")

        if not items:
            break

        all_items.extend(items)
        fetched += len(items)

        # 检查是否有下一页
        next_link = None
        for link in message.get("link", []):
            if link.get("rel") == "next":
                next_link = link.get("href")
                break

        if next_link:
            params = {}  # next link 包含全部参数
        elif fetched >= len(items):
            # 没有更多页
            break
        else:
            break

        # 防止无限循环
        if fetched >= max_rows:
            break

        random_delay()

    return all_items[:max_rows]


def parse_crossref_item(item, journal_name, category=""):
    """将 CrossRef 单条记录转为论文字典"""
    article = {
        "journal": journal_name,
        "category": category,
        "fetched_at": datetime.now().isoformat(),
        "source": "CrossRef API",
    }

    # DOI
    article["doi"] = item.get("DOI", "")

    # URL
    if article["doi"]:
        article["url"] = f"https://doi.org/{article['doi']}"
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

    # 发表年份
    date_parts = (
        item.get("published-print", {})
        or item.get("published-online", {})
        or item.get("created", {})
    ).get("date-parts", [[]])
    if date_parts and date_parts[0]:
        article["year"] = str(date_parts[0][0])

    # 摘要
    abstract = item.get("abstract", "")
    if abstract:
        article["abstract"] = clean_html(abstract)
        # CrossRef 的 abstract 有时带前缀 JATS 标签，清理掉
        article["abstract"] = re.sub(r"^.*?<p>", "", article["abstract"], count=1)
        article["abstract"] = re.sub(r"</p>.*$", "", article["abstract"])
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

    # OA 状态
    article["is_oa"] = bool(item.get("abstract", "").startswith("<jats:"))

    # ISSN
    article["issn"] = issn = item.get("ISSN", "")

    # 期刊名（以 CrossRef 返回的为准）
    if item.get("container-title"):
        article["journal"] = item["container-title"][0]

    # 页码 / 卷期
    article["volume"] = item.get("volume", "")
    article["issue"] = item.get("issue", "")
    article["page"] = item.get("page", "")

    # DOI URL
    article["doi"] = item.get("DOI", "")

    # 引用次数
    article["cited_by"] = item.get("is-referenced-by-count", 0)

    # 类型
    article["article_type"] = item.get("type", "journal-article")

    return article


# ==================== 期刊扫描 ====================

def is_vc_pe_paper(paper):
    """
    判断论文是否与 VC/PE 主题相关
    检查标题、摘要、关键词
    """
    title = paper.get("title", "").lower()
    abstract = paper.get("abstract", "").lower()
    keywords = " ".join(paper.get("keywords", [])).lower()
    journal = paper.get("journal", "").lower()

    text = f"{title} {abstract} {keywords}"

    # 排除不相关领域
    for kw in EXCLUDE_KEYWORDS:
        if kw in text:
            return False

    # 检查是否匹配 VC/PE 关键词
    match_count = 0
    for kw in VC_PE_KEYWORDS:
        if kw.lower() in text:
            match_count += 1

    # 至少匹配 1 个关键词
    return match_count >= 1


def scrape_all(max_articles_per_journal=200):
    print("=" * 60)
    print("VC/PE 学术论文抓取系统 — CrossRef API")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"期刊数: {len(VC_PE_JOURNALS)} 种")
    print(f"年份范围: {START_YEAR}-2026")
    print(f"主题: 风险投资 / 创业投资 / 私募股权")
    print("=" * 60)

    existing = load_existing()
    new_count = 0
    skip_count = 0
    irrelevant_count = 0

    for journal in VC_PE_JOURNALS:
        issn = journal["issn"]
        name = journal["name"]
        category = journal.get("category", "")
        print(f"\n📡 [{category}] {name} ({issn})")

        items = fetch_journal_works(issn, name, max_articles_per_journal)

        for raw_item in items:
            article = parse_crossref_item(raw_item, name, category)

            # 年份过滤：跳过 2000 年之前的
            year_str = article.get("year", "")
            if year_str:
                try:
                    year_int = int(year_str)
                    if year_int < START_YEAR:
                        skip_count += 1
                        continue
                except:
                    pass

            # VC/PE 主题相关性过滤
            if not is_vc_pe_paper(article):
                irrelevant_count += 1
                continue

            key = article.get("doi") or article.get("title", "")

            if not key:
                continue

            if key in existing:
                skip_count += 1
                continue

            if article.get("title"):
                existing[key] = article
                new_count += 1
                title = article["title"]
                year = article.get("year", "?")
                print(f"    ✅ [{year}] {title[:55]}")

        random_delay()

    print(f"\n{'=' * 60}")
    print(f"抓取完成！")
    print(f"  新增论文: {new_count} 篇")
    print(f"  跳过已有: {skip_count} 篇")
    print(f"  主题不符: {irrelevant_count} 篇")
    print(f"  共收录: {len(existing)} 篇")
    print("=" * 60)

    save_papers(existing)
    generate_report(list(existing.values()))

    return existing


# ==================== 报告 ====================

def generate_report(papers):
    journals = {}
    categories = {}
    years = {}
    oa_count = 0
    has_abstract = 0

    for p in papers:
        j = p.get("journal", "未知")
        journals[j] = journals.get(j, 0) + 1
        
        cat = p.get("category", "其他")
        categories[cat] = categories.get(cat, 0) + 1
        
        y = p.get("year", "未知")
        years[y] = years.get(y, 0) + 1
        if p.get("is_oa"):
            oa_count += 1
        if p.get("abstract"):
            has_abstract += 1

    print(f"\n📊 统计报告:")
    print(f"   总论文: {len(papers)} 篇")
    print(f"   有摘要: {has_abstract} 篇 ({100*has_abstract//max(len(papers),1)}%)")
    print(f"   OA 论文: {oa_count} 篇")
    print(f"   期刊数量: {len(journals)} 种")
    
    print(f"\n   📁 分类分布:")
    for cat, c in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"     {cat}: {c} 篇")
    
    print(f"\n   期刊分布（前 10）:")
    for j, c in sorted(journals.items(), key=lambda x: -x[1])[:10]:
        print(f"     {j}: {c} 篇")

    report = {
        "total": len(papers),
        "with_abstract": has_abstract,
        "oa_count": oa_count,
        "journal_count": len(journals),
        "by_journal": journals,
        "by_category": categories,
        "by_year": dict(sorted(years.items(), reverse=True)),
        "fetched_at": datetime.now().isoformat(),
        "start_year": START_YEAR,
        "topic": "VC/PE 风险投资/创业投资/私募股权",
    }

    report_file = os.path.join(DATA_DIR, "scrape_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


# ==================== 入口 ====================

if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    scrape_all(max_articles_per_journal=n)
