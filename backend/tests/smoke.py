# -*- coding: utf-8 -*-
"""对运行中的服务做端到端联调验证"""
import json
import urllib.request

BASE = "http://127.0.0.1:8300"


def call(path, method="GET", body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


t = call("/api/login", "POST", {"username": "admin", "password": "admin123"})["token"]
me = call("/api/me", token=t)
stats = call("/api/stats", token=t)
venues = call("/api/venues", token=t)
doors = call("/api/doors", token=t)
cams = call("/api/cameras", token=t)
patrol = call("/api/video/patrol", "POST", token=t)
logs = call("/api/access-logs?limit=5", token=t)
resvs = call("/api/reservations", token=t)
online = next(d for d in doors if d["net_type"] == "联网型")
opened = call(f"/api/door/{online['id']}/open", "POST", token=t)
live = call(f"/api/video/live/{cams[0]['id']}", token=t)

print("用户:", me["name"], me["role"])
print(f"阵地 {stats['venues']} 处 | 门禁 {stats['door_devices']}(联网{stats['online_doors']}) | 摄像头 {stats['cameras']} | 待审批 {stats['pending_reservations']}")
print("Top使用:", stats["top_usage"][0] if stats["top_usage"] else "无")
print("巡检:", patrol["count"], "路, 首路:", patrol["results"][0]["venue"], patrol["results"][0]["snapshot"])
print("开门:", opened["ok"], "| 预览地址:", live["url"])
print("最近记录:", logs[0]["created_at"], logs[0]["action"])
print("预约数:", len(resvs))
# 县公司权限隔离验证
t2 = call("/api/login", "POST", {"username": "公安县", "password": "123456"})["token"]
v2 = call("/api/venues", token=t2)
print("县公司可见阵地:", len(v2), "处, 单位:", set(v["org"] for v in v2))
