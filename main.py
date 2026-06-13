"""
AI 语言助教 - Web 模式入口
=========================
用法:
  python main.py                    # 启动 Web 界面
"""

from server import create_app

if __name__ == "__main__":
    app = create_app()
    from server import config as cfg
    app.run(host=cfg.WEB_HOST, port=cfg.WEB_PORT, debug=False, threaded=True)
