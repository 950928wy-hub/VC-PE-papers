"""Gunicorn 配置文件"""
import multiprocessing

bind = f"0.0.0.0:{os.environ.get('PORT', 8000)}"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 120
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = "info"
