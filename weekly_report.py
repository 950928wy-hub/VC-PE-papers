#!/usr/bin/env python3
"""
一周综述生成器
统计本周新增论文，按领域分类生成 Markdown 格式的周报
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

# ==================== 配置区 ====================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

PAPERS_FILE = os.path.join(DATA_DIR, "elsevier_papers.json")
SSRN_FILE = os.path.join(DATA_DIR, "ssrn_papers.json")
OUTPUT_DIR = os.path.join(DATA_DIR, "weekly_reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ==================== 核心函数 ====================

def load_papers():
    """加载所有论文数据"""
    papers = {"journals": [], "ssrn": []}
    
    if os.path.exists(PAPERS_FILE):
        with open(PAPERS_FILE, "r", encoding="utf-8") as f:
            papers["journals"] = json.load(f)
    
    if os.path.exists(SSRN_FILE):
        with open(SSRN_FILE, "r", encoding="utf-8") as f:
            papers["ssrn"] = json.load(f)
    
    return papers


def get_this_week_papers(papers, days_back=7):
    """获取本周新增的论文"""
    cutoff = datetime.now() - timedelta(days=days_back)
    week_papers = {"journals": [], "ssrn": []}
    
    for paper in papers["journals"]:
        try:
            fetched = datetime.fromisoformat(paper.get("fetched_at", "2000-01-01"))
            if fetched >= cutoff:
                week_papers["journals"].append(paper)
        except:
            pass
    
    for paper in papers["ssrn"]:
        try:
            fetched = datetime.fromisoformat(paper.get("fetched_at", "2000-01-01"))
            if fetched >= cutoff:
                week_papers["ssrn"].append(paper)
        except:
            pass
    
    return week_papers


def get_recent_papers(papers, days_back=7):
    """获取最近 days_back 天内发表的论文（按发表日期）"""
    cutoff = datetime.now() - timedelta(days=days_back)
    recent_papers = []
    
    for paper in papers["journals"] + papers["ssrn"]:
        # 尝试从发表日期判断
        year = paper.get("year", "")
        month = paper.get("month", "")
        
        if year and month:
            try:
                pub_date = datetime(int(year), int(month), 1)
                if pub_date >= cutoff:
                    recent_papers.append(paper)
            except:
                pass
        elif year:
            try:
                pub_date = datetime(int(year), 1, 1)
                if pub_date >= cutoff:
                    recent_papers.append(paper)
            except:
                pass
    
    return recent_papers


def categorize_by_field(papers):
    """按领域分类论文"""
    categories = defaultdict(list)
    
    for paper in papers:
        category = paper.get("category", "")
        
        # 如果没有 category 字段，根据 journal 名称判断
        if not category:
            journal = paper.get("journal", "").lower()
            if any(kw in journal for kw in ["finance", "banking", "financial"]):
                category = "Finance"
            elif any(kw in journal for kw in ["accounting", "account"]):
                category = "Accounting"
            elif any(kw in journal for kw in ["economic", "economics"]):
                category = "Economic"
            elif any(kw in journal for kw in ["management", "strategy", "organization", "business"]):
                category = "Management & Strategy"
            else:
                category = "Other"
        
        categories[category].append(paper)
    
    return categories


def generate_markdown_report(week_papers, categories):
    """生成 Markdown 格式的周报"""
    
    today = datetime.now()
    week_start = today - timedelta(days=6)
    
    md = f"""# 📚 学术论文周报

**生成时间**: {today.strftime('%Y-%m-%d %H:%M')}  
**统计周期**: {week_start.strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}

---

## 📊 本周数据概览

| 指标 | 数量 |
|:-----|-----:|
| 本周新增期刊论文 | {len(week_papers['journals'])} 篇 |
| 本周新增 SSRN 论文 | {len(week_papers['ssrn'])} 篇 |
| 涵盖期刊种类 | {len(set(p.get('journal', '') for p in week_papers['journals']))} 种 |
| 有摘要论文 | {sum(1 for p in week_papers['journals'] if p.get('abstract'))} 篇 |

---

"""
    
    # 按领域分类输出
    category_order = ["Finance", "Economic", "Accounting", "Strategy & Organization", "Management", "Management & Strategy", "Other"]
    
    for cat in category_order:
        if cat in categories and categories[cat]:
            md += f"## 🏛️ {cat}\n\n"
            
            # 按期刊分组
            by_journal = defaultdict(list)
            for p in categories[cat]:
                j = p.get("journal", "Unknown")
                by_journal[j].append(p)
            
            for journal, journal_papers in sorted(by_journal.items(), key=lambda x: -len(x[1])):
                md += f"### 📖 {journal} ({len(journal_papers)} 篇)\n\n"
                
                for i, p in enumerate(journal_papers[:10], 1):  # 每期刊最多显示10篇
                    title = p.get("title", "无标题")
                    authors = ", ".join(p.get("authors", [])[:3])
                    if len(p.get("authors", [])) > 3:
                        authors += " et al."
                    year = p.get("year", "n.d.")
                    doi = p.get("doi", "")
                    url = p.get("url", f"https://doi.org/{doi}") if doi else "#"
                    
                    md += f"{i}. **{title}**  \n"
                    md += f"   - Authors: {authors}  \n"
                    md += f"   - Year: {year}  \n"
                    md += f"   - Link: [{doi or 'N/A'}]({url})\n\n"
                
                if len(journal_papers) > 10:
                    md += f"> ... 还有 {len(journal_papers) - 10} 篇论文未显示\n\n"
            
            md += "---\n\n"
    
    # SSRN 工作论文
    if week_papers["ssrn"]:
        md += "## 📑 SSRN 工作论文\n\n"
        
        ssrn_categories = categorize_by_field(week_papers["ssrn"])
        for cat, papers in ssrn_categories.items():
            if papers:
                md += f"### {cat} ({len(papers)} 篇)\n\n"
                
                for i, p in enumerate(papers[:10], 1):
                    title = p.get("title", "无标题")
                    authors = ", ".join(p.get("authors", [])[:3])
                    if len(p.get("authors", [])) > 3:
                        authors += " et al."
                    url = p.get("url", "#")
                    
                    md += f"{i}. **{title}**  \n"
                    md += f"   - Authors: {authors}  \n"
                    md += f"   - Link: [SSRN]({url})\n\n"
        
        md += "---\n\n"
    
    # 高被引论文（本周新增中有摘要的）
    with_abstract = [p for p in week_papers["journals"] if p.get("abstract")]
    if with_abstract:
        md += "## ⭐ 精选论文（有摘要）\n\n"
        
        for i, p in enumerate(with_abstract[:5], 1):
            title = p.get("title", "无标题")
            authors = ", ".join(p.get("authors", [])[:3])
            if len(p.get("authors", [])) > 3:
                authors += " et al."
            journal = p.get("journal", "")
            year = p.get("year", "")
            abstract = p.get("abstract", "")[:300]
            if len(p.get("abstract", "")) > 300:
                abstract += "..."
            doi = p.get("doi", "")
            url = f"https://doi.org/{doi}" if doi else "#"
            
            md += f"### {i}. {title}\n\n"
            md += f"**{authors}** · *{journal}*, {year}\n\n"
            md += f"> {abstract}\n\n"
            md += f"[Read more →]({url})\n\n"
    
    # Footer
    md += """---

*本报告由学术论文推送站自动生成*  
*数据来源: CrossRef API, SSRN*  
*仅供学术研究使用*
"""
    
    return md


def generate_json_report(week_papers, categories):
    """生成 JSON 格式的周报（供前端使用）"""
    return {
        "generated_at": datetime.now().isoformat(),
        "period": {
            "start": (datetime.now() - timedelta(days=6)).isoformat(),
            "end": datetime.now().isoformat(),
        },
        "summary": {
            "journal_papers": len(week_papers["journals"]),
            "ssrn_papers": len(week_papers["ssrn"]),
            "journals_count": len(set(p.get("journal", "") for p in week_papers["journals"])),
        },
        "by_category": {
            cat: len(papers) 
            for cat, papers in categories.items()
        },
        "papers": week_papers["journals"] + week_papers["ssrn"],
    }


# ==================== 主函数 ====================

def generate_weekly_report(days_back=7):
    """生成一周综述"""
    print("=" * 60)
    print("一周综述生成器")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"统计周期: 最近 {days_back} 天")
    print("=" * 60)
    
    # 加载数据
    all_papers = load_papers()
    print(f"  📂 加载期刊论文: {len(all_papers['journals'])} 篇")
    print(f"  📂 加载 SSRN 论文: {len(all_papers['ssrn'])} 篇")
    
    # 获取本周新增
    week_papers = get_this_week_papers(all_papers, days_back)
    print(f"\n  📊 本周新增期刊论文: {len(week_papers['journals'])} 篇")
    print(f"  📊 本周新增 SSRN 论文: {len(week_papers['ssrn'])} 篇")
    
    if not week_papers["journals"] and not week_papers["ssrn"]:
        print("\n  ⚠️ 本周无新增论文，可能需要运行抓取脚本")
        return None
    
    # 按领域分类
    categories = categorize_by_field(week_papers["journals"])
    
    # 生成报告
    md_report = generate_markdown_report(week_papers, categories)
    json_report = generate_json_report(week_papers, categories)
    
    # 保存报告
    today_str = datetime.now().strftime("%Y-%m-%d")
    week_str = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    
    md_file = os.path.join(OUTPUT_DIR, f"weekly_{today_str}.md")
    json_file = os.path.join(OUTPUT_DIR, f"weekly_{today_str}.json")
    
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"\n  💾 Markdown 报告: {md_file}")
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)
    print(f"  💾 JSON 报告: {json_file}")
    
    # 更新 latest 链接
    latest_md = os.path.join(OUTPUT_DIR, "latest.md")
    latest_json = os.path.join(OUTPUT_DIR, "latest.json")
    
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(md_report)
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)
    
    print(f"\n  ✅ 最新周报已更新: {latest_md}")
    print("=" * 60)
    
    return json_report


# ==================== 入口 ====================

if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    generate_weekly_report(days_back=days)
