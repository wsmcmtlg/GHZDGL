# -*- coding: utf-8 -*-
"""视频接入适配层。
MOCK=true 时返回模拟播放地址与快照，跑通全流程；
接入真实萤石云时设置环境变量 EZVIZ_APP_KEY / EZVIZ_APP_SECRET，即可切换。
"""
import os
import time
import hashlib
import httpx

MOCK = not os.environ.get("EZVIZ_APP_KEY")

TOKEN_CACHE = {"token": None, "expire": 0}
EZVIZ_API = "https://open.ys7.com/api/lapp"


async def _get_token() -> str:
    if MOCK:
        return "mock-token"
    if TOKEN_CACHE["token"] and time.time() < TOKEN_CACHE["expire"]:
        return TOKEN_CACHE["token"]
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{EZVIZ_API}/token/get", data={
            "appKey": os.environ["EZVIZ_APP_KEY"],
            "appSecret": os.environ["EZVIZ_APP_SECRET"],
        })
        data = r.json()["data"]
        TOKEN_CACHE["token"] = data["accessToken"]
        TOKEN_CACHE["expire"] = time.time() + data.get("expireTime", 7200) - 300
        return TOKEN_CACHE["token"]


async def get_live_url(serial: str, validate_code: str = "") -> dict:
    """获取摄像头实时播放地址（萤石云 ezopen 协议）"""
    if MOCK:
        return {"url": f"ezopen://mock@open.ys7.com/{serial}/1.live",
                "mock": True, "expire": 300}
    token = await _get_token()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{EZVIZ_API}/v2/live/address/get", data={
            "accessToken": token, "deviceSerial": serial, "protocol": 2, "quality": 1,
        })
        return r.json()


async def capture_snapshot(serial: str) -> dict:
    """抓拍快照；mock 模式返回模拟路径"""
    if MOCK:
        ts = time.strftime("%Y%m%d%H%M%S")
        return {"snapshot": f"snapshots/mock_{serial}_{ts}.jpg", "mock": True}
    token = await _get_token()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{EZVIZ_API}/device/capture", data={
            "accessToken": token, "deviceSerial": serial,
        })
        return r.json()


async def door_control(serial: str, action: str = "open") -> dict:
    """门禁远程控制（联网型设备）。真实接入按门禁品牌 SDK 对接，此处预留。"""
    if MOCK:
        return {"ok": True, "action": action, "serial": serial, "mock": True}
    raise NotImplementedError("真实门禁 SDK 对接待设备清单确认后实现")
