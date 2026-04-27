"""华润燃气 API封装 - v1.0.8

修复: httpx → aiohttp (HA内置，零外部依赖)
"""

import base64
import json
import logging
import time
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Callable, Awaitable

from .const import (
    API_DO_REFRESH_TOKEN,
    API_GET_BINDING_CONS,
    API_GET_BILL_DETAIL,
    API_GET_BO_TOKEN,
    API_GET_GAS_BILL_LIST,
    API_GET_LOGIN_INFO,
    API_QUERY_ARREARS,
    API_QUERY_PAY_HISTORY,
    BASE_URL,
)

_LOGGER = logging.getLogger(__name__)


class SessionTimeoutError(Exception):
    """会话超时/Token失效异常"""
    pass


class HuarunGasApi:
    """华润燃气 API客户端 - 使用 aiohttp（HA内置）"""

    def __init__(
        self,
        refresh_token: str,
        bo_token: str,
        wx_code: str,
        on_token_refresh: Optional[Callable[[str, str], Awaitable[None]]] = None,
        session=None,  # 外部注入aiohttp session（从HA获取）
    ):
        self.refresh_token = refresh_token
        self.bo_token = bo_token
        self.wx_code = wx_code
        self._on_token_refresh = on_token_refresh
        self._session = session  # aiohttp.ClientSession

    def _decode_jwt_payload(self, token: str) -> Optional[Dict[str, Any]]:
        """解码JWT payload获取过期时间"""
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
        except Exception as e:
            _LOGGER.warning(f"JWT解码失败: {e}")
            return None

    def get_token_remaining_seconds(self, token: str = None) -> Optional[int]:
        """获取token剩余有效时间（秒）"""
        token = token or self.bo_token
        payload = self._decode_jwt_payload(token)
        if not payload:
            return None
        exp = payload.get('exp', 0)
        current = int(time.time())
        remaining = exp - current
        return max(0, remaining)

    def is_token_expiring_soon(self, threshold_seconds: int = 300) -> bool:
        """检查token是否即将过期（默认5分钟阈值）"""
        remaining = self.get_token_remaining_seconds()
        if remaining is None:
            return False
        return remaining < threshold_seconds

    @staticmethod
    def _is_session_timeout(data: Dict[str, Any]) -> bool:
        """
        检测华润API的特殊错误格式。
        
        华润API的错误响应：
          {"success": true, "msg": "会话超时", "statusCode": "SESSION_TIMEOUT", "dataResult": "2048458744932626432"}
        
        成功响应：
          {"success": true, "msg": "操作成功", "dataResult": {dict or list}}
        """
        msg = data.get("msg", "")
        status_code = data.get("statusCode", "")
        data_result = data.get("dataResult")

        if "会话超时" in msg:
            return True
        if "SESSION_TIMEOUT" in str(status_code).upper():
            return True
        if "系统繁忙" in msg:
            return True
        if isinstance(data_result, str):
            if data_result.isdigit() and len(data_result) > 10:
                return True
        return False

    def _get_headers(self) -> dict:
        """获取请求头（动态更新token）"""
        return {
            "Content-Type": "application/json;charset=UTF-8",
            "refresh-token": self.refresh_token,
            "bo-token": self.bo_token,
            "wxCode": self.wx_code,
            # 微信小程序必需请求头
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 "
                "Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI"
            ),
            "xweb_xhr": "1",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://servicewechat.com/wx34991921b0f92df7/46/page-frame.html",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        发送请求，自动检测会话超时等业务错误。
        使用注入的 aiohttp session。
        """
        url = f"{BASE_URL}{endpoint}"
        headers = self._get_headers()

        _LOGGER.debug(f"请求: {method} {url}")

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                timeout=30,
                **kwargs,
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    _LOGGER.error(f"HTTP {response.status}: {text[:200]}")
                    raise Exception(f"HTTP {response.status}: {text[:100]}")

                data = await response.json()

                # 检测华润API的"假成功"错误响应
                if self._is_session_timeout(data):
                    raise SessionTimeoutError(f"{data.get('msg')} ({data.get('statusCode')})")

                return data

        except SessionTimeoutError:
            raise
        except asyncio.TimeoutError:
            _LOGGER.error(f"请求超时: {method} {url}")
            raise Exception(f"请求超时: {url}")
        except Exception as e:
            _LOGGER.error(f"请求异常 ({type(e).__name__}): {e}")
            raise

    async def async_refresh_token(self) -> Dict[str, Any]:
        """
        刷新 Token。
        返回成功: {"refresh-token": "...", "bo-token": "..."}
        返回失败: {} 或抛出异常
        """
        url = f"{BASE_URL}{API_DO_REFRESH_TOKEN}"
        headers = self._get_headers()

        _LOGGER.info("开始刷新Token...")

        try:
            async with self._session.get(url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    _LOGGER.error(f"刷新Token HTTP错误: {response.status}")
                    return {}

                data = await response.json()

                _LOGGER.debug(f"刷新Token原始响应: {data}")

                if self._is_session_timeout(data):
                    _LOGGER.error(f"Token刷新失败(会话超时): {data.get('msg')}")
                    raise SessionTimeoutError(f"{data.get('msg')}")

                if not data.get("success"):
                    _LOGGER.error(f"Token刷新失败: {data.get('msg')}")
                    raise Exception(f"Token刷新失败: {data.get('msg')}")

                result = data.get("dataResult", {})
                
                if not isinstance(result, dict):
                    _LOGGER.warning(f"Token刷新返回非字典: type={type(result).__name__}, val={str(result)[:100]}")
                    return {}

                new_refresh_token = result.get("refresh-token") or result.get("refreshToken")
                new_bo_token = result.get("bo-token") or result.get("boToken")
                new_wx_code = result.get("wxCode") or result.get("wxcode")

                if new_refresh_token and new_bo_token:
                    old_rt = self.refresh_token[:30] if len(self.refresh_token) > 30 else self.refresh_token
                    self.refresh_token = new_refresh_token
                    self.bo_token = new_bo_token
                    if new_wx_code:
                        self.wx_code = new_wx_code

                    if self._on_token_refresh:
                        await self._on_token_refresh(new_refresh_token, new_bo_token)

                    _LOGGER.info("Token刷新成功!")
                    return {"refresh-token": new_refresh_token, "bo-token": new_bo_token}
                else:
                    _LOGGER.warning(f"Token刷新缺少字段: keys={list(result.keys()) if isinstance(result, dict) else 'N/A'}")
                    return {}

        except SessionTimeoutError:
            raise
        except Exception as e:
            _LOGGER.error(f"Token刷新异常: {e}")
            raise

    async def async_get_login_info(self) -> Dict[str, Any]:
        """获取登录信息"""
        return await self._request("GET", API_GET_LOGIN_INFO)

    async def async_get_binding_cons(self) -> Dict[str, Any]:
        """获取绑定的用户信息"""
        return await self._request("GET", API_GET_BINDING_CONS)

    async def async_get_gas_bill_list(self, cons_no: str, page: int = 1, page_num: int = 6) -> Dict[str, Any]:
        """获取账单列表"""
        params = {"consNo": cons_no, "page": page, "pageNum": page_num}
        return await self._request("GET", API_GET_GAS_BILL_LIST, params=params)

    async def async_get_bill_detail(self, cons_no: str, bill_ym: str, application_no: str) -> Dict[str, Any]:
        """获取账单详情 - 参数: billYm + consNo + applicationNo"""
        params = {"consNo": cons_no, "billYm": bill_ym, "applicationNo": application_no}
        return await self._request("GET", API_GET_BILL_DETAIL, params=params)

    async def async_get_gas_bill_list4chart(self, cons_no: str) -> Dict[str, Any]:
        """获取月度用气量图表数据"""
        params = {"consNo": cons_no}
        return await self._request("GET", "/bill/getGasBillList4Chart", params=params)

    async def async_query_arrears(self, cons_no: str) -> Dict[str, Any]:
        """查询欠费 - POST请求，JSON body"""
        order_time = datetime.now().strftime("%Y%m%d%H%M%S")
        payload = {
            "busiType": 1,
            "consNo": cons_no,
            "orderTime": order_time,
            "onlyQuery": 1
        }
        return await self._request("POST", API_QUERY_ARREARS, json=payload)

    async def async_get_bo_token(self) -> Dict[str, Any]:
        """获取 BO Token"""
        return await self._request("GET", API_GET_BO_TOKEN)

    async def async_query_pay_history(self, cons_no: str, page: int = 1, page_num: int = 12, start_ym: str = "2020-01", end_ym: str = "2100-12") -> Dict[str, Any]:
        """查询缴费历史"""
        params = {"consNo": cons_no, "page": page, "pageNum": page_num, "startYm": start_ym, "endYm": end_ym}
        return await self._request("GET", API_QUERY_PAY_HISTORY, params=params)
