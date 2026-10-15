# -*- coding: utf-8 -*-
"""手机端预约全流程测试（需服务运行中）"""
import json
import urllib.request
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8300"


def call(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


# 1. 免登录获取阵地列表
code, venues = call("/api/mobile/venues")
assert code == 200 and len(venues) > 0, "阵地列表失败"
vid = venues[0]["id"]

# 2. 免登录提交预约（自动寻找无冲突的阵地+时段）
base = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
rid = vid = None
for v in venues:
    for h in range(7, 21):
        start = base.replace(hour=h)
        end = start + timedelta(hours=1)
        code, r = call("/api/mobile/reservations", "POST", {
            "venue_id": v["id"], "applicant": "扫码职工", "phone": "13655556666",
            "start_time": start.isoformat(sep=" "), "end_time": end.isoformat(sep=" "),
            "reason": "手机端测试"})
        if code == 200:
            rid, vid = r["id"], v["id"]
            break
    if rid:
        break
assert rid, "所有阵地时段均被占用，测试数据异常"
print(f"  预约阵地: {next(v['name'] for v in venues if v['id']==vid)} {start:%m-%d %H}:00")

# 3. 时段冲突检查
code2, r2 = call("/api/mobile/reservations", "POST", {
    "venue_id": vid, "applicant": "另一人", "phone": "13655557777",
    "start_time": (start + timedelta(minutes=30)).isoformat(sep=" "),
    "end_time": (end + timedelta(hours=1)).isoformat(sep=" ")})
assert code2 == 400, f"冲突时段未拦截: {code2} {r2}"

# 4. 管理员审批通过
code, admin = call("/api/login", "POST", {"username": "admin", "password": "admin123"})
at = admin["token"]
req = urllib.request.Request(f"{BASE}/api/reservations/{rid}/review?approve=true", method="POST",
                             headers={"Authorization": f"Bearer {at}"})
urllib.request.urlopen(req)

# 5. 职工手机号查询
code, mine = call("/api/mobile/reservations?phone=13655556666")
assert code == 200 and any(x["id"] == rid and x["status"] == "已通过" for x in mine), f"查询失败: {mine}"

# 6. 二维码
req = urllib.request.Request(f"{BASE}/api/qrcode", headers={"Host": "192.168.44.3:8300"})
with urllib.request.urlopen(req) as resp:
    data = resp.read()
assert data[:4] == b"\x89PNG", "二维码非PNG"

print("手机预约全流程 6/6 通过：")
print(f"  提交预约 #{rid} → 时段冲突拦截 → 管理员已通过 → 手机号可查")
print(f"  二维码 {len(data)//1024}KB PNG 正常生成")
