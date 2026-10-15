# GHZDGL · 工会活动阵地精细化管理系统

荆州供电公司工会活动阵地管理系统：阵地台账、门禁控制、视频巡检、手机扫码预约、使用记录与统计分析。

## 访问方式

| 入口 | 地址 | 用途 |
|---|---|---|
| 管理端（PC） | GitHub Pages 或 后端同源 `/` | 台账/设备/巡检/审批/统计 |
| 手机预约 | Pages `/mobile.html` 或后端 `/mobile.html` | 职工扫码自助预约 |

前端（GitHub Pages）通过 `config.js` 指向后端 API；后端同源部署时 `config.js` 置空即可。

## 目录

- `index.html` / `mobile.html` / `config.js` — 前端（仓库根，即 GitHub Pages 站点根）
- `backend/` — FastAPI 后端（app 源码、测试、requirements、Dockerfile、deploy.sh）

## 云服务器部署（服务器端）

租好轻量云服务器后（CentOS/Ubuntu 均可），一条命令完成部署：

```bash
bash backend/deploy.sh
```

部署完成后：

1. 修改 `frontend/config.js` 中 `API` 为服务器公网地址（或绑域名后的 https 地址），提交推送，Pages 自动更新；
2. 云服务器安全组放行 8300 端口（或配置 Nginx 反代 + HTTPS 后改走 80/443）；
3. 配置萤石云 `EZVIZ_APP_KEY/SECRET` 环境变量（在 `/etc/systemd/system/vms.service` 中取消注释），重启服务即接入真实视频。

## 本地开发

```bash
cd backend
pip install -r requirements.txt
python -c "from app.seed import seed; seed()"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8300
python -m pytest tests/test_api.py -q
```

默认管理员 `admin/admin123`（部署后立即修改）。
