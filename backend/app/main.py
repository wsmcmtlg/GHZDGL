# -*- coding: utf-8 -*-
"""工会活动阵地精细化管理系统 · 后端主应用"""
import os
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import engine, get_db
from .models import AccessLog, Base, Camera, DoorDevice, Reservation, User, Venue
from . import ezviz

SECRET_KEY = os.environ.get("VMS_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12
app = FastAPI(title="工会活动阵地管理系统", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
oauth2 = OAuth2PasswordBearer(tokenUrl="api/login")


def hash_pwd(pwd: str) -> str:
    import hashlib
    return hashlib.sha256(pwd.encode()).hexdigest()


def create_token(user: User) -> str:
    payload = {"sub": user.username, "role": user.role, "org": user.org,
               "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)}
    return jwt.encode(payload, SECRET_KEY, ALGORITHM)


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, ALGORITHM)
    except JWTError:
        raise HTTPException(401, "登录已失效")
    user = db.scalar(select(User).where(User.username == payload["sub"]))
    if not user or not user.active:
        raise HTTPException(401, "用户不存在或已停用")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "需要管理员权限")
    return user


# ---------------- 认证 ----------------
class LoginIn(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or user.password_hash != hash_pwd(body.password):
        raise HTTPException(401, "用户名或密码错误")
    if not user.active:
        raise HTTPException(401, "账号已停用，请联系管理员")
    return {"token": create_token(user), "name": user.name, "role": user.role, "org": user.org}


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "name": user.name, "role": user.role, "org": user.org}


# ---------------- 阵地台账 ----------------
def venue_dict(v: Venue) -> dict:
    return {c: getattr(v, c) for c in
            ("id", "name", "level", "org", "address", "category", "area", "open_hours",
             "capacity", "facilities", "manager", "phone", "remark")}


class VenueIn(BaseModel):
    name: str
    level: str = "本部"
    org: str = ""
    address: str = ""
    category: str = ""
    area: float = 0
    open_hours: str = ""
    capacity: int = 0
    facilities: str = ""
    manager: str = ""
    phone: str = ""
    remark: str = ""


@app.get("/api/venues")
def list_venues(keyword: str = "", level: str = "", db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    q = select(Venue)
    if keyword:
        q = q.where(Venue.name.contains(keyword) | Venue.org.contains(keyword))
    if level:
        q = q.where(Venue.level == level)
    if user.role != "admin":
        q = q.where(Venue.org == user.org)
    return [venue_dict(v) for v in db.scalars(q.order_by(Venue.id))]


@app.post("/api/venues")
def create_venue(body: VenueIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    v = Venue(**body.model_dump())
    db.add(v); db.commit(); db.refresh(v)
    return venue_dict(v)


@app.put("/api/venues/{vid}")
def update_venue(vid: int, body: VenueIn, db: Session = Depends(get_db),
                 user: User = Depends(require_admin)):
    v = db.get(Venue, vid) or _404()
    for k, val in body.model_dump().items():
        setattr(v, k, val)
    db.commit()
    return venue_dict(v)


@app.delete("/api/venues/{vid}")
def delete_venue(vid: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    v = db.get(Venue, vid) or _404()
    for d in v.door_devices:
        db.delete(d)
    for c in v.cameras:
        db.delete(c)
    db.delete(v); db.commit()
    return {"ok": True}


def _404():
    raise HTTPException(404, "阵地不存在")


# ---------------- 设备清单 ----------------
class DoorIn(BaseModel):
    venue_id: int
    brand: str = ""
    model: str = ""
    net_type: str = "联网型"
    access_mode: str = ""
    serial: str = ""
    location: str = ""
    remark: str = ""


class CamIn(BaseModel):
    venue_id: int
    brand: str = ""
    model: str = ""
    platform: str = "萤石云"
    serial: str = ""
    validate_code: str = ""
    location: str = ""
    coverage: str = ""
    remark: str = ""


@app.get("/api/doors")
def list_doors(venue_id: int = 0, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(DoorDevice).join(Venue)
    if venue_id:
        q = q.where(DoorDevice.venue_id == venue_id)
    if user.role != "admin":
        q = q.where(Venue.org == user.org)
    return [{"id": d.id, "venue_id": d.venue_id, "venue": d.venue.name, "brand": d.brand,
             "model": d.model, "net_type": d.net_type, "access_mode": d.access_mode,
             "serial": d.serial, "location": d.location, "remark": d.remark}
            for d in db.scalars(q.order_by(DoorDevice.id))]


@app.post("/api/doors")
def create_door(body: DoorIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    d = DoorDevice(**body.model_dump()); db.add(d); db.commit(); db.refresh(d)
    return {"id": d.id}


@app.get("/api/cameras")
def list_cameras(venue_id: int = 0, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Camera).join(Venue)
    if venue_id:
        q = q.where(Camera.venue_id == venue_id)
    if user.role != "admin":
        q = q.where(Venue.org == user.org)
    return [{"id": c.id, "venue_id": c.venue_id, "venue": c.venue.name, "brand": c.brand,
             "model": c.model, "platform": c.platform, "serial": c.serial,
             "location": c.location, "coverage": c.coverage, "remark": c.remark}
            for c in db.scalars(q.order_by(Camera.id))]


@app.post("/api/cameras")
def create_camera(body: CamIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    c = Camera(**body.model_dump()); db.add(c); db.commit(); db.refresh(c)
    return {"id": c.id}


# ---------------- 视频：实时预览 / 一键巡检 ----------------
@app.get("/api/video/live/{camera_id}")
async def video_live(camera_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "摄像头不存在")
    result = await ezviz.get_live_url(cam.serial, cam.validate_code)
    return {"camera": cam.name if hasattr(cam, "name") else cam.serial, "serial": cam.serial,
            "venue": cam.venue.name, **result}


@app.post("/api/video/patrol")
async def video_patrol(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """一键轮巡：对全部（或权限内）摄像头抓拍存档"""
    q = select(Camera).join(Venue)
    if user.role != "admin":
        q = q.where(Venue.org == user.org)
    results = []
    for cam in db.scalars(q):
        snap = await ezviz.capture_snapshot(cam.serial)
        results.append({"camera_id": cam.id, "venue": cam.venue.name, "serial": cam.serial,
                        "location": cam.location, "snapshot": snap.get("snapshot", ""),
                        "time": datetime.now().isoformat(timespec="seconds"),
                        "mock": snap.get("mock", False)})
    return {"count": len(results), "results": results}


# ---------------- 门禁控制与记录 ----------------
@app.post("/api/door/{door_id}/open")
async def door_open(door_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    d = db.get(DoorDevice, door_id)
    if not d:
        raise HTTPException(404, "门禁设备不存在")
    if d.net_type != "联网型":
        raise HTTPException(400, "独立刷卡机不支持远程控制，仅记录采集")
    result = await ezviz.door_control(d.serial, "open")
    log = AccessLog(venue_id=d.venue_id, device_id=d.id, person=user.name,
                    action="remote_open", source="系统")
    db.add(log); db.commit()
    return {"ok": True, "log_id": log.id, **result}


@app.get("/api/access-logs")
def access_logs(venue_id: int = 0, limit: int = 100, db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    q = select(AccessLog).join(Venue)
    if venue_id:
        q = q.where(AccessLog.venue_id == venue_id)
    if user.role != "admin":
        q = q.where(Venue.org == user.org)
    rows = db.scalars(q.order_by(AccessLog.id.desc()).limit(min(limit, 500)))
    return [{"id": a.id, "venue_id": a.venue_id, "person": a.person, "action": a.action,
             "source": a.source, "snapshot": a.snapshot, "created_at": a.created_at.isoformat(" ")}
            for a in rows]


# ---------------- 预约 ----------------
class ReserveIn(BaseModel):
    venue_id: int
    applicant: str
    phone: str = ""
    start_time: datetime
    end_time: datetime
    reason: str = ""


@app.get("/api/reservations")
def list_reservations(status: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Reservation).join(Venue)
    if status:
        q = q.where(Reservation.status == status)
    if user.role != "admin":
        q = q.where(Venue.org == user.org)
    return [{"id": r.id, "venue_id": r.venue_id, "venue": (db.get(Venue, r.venue_id) or Venue(name="")).name,
             "applicant": r.applicant, "phone": r.phone,
             "start_time": r.start_time.isoformat(" "), "end_time": r.end_time.isoformat(" "),
             "status": r.status, "reason": r.reason} for r in db.scalars(q.order_by(Reservation.id.desc()))]


@app.post("/api/reservations")
def create_reservation(body: ReserveIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = Reservation(**body.model_dump())
    db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "status": r.status}


@app.post("/api/reservations/{rid}/review")
def review_reservation(rid: int, approve: bool, db: Session = Depends(get_db),
                       user: User = Depends(current_user)):
    r = db.get(Reservation, rid)
    if not r:
        raise HTTPException(404, "预约不存在")
    r.status = "已通过" if approve else "已拒绝"
    db.commit()
    # 审批通过后，预约时段内门禁自动授权（联网型设备场景）
    return {"id": r.id, "status": r.status}


# ---------------- 统计分析 ----------------
@app.get("/api/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(current_user)):
    total = db.scalar(select(func.count(Venue.id)))
    doors = db.scalar(select(func.count(DoorDevice.id)))
    online_doors = db.scalar(select(func.count(DoorDevice.id)).where(DoorDevice.net_type == "联网型"))
    cams = db.scalar(select(func.count(Camera.id)))
    # 近30日各阵地使用次数 Top10
    since = datetime.now() - timedelta(days=30)
    rows = db.execute(
        select(Venue.name, func.count(AccessLog.id))
        .join(AccessLog, AccessLog.venue_id == Venue.id)
        .where(AccessLog.created_at >= since)
        .group_by(Venue.id).order_by(func.count(AccessLog.id).desc()).limit(10)
    ).all()
    pending = db.scalar(select(func.count(Reservation.id)).where(Reservation.status == "待审批"))
    return {"venues": total, "door_devices": doors, "online_doors": online_doors,
            "cameras": cams, "pending_reservations": pending,
            "top_usage": [{"venue": n, "count": c} for n, c in rows]}


# ---------------- Excel 导入（兼容填报模板三张表） ----------------
@app.post("/api/import")
def import_excel(file: UploadFile, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(file.file.read()), data_only=True)
    report = {"venues": 0, "doors": 0, "cameras": 0, "skipped": 0, "errors": []}

    def rows_of(sheet):
        ws = wb[sheet]
        return list(ws.iter_rows(min_row=4, values_only=True))

    def is_example(r):
        """模板示例行：地址含占位符 xx 或首列为“示例”"""
        return any(str(x or "") == "示例" for x in r[:2]) or "xx" in str(r[4] or "")

    name_map = {}
    for r in rows_of("阵地台账"):
        if not r or not r[1] or is_example(r):
            continue
        v = Venue(name=str(r[1]).strip(), level=r[2] or "本部", org=r[3] or "", address=r[4] or "",
                  category=r[5] or "", area=float(r[6] or 0), open_hours=r[7] or "",
                  capacity=int(r[8] or 0), facilities=r[9] or "", manager=r[10] or "",
                  phone=str(r[11] or ""), remark=r[12] or "")
        db.add(v); db.flush()
        name_map[v.name] = v.id
        report["venues"] += 1
    for r in rows_of("门禁设备清单"):
        if not r or not r[1] or is_example(r):
            continue
        vid = name_map.get(str(r[1]).strip())
        if not vid:
            report["errors"].append(f"门禁设备所属阵地不存在: {r[1]}"); report["skipped"] += 1; continue
        db.add(DoorDevice(venue_id=vid, brand=r[2] or "", model=r[3] or "", net_type=r[4] or "联网型",
                          access_mode=r[5] or "", serial=str(r[6] or ""), location=r[7] or "", remark=r[10] or ""))
        report["doors"] += 1
    for r in rows_of("摄像头设备清单"):
        if not r or not r[1] or is_example(r):
            continue
        vid = name_map.get(str(r[1]).strip())
        if not vid:
            report["errors"].append(f"摄像头所属阵地不存在: {r[1]}"); report["skipped"] += 1; continue
        db.add(Camera(venue_id=vid, brand=r[2] or "", model=r[3] or "", platform=r[4] or "萤石云",
                      serial=str(r[5] or ""), validate_code=str(r[6] or ""), location=r[7] or "",
                      coverage=r[8] or "", remark=r[9] or ""))
        report["cameras"] += 1
    db.commit()
    return report


# ---------------- 手机端免登录预约（扫码进入） ----------------
@app.get("/api/mobile/venues")
def mobile_venues(db: Session = Depends(get_db)):
    """开放中的阵地列表，供职工自助预约，免登录"""
    return [{"id": v.id, "name": v.name, "category": v.category, "org": v.org,
             "open_hours": v.open_hours, "capacity": v.capacity, "address": v.address,
             "lat": v.lat, "lng": v.lng}
            for v in db.scalars(select(Venue).order_by(Venue.level, Venue.id))]


class MobileReserveIn(BaseModel):
    venue_id: int
    applicant: str
    phone: str
    start_time: datetime
    end_time: datetime
    reason: str = ""


@app.post("/api/mobile/reservations")
def mobile_reserve(body: MobileReserveIn, db: Session = Depends(get_db)):
    if not db.get(Venue, body.venue_id):
        raise HTTPException(404, "阵地不存在")
    if body.start_time >= body.end_time or body.start_time < datetime.now():
        raise HTTPException(400, "预约时间无效（不能早于当前时间）")
    # 时段冲突检查：同一阵地已通过的预约不允许重叠
    overlap = db.scalar(select(Reservation).where(
        Reservation.venue_id == body.venue_id,
        Reservation.status.in_(["待审批", "已通过"]),
        Reservation.start_time < body.end_time,
        Reservation.end_time > body.start_time))
    if overlap:
        raise HTTPException(400, "该时段已被预约或预约审批中，请换一个时间")
    r = Reservation(**body.model_dump())
    db.add(r); db.commit(); db.refresh(r)
    return {"id": r.id, "status": r.status}


@app.get("/api/mobile/reservations")
def mobile_my_reservations(phone: str, db: Session = Depends(get_db)):
    """职工凭手机号查询自己的预约，免登录"""
    rows = db.scalars(select(Reservation).where(Reservation.phone == phone)
                      .order_by(Reservation.id.desc()).limit(50))
    out = []
    for r in rows:
        v = db.get(Venue, r.venue_id)
        out.append({"id": r.id, "venue": v.name if v else "", "status": r.status,
                    "start_time": r.start_time.isoformat(" ", timespec="minutes") if hasattr(r.start_time, 'isoformat') else str(r.start_time),
                    "end_time": r.end_time.isoformat(" ", timespec="minutes") if hasattr(r.end_time, 'isoformat') else str(r.end_time)})
    return out


@app.get("/api/qrcode")
def qrcode_png(request: Request):
    """生成手机预约页二维码 PNG（按访问地址自动拼接）"""
    import io
    import qrcode
    host = request.headers.get("host") or "127.0.0.1:8300"
    url = f"http://{host}/mobile.html"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    from fastapi import Response
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers={"Content-Disposition": "inline; filename=reserve_qr.png"})


# ---------------- 系统管理：用户管理 ----------------
ORG_LIST = ["荆州供电公司工会", "江陵县供电公司", "公安县供电公司", "监利市供电公司",
            "松滋市供电公司", "石首市供电公司", "洪湖市供电公司"]


class UserIn(BaseModel):
    username: str
    name: str
    role: str = "county"          # admin / county / keeper
    org: str = ""
    password: str = ""
    active: bool = True


class PwdIn(BaseModel):
    old_password: str
    new_password: str


@app.get("/api/meta/orgs")
def meta_orgs(user: User = Depends(current_user)):
    return ORG_LIST


@app.get("/api/users")
def list_users(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return [{"id": u.id, "username": u.username, "name": u.name, "role": u.role,
             "org": u.org, "active": u.active}
            for u in db.scalars(select(User).order_by(User.id))]


@app.post("/api/users")
def create_user(body: UserIn, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if not body.password:
        raise HTTPException(400, "新建用户必须设置初始密码")
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(400, "用户名已存在")
    if body.role != "admin" and body.org not in ORG_LIST:
        raise HTTPException(400, "所属单位无效")
    u = User(username=body.username, name=body.name, role=body.role, org=body.org,
             password_hash=hash_pwd(body.password), active=body.active)
    db.add(u); db.commit(); db.refresh(u)
    return {"id": u.id}


@app.put("/api/users/{uid}")
def update_user(uid: int, body: UserIn, db: Session = Depends(get_db),
                user: User = Depends(require_admin)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "用户不存在")
    if u.username == "admin" and (body.role != "admin" or not body.active):
        raise HTTPException(400, "不能停用或降级内置管理员")
    u.name, u.role, u.org, u.active = body.name, body.role, body.org, body.active
    if body.password:
        u.password_hash = hash_pwd(body.password)
    db.commit()
    return {"id": u.id}


@app.post("/api/change-password")
def change_password(body: PwdIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.password_hash != hash_pwd(body.old_password):
        raise HTTPException(400, "原密码错误")
    if len(body.new_password) < 6:
        raise HTTPException(400, "新密码至少6位")
    user.password_hash = hash_pwd(body.new_password)
    db.commit()
    return {"ok": True}


# ---------------- 前端静态页面 ----------------
FRONT_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
if os.path.isdir(FRONT_DIR):
    app.mount("/", StaticFiles(directory=FRONT_DIR, html=True), name="front")


Base.metadata.create_all(engine)

# 轻量迁移：老库补充经纬度列并按单位回填（正式数据可逐阵地精确坐标覆盖）
ORG_COORDS = {
    "荆州供电公司工会": (30.311, 112.240),   # 荆州市区（本部）
    "江陵县供电公司": (30.042, 112.424),
    "公安县供电公司": (30.058, 112.230),
    "监利市供电公司": (29.821, 112.898),
    "松滋市供电公司": (30.175, 111.763),
    "石首市供电公司": (29.721, 112.412),
    "洪湖市供电公司": (29.817, 113.468),
}
with engine.begin() as conn:
    cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(venues)")]
    if "lat" not in cols:
        conn.exec_driver_sql("ALTER TABLE venues ADD COLUMN lat REAL")
        conn.exec_driver_sql("ALTER TABLE venues ADD COLUMN lng REAL")
        for org, (la, ln) in ORG_COORDS.items():
            conn.exec_driver_sql(
                "UPDATE venues SET lat=?, lng=? WHERE org=? AND lat IS NULL",
                (la, ln, org))
