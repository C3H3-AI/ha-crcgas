"""华润燃气 配置流程"""

import logging

import httpx
import homeassistant.helpers.config_validation as config_validation
from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

from .const import (
    API_GET_BINDING_CONS,
    BASE_URL,
    CONF_AREA,
    CONF_BO_TOKEN,
    CONF_CONS_ADDR,
    CONF_CONS_NAME,
    CONF_CONS_NO,
    CONF_MOBILE,
    CONF_REFRESH_TOKEN,
    CONF_SERVICE_PASSWORD,
    CONF_WX_CODE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# 配置表单
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REFRESH_TOKEN): str,
        vol.Required(CONF_BO_TOKEN): str,
        vol.Required(CONF_WX_CODE): str,
        vol.Optional(CONF_SERVICE_PASSWORD, default=""): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """华润燃气配置流程"""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input=None):
        """用户配置步骤"""
        errors = {}

        if user_input is not None:
            refresh_token = user_input[CONF_REFRESH_TOKEN]
            bo_token = user_input[CONF_BO_TOKEN]
            wx_code = user_input[CONF_WX_CODE]

            # 验证 tokens 并获取户号信息
            try:
                result = await self._validate_and_get_cons(
                    refresh_token, bo_token, wx_code
                )
                if result.get("success"):
                    cons_info = result.get("cons_info", {})
                    # 合并用户输入和户号信息
                    final_data = {
                        **user_input,
                        CONF_CONS_NO: cons_info.get("consNo", ""),
                        CONF_CONS_NAME: cons_info.get("consName", ""),
                        CONF_CONS_ADDR: cons_info.get("consAddr", ""),
                        CONF_MOBILE: cons_info.get("mobile", ""),
                        CONF_AREA: cons_info.get("area", ""),
                    }
                    return self.async_create_entry(
                        title=f"华润燃气 ({cons_info.get('consNo', '未知户号')})",
                        data=final_data,
                    )
                else:
                    errors["base"] = result.get("error", "auth_failed")
            except Exception as e:
                _LOGGER.error(f"验证失败: {e}")
                errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )

    async def _validate_and_get_cons(
        self, refresh_token: str, bo_token: str, wx_code: str
    ) -> dict:
        """验证 tokens 并获取户号信息"""
        headers = {
            "Content-Type": "application/json",
            "refresh-token": refresh_token,
            "bo-token": bo_token,
            "wxCode": wx_code,
        }

        try:
            async with httpx.AsyncClient(
                base_url=BASE_URL, headers=headers, timeout=30.0
            ) as client:
                response = await client.get(API_GET_BINDING_CONS)
                response.raise_for_status()
                data = response.json()

                _LOGGER.debug(f"验证响应: {data}")

                if data.get("code") == 0 or data.get("code") == "0":
                    cons_list = data.get("list", []) or data.get("data", [])
                    if cons_list:
                        return {
                            "success": True,
                            "cons_info": cons_list[0],
                        }
                    else:
                        return {"success": False, "error": "no_binding"}
                else:
                    return {"success": False, "error": "auth_failed"}

        except httpx.HTTPStatusError as e:
            _LOGGER.error(f"HTTP错误: {e.response.status_code}")
            return {"success": False, "error": "auth_failed"}
        except Exception as e:
            _LOGGER.error(f"验证异常: {e}")
            return {"success": False, "error": "auth_failed"}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """获取选项配置流程"""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """选项配置流程"""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """初始化选项"""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_REFRESH_TOKEN,
                    default=self.config_entry.data.get(CONF_REFRESH_TOKEN),
                ): str,
                vol.Required(
                    CONF_BO_TOKEN,
                    default=self.config_entry.data.get(CONF_BO_TOKEN),
                ): str,
                vol.Required(
                    CONF_WX_CODE,
                    default=self.config_entry.data.get(CONF_WX_CODE),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
