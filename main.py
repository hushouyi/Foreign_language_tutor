"""
AI 语言助教 - Web 模式入口
=========================
用法:
  python main.py                    # 启动 Web 界面
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from web_server import run_web_server

if __name__ == "__main__":
    run_web_server()
