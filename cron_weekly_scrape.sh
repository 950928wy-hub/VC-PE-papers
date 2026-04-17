#!/bin/bash
# VC/PE 论文定时抓取脚本
# 每周自动运行一次

cd /Users/yanyan/Documents/vc-pe-papers
python3 scrape_elsevier.py 200 >> logs/cron_scrape.log 2>&1

# 重启 Flask 服务（让网站显示最新数据）
pkill -f "python3 app.py" 2>/dev/null
cd /Users/yanyan/Documents/vc-pe-papers
python3 app.py >> logs/flask.log 2>&1 &
