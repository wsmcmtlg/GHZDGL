# -*- coding: utf-8 -*-
"""工会活动阵地精细化管理平台 - 桌面版启动器
自托管后端(uvicorn) + WebView2 窗口(不依赖用户浏览器，免疫扩展/缓存问题)。
打包: pyinstaller --onefile --noconsole --name 工会阵地管理平台
      --add-data "../index.html;." --add-data "../mobile.html;."
      --add-data "../config.js;." --add-data "../assets;assets"
      --add-data "../qr-mobile.png;." --add-data "../backend/app;app"
      --add-data "../tpl-venues.xlsx;." --add-data "../tpl-members.xlsx;."
"""
import os
import sys
import time
import socket
import threading

import uvicorn
import webview

HOST, PORT = "127.0.0.1", 8300


def base_dir():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def port_in_use():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, PORT)) == 0


def start_server(front_dir, db_path):
    base = base_dir()
    # 开发模式：backend 目录是 app 包的父目录；打包后 app 包在解包根目录
    app_parent = os.path.join(base, "backend")
    if not os.path.isdir(os.path.join(app_parent, "app")):
        app_parent = base
    if app_parent not in sys.path:
        sys.path.insert(0, app_parent)
    os.environ["VMS_FRONT_DIR"] = front_dir
    os.environ["VMS_DB"] = db_path
    import sqlalchemy
    from app import database as adb
    from app import seed as appseed
    adb.Base.metadata.create_all(adb.engine)
    with adb.engine.connect() as conn:
        n = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM users")).scalar()
    if n == 0:
        appseed.seed()
        print("database initialized with seed data")
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, log_level="warning")


def main():
    data_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "GHZDGL")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "vms.db")
    front_dir = base_dir()

    if not port_in_use():
        threading.Thread(target=start_server, args=(front_dir, db_path), daemon=True).start()
        for _ in range(50):  # 最多等5秒
            if port_in_use():
                break
            time.sleep(0.1)

    webview.create_window(
        "工会活动阵地精细化管理平台",
        f"http://{HOST}:{PORT}/",
        width=1280, height=850, min_size=(1000, 640),
    )
    webview.start()


if __name__ == "__main__":
    main()
