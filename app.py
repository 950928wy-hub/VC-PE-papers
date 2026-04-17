#!/usr/bin/env python3
"""
VC/PE 论文推送站 — Flask 后端
提供论文搜索、筛选、AI 翻译、自动标签等 API
"""

import json
import os
import re
import math
from datetime import datetime

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

# ==================== 初始化 ====================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PAPERS_FILE = os.path.join(DATA_DIR, "elsevier_papers.json")

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# 加载论文数据
def load_papers():
    if os.path.exists(PAPERS_FILE):
        with open(PAPERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


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


def auto_tag_paper(paper):
    """
    基于关键词和摘要自动为论文打标签
    不依赖 AI API，纯规则匹配
    """
    text = " ".join([
        paper.get("title", ""),
        paper.get("abstract", ""),
        " ".join(paper.get("keywords", [])),
        " ".join(paper.get("subjects", [])),
    ]).lower()
    
    tags = []
    
    # VC/PE 核心标签
    if any(kw in text for kw in ["venture capital", "vc", "venture fund"]):
        tags.append("风险投资")
    if any(kw in text for kw in ["private equity", "pe fund", "buyout"]):
        tags.append("私募股权")
    if any(kw in text for kw in ["lp", "limited partner"]):
        tags.append("LP")
    if any(kw in text for kw in ["gp", "general partner", "fund manager"]):
        tags.append("GP")
    if any(kw in text for kw in ["leveraged buyout", "lbo", "杠杆收购"]):
        tags.append("杠杆收购")
    if any(kw in text for kw in ["exit", "ipo", "m&a", "merger", "acquisition"]):
        tags.append("退出策略")
    if any(kw in text for kw in ["startup", "entrepreneur", "new venture"]):
        tags.append("创业")
    if any(kw in text for kw in ["angel investor", "angel investment"]):
        tags.append("天使投资")
    if any(kw in text for kw in ["fundraising", "fund rising", "capital raising"]):
        tags.append("融资")
    if any(kw in text for kw in ["valuation", "appraisal"]):
        tags.append("估值")
    if any(kw in text for kw in ["corporate governance", "board", "monitoring"]):
        tags.append("公司治理")
    if any(kw in text for kw in ["performance", "return", "irr", "alpha"]):
        tags.append("业绩回报")
    if any(kw in text for kw in ["risk", "volatility", "uncertainty"]):
        tags.append("风险管理")
    if any(kw in text for kw in ["china", "chinese"]):
        tags.append("中国")
    if any(kw in text for kw in ["us", "united states", "america"]):
        tags.append("美国")
    if any(kw in text for kw in ["europe", "eu", "european"]):
        tags.append("欧洲")
    
    return tags if tags else ["其他"]


# ==================== API 路由 ====================

@app.route("/")
def index():
    """主页"""
    return render_template("index.html")


@app.route("/api/papers", methods=["GET"])
def get_papers():
    """
    获取论文列表
    支持分页、搜索、筛选
    """
    papers = load_papers()
    
    # 搜索
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
    
    # OA 筛选
    oa_only = request.args.get("oa", "").strip()
    if oa_only == "1":
        papers = [p for p in papers if p.get("is_oa")]
    
    # 排序
    sort = request.args.get("sort", "newest")
    if sort == "newest":
        papers.sort(key=lambda p: p.get("year", "0") + p.get("fetched_at", ""), reverse=True)
    elif sort == "oldest":
        papers.sort(key=lambda p: p.get("year", "0") + p.get("fetched_at", ""))
    
    # 分页
    page = max(1, int(request.args.get("page", 1)))
    per_page = 20
    total = len(papers)
    total_pages = math.ceil(total / per_page)
    start = (page - 1) * per_page
    end = start + per_page
    
    page_papers = papers[start:end]
    
    # 为每篇论文添加标签
    for p in page_papers:
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
    
    journals = {}
    years = {}
    oa_count = 0
    
    for p in papers:
        year = p.get("year", "未知")
        years[year] = years.get(year, 0) + 1
        
        journal = p.get("journal", "未知")
        journals[journal] = journals.get(journal, 0) + 1
        
        if p.get("is_oa"):
            oa_count += 1
    
    return jsonify({
        "total": len(papers),
        "oa_count": oa_count,
        "journal_count": len(journals),
        "top_journals": sorted(journals.items(), key=lambda x: -x[1])[:10],
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
            journals[journal] = 0
        journals[journal] += 1
    
    return jsonify([
        {"name": j, "count": c}
        for j, c in sorted(journals.items(), key=lambda x: -x[1])
    ])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
