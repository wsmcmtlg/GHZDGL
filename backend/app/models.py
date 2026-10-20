# -*- coding: utf-8 -*-
"""数据模型：用户、阵地、门禁设备、摄像头、门禁记录、预约"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(50))
    # role: admin=荆州公司工会(全局) / county=县公司工会 / keeper=阵地管理员
    role: Mapped[str] = mapped_column(String(20), default="county")
    org: Mapped[str] = mapped_column(String(100), default="")  # 所属单位
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Venue(Base):
    __tablename__ = "venues"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    level: Mapped[str] = mapped_column(String(10))  # 本部 / 县级公司
    org: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(50), default="")
    area: Mapped[float] = mapped_column(Float, default=0)  # ㎡
    open_hours: Mapped[str] = mapped_column(String(100), default="")
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    facilities: Mapped[str] = mapped_column(Text, default="")
    manager: Mapped[str] = mapped_column(String(50), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    lat: Mapped[float | None] = mapped_column(default=None)   # 纬度
    lng: Mapped[float | None] = mapped_column(default=None)   # 经度

    door_devices: Mapped[list["DoorDevice"]] = relationship(back_populates="venue")
    cameras: Mapped[list["Camera"]] = relationship(back_populates="venue")


class DoorDevice(Base):
    __tablename__ = "door_devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    brand: Mapped[str] = mapped_column(String(50), default="")
    model: Mapped[str] = mapped_column(String(50), default="")
    net_type: Mapped[str] = mapped_column(String(20))  # 联网型 / 独立刷卡机
    access_mode: Mapped[str] = mapped_column(String(20), default="")  # 厂商SDK/网络继电器/记录采集器
    serial: Mapped[str] = mapped_column(String(100), default="")  # 序列号/IP
    location: Mapped[str] = mapped_column(String(100), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    venue: Mapped["Venue"] = relationship(back_populates="door_devices")


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    brand: Mapped[str] = mapped_column(String(50), default="")
    model: Mapped[str] = mapped_column(String(50), default="")
    platform: Mapped[str] = mapped_column(String(30), default="萤石云")
    serial: Mapped[str] = mapped_column(String(100), default="")
    validate_code: Mapped[str] = mapped_column(String(50), default="")
    location: Mapped[str] = mapped_column(String(100), default="")
    coverage: Mapped[str] = mapped_column(String(100), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    venue: Mapped["Venue"] = relationship(back_populates="cameras")


class AccessLog(Base):
    """门禁/使用记录"""
    __tablename__ = "access_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("door_devices.id"), nullable=True)
    person: Mapped[str] = mapped_column(String(50), default="")
    action: Mapped[str] = mapped_column(String(20))  # remote_open / card_open / scheduled_open
    source: Mapped[str] = mapped_column(String(20), default="")  # 系统 / 采集器
    snapshot: Mapped[str] = mapped_column(String(300), default="")  # 关联快照路径
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)


class Member(Base):
    """工会会员/人员名单（门禁授权依据）"""
    __tablename__ = "members"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), index=True)
    org: Mapped[str] = mapped_column(String(100), default="")
    dept: Mapped[str] = mapped_column(String(100), default="")
    phone: Mapped[str] = mapped_column(String(30), default="", index=True)
    card_no: Mapped[str] = mapped_column(String(50), default="")  # 门禁卡号/工号
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    remark: Mapped[str] = mapped_column(Text, default="")


class DoorAuth(Base):
    """门禁授权记录：人员 ↔ 门禁设备"""
    __tablename__ = "door_auths"
    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    door_id: Mapped[int] = mapped_column(ForeignKey("door_devices.id"), index=True)
    granted_by: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(20), default="已授权")  # 已授权/已回收
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Reservation(Base):
    """场地预约"""
    __tablename__ = "reservations"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    applicant: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str] = mapped_column(String(30), default="")
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="待审批")  # 待审批/已通过/已拒绝/已取消
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
