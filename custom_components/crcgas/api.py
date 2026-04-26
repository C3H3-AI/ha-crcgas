"""华润燃气 API封装"""

import base64
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Callable, Awaitable

import httpx

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


class HuarunGasApi:
    """华润燃气 API客户端"""

    def __init__(
        self,
        refresh_token: str,
        bo_token: str,
        wx_code: str,
        on_token_refresh: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ):
        self.refresh_token = refresh_token
        self.bo_token = bo_token
        self.wx_code = wx_code
        self._on_token_refresh = on_token_refresh  # Token刷新回调
        self._client: Optional[httpx.AsyncClient] = None

    def _decode_jwt_payload(self, token: str) -> Optional[Dict[str, Any]]:
        """解码JWT payload获取过期时间"""
        try:
            # JWT格式: header.payload.signature
            parts = token.split('.')
            if len(parts) != 3:
                return None
            # Base64URL解码payload
            payload = parts[1]
            # 补全padding
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
            return False  # 无法判断时保守处理
        return remaining < threshold_seconds

    def _get_headers(self) -> dict:
        """获取请求头（动态更新token）"""
        return {
            "Content-Type": "application/json;charset=UTF-8",
            "refresh-token": self.refresh_token,
            "bo-token": self.bo_token,
            "wxCode": self.wx_code,
            # 微信小程序必需请求头
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf254186b) XWEB/19481",
            "xweb_xhr": "1",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://servicewechat.com/wx34991921b0f92df7/46/page-frame.html",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        """确保客户端已创建"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                headers=self._get_headers(),
                timeout=30.0,
            )
        return self._client

    async def _rebuild_client(self):
        """重建客户端（token更新后）"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """发送请求"""
        client = await self._ensure_client()
        url = f"{BASE_URL}{endpoint}"
        headers = self._get_headers()

        _LOGGER.debug(f"请求: {method} {url}")
        _LOGGER.debug(f"Headers: refresh-token={self.refresh_token[:30]}...")

        try:
            response = await client.request(
                method,
                endpoint,
                headers=headers,  # 每次请求都用最新的headers
                **kwargs,
            )
            response.raise_for_status()
            data = response.json()
            _LOGGER.debug(f"响应: {data}")
            return data
        except httpx.HTTPStatusError as e:
            _LOGGER.error(f"HTTP错误: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            _LOGGER.error(f"请求异常: {e}")
            raise

    async def async_refresh_token(self) -> Dict[str, Any]:
        """
        刷新 Token
        返回: {"refresh-token": "...", "bo-token": "..."}
        """
        client = await self._ensure_client()
        headers = self._get_headers()
        url = f"{BASE_URL}{API_DO_REFRESH_TOKEN}"

        _LOGGER.info("开始刷新Token...")

        try:
            # GET请求，不需要body
            response = await client.get(
                API_DO_REFRESH_TOKEN,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            _LOGGER.debug(f"刷新Token响应: {data}")

            # 检查是否成功
            if data.get("success"):
                result = data.get("dataResult", {})
                new_refresh_token = result.get("refresh-token")
                new_bo_token = result.get("bo-token")

                if new_refresh_token and new_bo_token:
                    # 更新本地token
                    self.refresh_token = new_refresh_token
                    self.bo_token = new_bo_token
                    await self._rebuild_client()

                    # 调用回调保存新token
                    if self._on_token_refresh:
                        await self._on_token_refresh(new_refresh_token, new_bo_token)

                    _LOGGER.info("Token刷新成功!")
                    return {"refresh-token": new_refresh_token, "bo-token": new_bo_token}
                else:
                    _LOGGER.warning(f"Token刷新响应缺少token: {result}")
                    return {}
            else:
                # SESSION_TIMEOUT 等错误
                _LOGGER.error(f"Token刷新失败: {data.get('msg')} ({data.get('statusCode')})")
                raise Exception(f"Token刷新失败: {data.get('msg')}")

        except Exception as e:
            _LOGGER.error(f"Token刷新异常: {e}")
            raise

    async def async_get_login_info(self) -> Dict[str, Any]:
        """获取登录信息"""
        return await self._request("GET", API_GET_LOGIN_INFO)

    async def async_get_binding_cons(self) -> Dict[str, Any]:
        """获取绑定的用户"""
        return await self._request("GET", API_GET_BINDING_CONS)

    async def async_get_gas_bill_list(self, cons_no: str, page: int = 1, page_num: int = 6) -> Dict[str, Any]:
        """获取账单列表"""
        params = {"consNo": cons_no, "page": page, "pageNum": page_num}
        return await self._request("GET", API_GET_GAS_BILL_LIST, params=params)

    async def async_get_bill_detail(self, cons_no: str, bill_ym: str, application_no: str) -> Dict[str, Any]:
        """获取账单详情 - 抓包确认参数: billYm + consNo + applicationNo"""
        params = {"consNo": cons_no, "billYm": bill_ym, "applicationNo": application_no}
        return await self._request("GET", API_GET_BILL_DETAIL, params=params)

    async def async_get_gas_bill_list4chart(self, cons_no: str) -> Dict[str, Any]:
        """获取月度用气量图表数据"""
        params = {"consNo": cons_no}
        return await self._request("GET", "/bill/getGasBillList4Chart", params=params)

    async def async_query_arrears(self, cons_no: str) -> Dict[str, Any]:
        """查询欠费 - POST请求，需要JSON body"""
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
        """查询缴费历史 - 需要 startYm/endYm/page/pageNum"""
        params = {"consNo": cons_no, "page": page, "pageNum": page_num, "startYm": start_ym, "endYm": end_ym}
        return await self._request("GET", API_QUERY_PAY_HISTORY, params=params)

    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
