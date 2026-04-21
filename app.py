#!/usr/bin/env python3
"""
学术论文推送站 — Flask 后端 v2
支持权威期刊 + SSRN 工作论文 + 一周综述
"""

import json
import os
import re
import math
from datetime import datetime, timedelta
from collections import defaultdict

from flask import Flask, request, jsonify, render_template, send_from_directory, abort
from flask_cors import CORS

# ==================== 初始化 ====================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PAPERS_FILE = os.path.join(DATA_DIR, "elsevier_papers.json")
SSRN_FILE = os.path.join(DATA_DIR, "ssrn_papers.json")
REPORTS_DIR = os.path.join(DATA_DIR, "weekly_reports")

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# 期刊分类配置
JOURNAL_CATEGORIES = {
    "Finance": ["Journal of Finance", "Journal of Financial and Quantitative Analysis",
                "Journal of Financial Economics", "Review of Financial Studies",
                "Review of Finance", "Journal of Banking and Finance", "Journal of Corporate Finance"],
    "Economic": ["Journal of Economic Literature", "Journal of Economic Perspectives",
                 "Journal of Economics and Management Strategy"],
    "Accounting": ["Accounting Review", "Contemporary Accounting Research",
                   "Journal of Accounting and Economics", "Journal of Accounting Research",
                   "Review of Accounting Studies"],
    "Strategy & Organization": ["Academy of Management Journal", "Academy of Management Review",
                                  "Strategic Management Journal", "Harvard Business Review",
                                  "Organization Science", "Journal of International Business Studies",
                                  "Journal of Business Venturing", "Journal of Management"],
    "Management": ["Management Science"],
}

# VC/PE 主题关键词
VC_PE_KEYWORDS = [
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
    "vc", "pe", "cvc", "cve",
]

# 排除关键词
EXCLUDE_KEYWORDS = [
    "medical", "medicine", "healthcare", "biology", "biochemistry",
    "physics", "chemistry", "engineering", "materials",
    "agriculture", "environmental science", "ecology", "climate",
    "education", "psychology", "sociology",
    "agricultural economics", "health economics",
]

START_YEAR = 2000


def is_vc_pe_paper(paper):
    """判断论文是否与 VC/PE 主题相关"""
    title = paper.get("title", "").lower()
    abstract = paper.get("abstract", "").lower()
    keywords = " ".join(paper.get("keywords", [])).lower()
    text = f"{title} {abstract} {keywords}"

    for kw in EXCLUDE_KEYWORDS:
        if kw in text:
            return False

    match_count = 0
    for kw in VC_PE_KEYWORDS:
        if kw.lower() in text:
            match_count += 1
    return match_count >= 1


def get_paper_category(paper):
    """获取论文所属分类"""
    journal = paper.get("journal", "")
    if paper.get("category"):
        return paper["category"]
    for cat, journals in JOURNAL_CATEGORIES.items():
        if any(j.lower() in journal.lower() for j in journals):
            return cat
    return "Other"


def load_papers():
    """加载论文数据"""
    papers = []
    if os.path.exists(PAPERS_FILE):
        with open(PAPERS_FILE, "r", encoding="utf-8") as f:
            papers = json.load(f)
    return papers


def load_ssrn_papers():
    """加载 SSRN 论文数据"""
    papers = []
    if os.path.exists(SSRN_FILE):
        with open(SSRN_FILE, "r", encoding="utf-8") as f:
            papers = json.load(f)
    return papers


def load_weekly_report():
    """加载最新周报"""
    latest_json = os.path.join(REPORTS_DIR, "latest.json")
    if os.path.exists(latest_json):
        with open(latest_json, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# ==================== AI 翻译模块 ====================

def translate_text(text, target_lang="zh"):
    """
    使用免费翻译 API 翻译文本
    支持 DeepL Free / Google Translate / 百度翻译
    这里使用 DeepL Free API（免费额度充足）
    """
    # 可以在这里配置你的翻译 API
    # 推荐使用 DeepL Free（每月 50 万字符免费）
    DEEPL_KEY = os.environ.get("DEEPL_API_KEY", "")
    
    if not text:
        return ""
    
    if not DEEPL_KEY:
        return "[请配置 DEEPL_API_KEY 以启用翻译]"
    
    try:
        import urllib.request
        import urllib.parse
        
        params = urllib.parse.urlencode({
            "auth_key": DEEPL_KEY,
            "text": text[:5000],  # 单次限制 5000 字符
            "target_lang": target_lang.upper(),
        })
        
        req = urllib.request.Request(
            "https://api-free.deepl.com/v2/translate",
            data=params.encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result["translations"][0]["text"]
    except Exception as e:
        return f"[翻译失败: {e}]"


# 过滤关键词列表（用于排除不相关论文）
EXCLUDE_KEYWORDS = [
    "medical", "medicine", "healthcare", "biology", "biochemistry",
    "physics", "chemistry", "engineering", "materials",
    "agriculture", "environmental science", "ecology",
]

# 包含关键词列表（确保论文与学术/商业研究相关）
INCLUDE_KEYWORDS = [
    "finance", "financial", "economi", "accounting", "management",
    "strategy", "organization", "business", "investment", "market",
    "capital", "bank", "credit", "risk", "return", "performance",
    "corporate", "entrepreneur", "innovation", "technology",
    "venture", "private equity", "merger", "acquisition", "ipo",
]


def auto_tag_paper(paper):
    """
    基于关键词和摘要自动为论文打标签
    针对导师指定的权威期刊领域优化
    """
    text = " ".join([
        paper.get("title", ""),
        paper.get("abstract", ""),
        " ".join(paper.get("keywords", [])),
    ]).lower()
    
    tags = []
    
    # Finance 领域
    if any(kw in text for kw in ["asset pricing", "stock market", "portfolio", "investment", "return", "risk"]):
        tags.append("资产定价")
    if any(kw in text for kw in ["venture capital", "vc", "private equity", "buyout", "lbo"]):
        tags.append("VC/PE")
    if any(kw in text for kw in ["bank", "banking", "intermediation", "credit"]):
        tags.append("银行与信贷")
    if any(kw in text for kw in ["ipo", "listing", "securities", "bond"]):
        tags.append("资本市场")
    if any(kw in text for kw in ["corporate finance", "financing", "capital structure", "leverage"]):
        tags.append("公司金融")
    if any(kw in text for kw in ["merger", "m&a", "acquisition", "takeover"]):
        tags.append("并购")
    if any(kw in text for kw in ["governance", "board", "ownership", "shareholder"]):
        tags.append("公司治理")
    
    # Accounting 领域
    if any(kw in text for kw in ["earnings", "accrual", "accounting", "financial reporting"]):
        tags.append("会计信息")
    if any(kw in text for kw in ["audit", "auditing", "audit quality"]):
        tags.append("审计")
    if any(kw in text for kw in ["ifrs", "gaap", "accounting standard"]):
        tags.append("会计准则")
    
    # Economics 领域
    if any(kw in text for kw in ["economic growth", "gdp", "macroeconom"]):
        tags.append("宏观经济")
    if any(kw in text for kw in ["regulation", "antitrust", "competition policy"]):
        tags.append("监管政策")
    if any(kw in text for kw in ["development", "emerging market", "developing"]):
        tags.append("发展经济")
    
    # Strategy & Management 领域
    if any(kw in text for kw in ["strategy", "strategic", "competitive advantage", "壁垒"]):
        tags.append("战略管理")
    if any(kw in text for kw in ["innovation", "patent", "r&d", "technology"]):
        tags.append("创新与技术")
    if any(kw in text for kw in ["entrepreneur", "startup", "venture creation"]):
        tags.append("创业")
    if any(kw in text for kw in ["organization", "organizational", "structure"]):
        tags.append("组织管理")
    if any(kw in text for kw in ["international", "global", "multinational", "cross-border"]):
        tags.append("国际化经营")
    if any(kw in text for kw in ["leadership", "ceo", "top management"]):
        tags.append("高管与领导力")
    
    # 地区标签
    if any(kw in text for kw in ["china", "chinese"]):
        tags.append("中国")
    if any(kw in text for kw in ["us", "united states", "america", "american"]):
        tags.append("美国")
    if any(kw in text for kw in ["europe", "eu", "european"]):
        tags.append("欧洲")
    
    # 如果没有标签，添加一个通用的
    if not tags:
        tags = ["其他"]
    
    return list(set(tags))  # 去重


# ==================== API 路由 ====================

@app.route("/")
def index():
    """主页"""
    return render_template("index.html")


@app.route("/api/papers", methods=["GET"])
def get_papers():
    """
    获取论文列表
    支持分页、搜索、筛选、来源筛选
    仅返回与 VC/PE 主题相关的论文
    """
    papers = load_papers()

    # 数据来源筛选
    source = request.args.get("source", "").strip()
    if source == "ssrn":
        papers = load_ssrn_papers()
    elif source == "journal":
        papers = load_papers()

    # VC/PE 主题过滤（默认开启）
    vc_pe_filter = request.args.get("vcpe", "1").strip()
    if vc_pe_filter == "1":
        papers = [p for p in papers if is_vc_pe_paper(p)]

    # 年份过滤（2000年至今）
    papers = [p for p in papers if int(p.get("year", "0") or 0) >= START_YEAR]

    # 搜索（仅搜索相关论文）
    q = request.args.get("q", "").strip().lower()
    if q:
        papers = [
            p for p in papers
            if q in p.get("title", "").lower()
            or q in p.get("abstract", "").lower()
            or q in " ".join(p.get("authors", [])).lower()
            or q in p.get("journal", "").lower()
        ]
    
    # 年份筛选
    year = request.args.get("year", "").strip()
    if year:
        papers = [p for p in papers if p.get("year", "").startswith(year)]
    
    # 期刊筛选
    journal = request.args.get("journal", "").strip()
    if journal:
        papers = [p for p in papers if journal.lower() in p.get("journal", "").lower()]
    
    # 分类筛选
    category = request.args.get("category", "").strip()
    if category:
        papers = [p for p in papers if get_paper_category(p) == category]
    
    # OA 筛选
    oa_only = request.args.get("oa", "").strip()
    if oa_only == "1":
        papers = [p for p in papers if p.get("is_oa")]
    
    # 排序
    sort = request.args.get("sort", "newest")
    if sort == "newest":
        papers.sort(key=lambda p: (p.get("year", "0"), p.get("fetched_at", "")), reverse=True)
    elif sort == "oldest":
        papers.sort(key=lambda p: (p.get("year", "0") + p.get("fetched_at", "")))
    elif sort == "cited":
        papers.sort(key=lambda p: p.get("cited_by", 0), reverse=True)
    
    # 分页
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20
    total = len(papers)
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    start = (page - 1) * per_page
    end = start + per_page
    
    page_papers = papers[start:end]
    
    # 为每篇论文添加分类和标签
    for p in page_papers:
        p["category"] = get_paper_category(p)
        p["auto_tags"] = auto_tag_paper(p)
    
    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "papers": page_papers,
    })


@app.route("/api/paper/<doi>", methods=["GET"])
def get_paper(doi):
    """获取单篇论文详情"""
    papers = load_papers()
    doi_decoded = doi.replace("__SLASH__", "/")
    
    for p in papers:
        if p.get("doi", "") == doi_decoded:
            p["category"] = get_paper_category(p)
            p["auto_tags"] = auto_tag_paper(p)
            return jsonify(p)
    
    return jsonify({"error": "论文未找到"}), 404


@app.route("/api/translate", methods=["POST"])
def translate():
    """翻译摘要"""
    data = request.get_json()
    text = data.get("text", "")
    target = data.get("target", "zh")
    
    if not text:
        return jsonify({"error": "文本不能为空"}), 400
    
    translated = translate_text(text, target)
    return jsonify({"original": text, "translated": translated})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """获取统计信息"""
    papers = load_papers()
    ssrn_papers = load_ssrn_papers()

    # 仅统计 VC/PE 主题论文
    papers = [p for p in papers if is_vc_pe_paper(p) and int(p.get("year", "0") or 0) >= START_YEAR]

    journals = {}
    categories = {}
    years = {}
    oa_count = 0

    for p in papers:
        cat = get_paper_category(p)
        categories[cat] = categories.get(cat, 0) + 1
        
        year = p.get("year", "未知")
        years[year] = years.get(year, 0) + 1
        
        journal = p.get("journal", "未知")
        journals[journal] = journals.get(journal, 0) + 1
        
        if p.get("is_oa"):
            oa_count += 1
    
    return jsonify({
        "total": len(papers),
        "ssrn_total": len(ssrn_papers),
        "oa_count": oa_count,
        "journal_count": len(journals),
        "category_count": len(categories),
        "top_journals": sorted(journals.items(), key=lambda x: -x[1])[:10],
        "categories": dict(sorted(categories.items(), key=lambda x: -x[1])),
        "by_year": dict(sorted(years.items(), reverse=True)),
    })


@app.route("/api/journals", methods=["GET"])
def get_journals():
    """获取所有期刊列表"""
    papers = load_papers()
    journals = {}
    
    for p in papers:
        journal = p.get("journal", "未知")
        if journal not in journals:
            journals[journal] = {"name": journal, "count": 0, "category": get_paper_category(p)}
        journals[journal]["count"] += 1
    
    return jsonify([
        {"name": j["name"], "count": j["count"], "category": j["category"]}
        for j in journals.values()
    ])


@app.route("/api/categories", methods=["GET"])
def get_categories():
    """获取所有分类"""
    return jsonify([
        {"id": "Finance", "name": "金融", "icon": "💰"},
        {"id": "Economic", "name": "经济", "icon": "📊"},
        {"id": "Accounting", "name": "会计", "icon": "📒"},
        {"id": "Strategy & Organization", "name": "战略与组织", "icon": "🏢"},
        {"id": "Management", "name": "管理", "icon": "⚙️"},
        {"id": "Other", "name": "其他", "icon": "📄"},
    ])


@app.route("/api/weekly-report", methods=["GET"])
def get_weekly_report():
    """获取一周综述"""
    report = load_weekly_report()
    if report:
        return jsonify(report)
    return jsonify({"error": "暂无周报，请先运行抓取脚本"}), 404


@app.route("/weekly-report")
def weekly_report_page():
    """一周综述页面"""
    return render_template("weekly_report.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
