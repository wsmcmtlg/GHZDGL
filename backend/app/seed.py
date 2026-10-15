# -*- coding: utf-8 -*-
"""生成测试数据：管理员+县公司用户、阵地、设备、使用记录、预约"""
import random
from datetime import datetime, timedelta

from .database import SessionLocal, engine
from .models import AccessLog, Base, Camera, DoorDevice, Reservation, User, Venue
from .main import hash_pwd

COUNTIES = ["江陵县供电公司", "公安县供电公司", "监利市供电公司", "松滋市供电公司", "石首市供电公司", "洪湖市供电公司"]
CATS = ["健身房", "球场", "职工书屋", "棋牌室", "乒乓球室", "瑜伽室", "舞蹈室", "多功能厅"]

def seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if db.query(User).count() > 0:
        print("已有数据，跳过"); return
    db.add(User(username="admin", password_hash=hash_pwd("admin123"), name="荆州工会管理员", role="admin", org="荆州供电公司工会"))
    for c in COUNTIES:
        db.add(User(username=c[:3], password_hash=hash_pwd("123456"), name=f"{c}管理员", role="county", org=c))
    db.commit()

    venues = []
    for i in range(1, 24):  # 本部 23 处
        venues.append(Venue(name=f"本部职工活动中心{i}号馆", level="本部", org="荆州供电公司工会",
                            address=f"荆州市沙市区xx路{i}号", category=random.choice(CATS),
                            area=random.randint(80, 500), open_hours="工作日 8:00-21:00",
                            capacity=random.randint(10, 80), facilities="健身器材、空调、饮水机",
                            manager=f"管理员{i}", phone="1380000%04d" % i))
    for c in COUNTIES:
        for i in range(1, 8):  # 每县 7 处，共 42+23
            venues.append(Venue(name=f"{c}职工之家{i}", level="县级公司", org=c,
                                address=f"{c}院内{i}号楼", category=random.choice(CATS),
                                area=random.randint(60, 300), open_hours="工作日 8:00-20:00",
                                capacity=random.randint(10, 40), facilities="乒乓球桌、图书角",
                                manager=f"{c[:3]}管理员{i}", phone="1390000%04d" % i))
    db.add_all(venues); db.commit()

    for i, v in enumerate(venues):
        net = random.random() < 0.75
        db.add(DoorDevice(venue_id=v.id, brand=random.choice(["海康威视", "大华", "达实"]),
                          model="DS-K1T671M", net_type="联网型" if net else "独立刷卡机",
                          access_mode="厂商SDK" if net else "记录采集器",
                          serial=f"192.168.10.{i+2}", location="正门", remark=""))
        if random.random() < 0.85:
            db.add(Camera(venue_id=v.id, brand="萤石", model="C8W", platform="萤石云",
                          serial=f"F{1000000+i}", validate_code="ABCD%d" % (i % 100),
                          location="大厅顶部", coverage="活动区域全域", remark=""))
    db.commit()

    # 近30日使用记录
    logs = []
    now = datetime.now()
    for v in venues:
        for _ in range(random.randint(3, 40)):
            t = now - timedelta(days=random.randint(0, 29), hours=random.randint(0, 12))
            logs.append(AccessLog(venue_id=v.id, person=random.choice(["刷卡用户", "预约用户", "访客"]),
                                  action=random.choice(["card_open", "remote_open", "scheduled_open"]),
                                  source="采集器", created_at=t))
    db.add_all(logs)
    for v in random.sample(venues, 6):
        s = now + timedelta(days=random.randint(1, 5), hours=random.choice([9, 14, 19]))
        db.add(Reservation(venue_id=v.id, applicant="职工李四", phone="13711112222",
                           start_time=s, end_time=s + timedelta(hours=2),
                           status=random.choice(["待审批", "待审批", "已通过"]), reason="部门羽毛球活动"))
    db.commit(); db.close()
    print(f"seeded: 1 admin + {len(COUNTIES)} county users, {len(venues)} venues, logs done")

if __name__ == "__main__":
    seed()
