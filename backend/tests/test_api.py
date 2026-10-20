# -*- coding: utf-8 -*-
"""全流程 API 测试：登录→台账→设备→导入→巡检→门禁→预约→统计"""
import io
import os
import sys
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["VMS_DB"] = os.path.join(
    os.path.dirname(__file__), f"test_vms_{datetime.now().strftime('%H%M%S%f')}.db")

from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

seed()
client = TestClient(app)
TOKEN = None


def auth():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_login():
    global TOKEN
    r = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    TOKEN = r.json()["token"]
    assert r.json()["role"] == "admin"


def test_me():
    r = client.get("/api/me", headers=auth())
    assert r.status_code == 200 and r.json()["name"] == "荆州工会管理员"


def test_venues():
    r = client.get("/api/venues", headers=auth())
    venues = r.json()
    assert len(venues) == 65  # 23 本部 + 6*7 县公司
    assert all("name" in v for v in venues)
    # 县公司账号只能看本单位
    r2 = client.post("/api/login", json={"username": "公安县", "password": "123456"})
    t2 = r2.json()["token"]
    r3 = client.get("/api/venues", headers={"Authorization": f"Bearer {t2}"})
    assert all(v["org"] == "公安县供电公司" for v in r3.json())


def test_crud_venue():
    r = client.post("/api/venues", json={"name": "测试新阵地", "level": "本部",
                                         "org": "荆州供电公司工会"}, headers=auth())
    assert r.status_code == 200
    vid = r.json()["id"]
    r = client.put(f"/api/venues/{vid}", json={"name": "测试新阵地改", "level": "本部",
                                               "org": "荆州供电公司工会"}, headers=auth())
    assert r.json()["name"] == "测试新阵地改"
    r = client.delete(f"/api/venues/{vid}", headers=auth())
    assert r.json()["ok"]


def test_devices():
    vid = client.get("/api/venues", headers=auth()).json()[0]["id"]
    r = client.post("/api/doors", json={"venue_id": vid, "brand": "海康", "net_type": "联网型",
                                        "serial": "1.2.3.4"}, headers=auth())
    assert r.status_code == 200
    r = client.post("/api/cameras", json={"venue_id": vid, "brand": "萤石", "serial": "FTEST01",
                                          "validate_code": "XX"}, headers=auth())
    assert r.status_code == 200
    doors = client.get("/api/doors", headers=auth()).json()
    cams = client.get("/api/cameras", headers=auth()).json()
    assert doors and cams


def test_import_excel():
    tpl = os.path.join(os.path.dirname(__file__), "..", "..", "..", "阵地台账与设备清单填报模板.xlsx")
    with open(tpl, "rb") as f:
        content = f.read()
    r = client.post("/api/import", files={"file": ("tpl.xlsx", io.BytesIO(content),
                                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    headers=auth())
    assert r.status_code == 200
    data = r.json()
    # 模板只有示例行，应导入 0 条且不报错
    assert data["venues"] == 0 and "errors" in data


def test_patrol_and_live():
    r = client.post("/api/video/patrol", headers=auth())
    assert r.status_code == 200
    assert r.json()["count"] > 0
    assert r.json()["results"][0]["mock"] is True
    cam_id = r.json()["results"][0]["camera_id"]
    r = client.get(f"/api/video/live/{cam_id}", headers=auth())
    assert r.status_code == 200 and r.json()["url"].startswith("ezopen://")


def test_door_open():
    doors = client.get("/api/doors", headers=auth()).json()
    online = next(d for d in doors if d["net_type"] == "联网型")
    r = client.post(f"/api/door/{online['id']}/open", headers=auth())
    assert r.status_code == 200 and r.json()["ok"]
    offline = next(d for d in doors if d["net_type"] != "联网型")
    r = client.post(f"/api/door/{offline['id']}/open", headers=auth())
    assert r.status_code == 400  # 独立刷卡机不可远程控制


def test_access_logs():
    r = client.get("/api/access-logs?limit=10", headers=auth())
    assert r.status_code == 200 and len(r.json()) > 0


def test_reservation_flow():
    vid = client.get("/api/venues", headers=auth()).json()[0]["id"]
    r = client.post("/api/reservations", json={
        "venue_id": vid, "applicant": "测试职工",
        "start_time": "2026-10-20 14:00:00", "end_time": "2026-10-20 16:00:00",
        "reason": "测试预约"}, headers=auth())
    rid = r.json()["id"]
    assert r.json()["status"] == "待审批"
    r = client.post(f"/api/reservations/{rid}/review?approve=true", headers=auth())
    assert r.json()["status"] == "已通过"


def test_stats():
    r = client.get("/api/stats", headers=auth())
    s = r.json()
    assert s["venues"] == 65 and s["door_devices"] > 0 and s["cameras"] > 0
    assert isinstance(s["top_usage"], list)


def test_user_management():
    # 非管理员无权访问
    r = client.post("/api/login", json={"username": "公安县", "password": "123456"})
    t2 = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/users", headers=t2).status_code == 403
    # 新增县公司账号
    r = client.post("/api/users", headers=auth(), json={
        "username": "testkeeper", "name": "测试管理员", "role": "keeper",
        "org": "公安县供电公司", "password": "abc12345"})
    assert r.status_code == 200
    # 新账号登录：keeper 只能看本单位阵地
    r = client.post("/api/login", json={"username": "testkeeper", "password": "abc12345"})
    tk = r.json()["token"]
    vs = client.get("/api/venues", headers={"Authorization": f"Bearer {tk}"}).json()
    assert len(vs) == 7 and all(v["org"] == "公安县供电公司" for v in vs)
    # 重置密码后用新密码登录
    uid = client.get("/api/users", headers=auth()).json()
    uid = next(u for u in uid if u["username"] == "testkeeper")["id"]
    import copy
    row = {"username": "testkeeper", "name": "测试管理员", "role": "keeper",
           "org": "公安县供电公司", "password": "newpwd66", "active": True}
    assert client.put(f"/api/users/{uid}", headers=auth(), json=row).status_code == 200
    assert client.post("/api/login", json={"username": "testkeeper", "password": "newpwd66"}).status_code == 200
    # 停用后登录被拒
    row["active"] = False
    client.put(f"/api/users/{uid}", headers=auth(), json=row)
    assert client.post("/api/login", json={"username": "testkeeper", "password": "newpwd66"}).status_code == 401
    # 内置管理员不可停用/降级
    admin_row = next(u for u in client.get("/api/users", headers=auth()).json() if u["username"] == "admin")
    r = client.put(f"/api/users/{admin_row['id']}", headers=auth(),
                   json={**admin_row, "active": False})
    assert r.status_code == 400
    # 修改自己密码：错原密码被拒，正确后新密码可登录
    r = client.post("/api/change-password", headers=auth(),
                    json={"old_password": "wrong", "new_password": "x1y2z3"})
    assert r.status_code == 400
    r = client.post("/api/change-password", headers=auth(),
                    json={"old_password": "admin123", "new_password": "x1y2z3"})
    assert r.status_code == 200
    assert client.post("/api/login", json={"username": "admin", "password": "x1y2z3"}).status_code == 200


def test_members_and_auth():
    # 导入人员名单
    tpl = os.path.join(os.path.dirname(__file__), "..", "..", "人员名单导入模板.xlsx")
    with open(tpl, "rb") as f:
        content = f.read()
    r = client.post("/api/import-members", files={"file": ("m.xlsx", io.BytesIO(content), "application/octet-stream")}, headers=auth())
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 0  # 模板只有示例行
    # 直接造两条人员再导入同名同号验证去重
    from app.database import SessionLocal
    from app.models import Member
    db = SessionLocal()
    db.add(Member(name="张测试", org="公安县供电公司", dept="工会办", phone="13600001111", card_no="GD001"))
    db.add(Member(name="李测试", org="公安县供电公司", dept="办公室", phone="13600002222", card_no="GD002"))
    db.commit(); db.close()
    # 列表与搜索
    ms = client.get("/api/members?keyword=张测试", headers=auth()).json()
    assert len(ms) == 1 and ms[0]["card_no"] == "GD001"
    mid = ms[0]["id"]
    # 授权与回收
    doors = client.get("/api/doors", headers=auth()).json()
    did = doors[0]["id"]
    r = client.post(f"/api/members/{mid}/grant/{did}", headers=auth())
    assert r.json()["status"] == "已授权"
    r = client.post(f"/api/members/{mid}/grant/{did}", headers=auth())
    assert r.json()["status"] == "已授权"  # 重复授权幂等
    assert len(client.get(f"/api/door-auths?member_id={mid}", headers=auth()).json()) == 1
    # 停用人员自动回收授权
    client.put(f"/api/members/{mid}?name=张测试&org=公安县供电公司&phone=13600001111&card_no=GD001&active=false", headers=auth())
    a = client.get(f"/api/door-auths?member_id={mid}", headers=auth()).json()[0]
    assert a["status"] == "已回收"
