"""华润燃气 API封装"""

import logging
from typing import Any, Dict, Optional

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
    ):
        self.refresh_token = refresh_token
        self.bo_token = bo_token
        self.wx_code = wx_code
        self._headers = {
            "Content-Type": "application/json",
            "refresh-token": refresh_token,
            "bo-token": bo_token,
            "wxCode": wx_code,
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """确保客户端已创建"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                headers=self._headers,
                timeout=30.0,
            )
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """发送请求"""
        client = await self._ensure_client()
        url = f"{BASE_URL}{endpoint}"

        _LOGGER.debug(f"请求: {method} {url}")
        _LOGGER.debug(f"Headers: {self._headers}")

        try:
            response = await client.request(
                method,
                endpoint,
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
        """刷新 Token"""
        return await self._request("POST", API_DO_REFRESH_TOKEN)

    async def async_get_login_info(self) -> Dict[str, Any]:
        """获取登录信息"""
        return await self._request("GET", API_GET_LOGIN_INFO)

    async def async_get_binding_cons(self) -> Dict[str, Any]:
        """获取绑定的用户"""
        return await self._request("GET", API_GET_BINDING_CONS)

    async def async_get_gas_bill_list(self, cons_no: str) -> Dict[str, Any]:
        """获取账单列表"""
        params = {"consNo": cons_no}
        return await self._request("GET", API_GET_GAS_BILL_LIST, params=params)

    async def async_get_bill_detail(self, cons_no: str, bill_id: str) -> Dict[str, Any]:
        """获取账单详情"""
        params = {"consNo": cons_no, "billId": bill_id}
        return await self._request("GET", API_GET_BILL_DETAIL, params=params)

    async def async_query_arrears(self, cons_no: str) -> Dict[str, Any]:
        """查询欠费"""
        params = {"consNo": cons_no}
        return await self._request("GET", API_QUERY_ARREARS, params=params)

    async def async_get_bo_token(self) -> Dict[str, Any]:
        """获取 BO Token"""
        return await self._request("GET", API_GET_BO_TOKEN)

    async def async_query_pay_history(self, cons_no: str) -> Dict[str, Any]:
        """查询缴费历史"""
        params = {"consNo": cons_no}
        return await self._request("GET", API_QUERY_PAY_HISTORY, params=params)

    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
