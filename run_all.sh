#!/bin/bash
# 一键抓取论文 + 生成周报

echo "=========================================="
echo "学术论文抓取系统"
echo "=========================================="

cd "$(dirname "$0")"

echo ""
echo "📡 Step 1: 抓取权威期刊论文..."
python scrape_elsevier.py 200

echo ""
echo "📡 Step 2: 抓取 SSRN 工作论文..."
python scrape_ssrn.py 30 200

echo ""
echo "📊 Step 3: 生成一周综述..."
python weekly_report.py

echo ""
echo "=========================================="
echo "✅ 完成！"
echo "=========================================="
echo ""
echo "运行以下命令启动网站:"
echo "  python app.py"
echo ""
echo "或使用 gunicorn:"
echo "  gunicorn -w 2 -b 0.0.0.0:5000 app:app"
echo ""
