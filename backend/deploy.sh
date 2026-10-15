#!/usr/bin/env bash
# 工会活动阵地管理系统 · 云服务器一键部署脚本
# 用法: 在云服务器上执行  bash deploy.sh
set -e
REPO_URL="https://github.com/wsmcmtlg/GHZDGL.git"
APP_DIR="/opt/vms"

echo "==> 1/5 克拉取代码"
[ -d "$APP_DIR" ] || git clone "$REPO_URL" "$APP_DIR"
cd "$APP_DIR/backend"

echo "==> 2/5 安装依赖"
pip3 install -r requirements.txt

echo "==> 3/5 初始化数据（含默认管理员 admin/admin123，首次运行后请修改密码）"
python3 -c "from app.seed import seed; seed()"

echo "==> 4/5 注册 systemd 服务"
cat > /etc/systemd/system/vms.service <<EOF
[Unit]
Description=GongHui ZhenDi Management System
After=network.target
[Service]
WorkingDirectory=$APP_DIR/backend
# 萤石云密钥配置后取消注释即可切真实视频流
# Environment=EZVIZ_APP_KEY=xxx
# Environment=EZVIZ_APP_SECRET=xxx
Environment=VMS_SECRET=please-change-this-secret
ExecStart=$(which python3) -m uvicorn app.main:app --host 0.0.0.0 --port 8300
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now vms

echo "==> 5/5 完成"
echo "服务地址: http://<服务器IP>:8300   管理端: /   手机预约: /mobile.html"
echo "创建管理员: 修改 deploy.sh 中 create_admin 命令后执行，或调用 POST /api/login 注册逻辑另见 README"
