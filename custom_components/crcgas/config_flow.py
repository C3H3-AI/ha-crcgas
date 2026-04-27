"""华润燃气 配置流程 - v1.0.9

修复：
1. OptionsFlow 500 错误（HA 2024.7+ 不再通过 __init__ 接收 config_entry）
2. scan_interval 支持四种单位：小时/天/周/月
3. 输入验证：根据单位限制合理范围
"""

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_UNIT,
    CONF_WX_CODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SCAN_INTERVAL_UNITS,
)

_LOGGER = logging.getLogger(__name__)


def _build_interval_schema(default_value=1, default_unit="month"):
    """构建扫描间隔表单 Schema"""
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=default_value,
            ): vol.All(
                vol.Coerce(int),
            ),
            vol.Required(
                CONF_SCAN_INTERVAL_UNIT,
                default=default_unit,
            ): vol.In(SCAN_INTERVAL_UNITS),
        }
    )


def _validate_interval(value, unit):
    """验证数值是否符合单位要求（定时/间隔语义）"""
    if unit == "hour":
        if not 1 <= value <= 24:
            return "间隔小时数请输入 1-24"
    elif unit == "day":
        if not 0 <= value <= 23:
            return "日模式请输入 0-23（表示每天几点更新，如20表示每天20:00）"
    elif unit == "week":
        if not 1 <= value <= 7:
            return "周模式请输入 1-7（1=周一，7=周日）"
    elif unit == "month":
        if not 1 <= value <= 31:
            return "月模式请输入 1-31（表示每月几号更新）"
    return None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(self, user_input=None):
        """初始配置步骤"""
        errors = {}
        if user_input is not None:
            refresh_token = user_input[CONF_REFRESH_TOKEN]
            bo_token = user_input[CONF_BO_TOKEN]
            wx_code = user_input[CONF_WX_CODE]

            # 验证扫描间隔
            interval_val = user_input.get(CONF_SCAN_INTERVAL, 1)
            interval_unit = user_input.get(CONF_SCAN_INTERVAL_UNIT, "month")
            validation_error = _validate_interval(interval_val, interval_unit)
            if validation_error:
                errors[CONF_SCAN_INTERVAL] = validation_error
            else:
                try:
                    result = await self._validate_and_get_cons(refresh_token, bo_token, wx_code)
                    if result.get("success"):
                        cons_info = result["cons_info"]
                        final_data = {
                            CONF_REFRESH_TOKEN: refresh_token,
                            CONF_BO_TOKEN: bo_token,
                            CONF_WX_CODE: wx_code,
                            CONF_CONS_NO: cons_info.get("consNo", ""),
                            CONF_CONS_NAME: cons_info.get("consName", ""),
                            CONF_CONS_ADDR: cons_info.get("consAddr", ""),
                            CONF_MOBILE: cons_info.get("mobile", ""),
                            CONF_AREA: cons_info.get("area", ""),
                            CONF_SCAN_INTERVAL: int(interval_val),
                            CONF_SCAN_INTERVAL_UNIT: interval_unit,
                        }
                        return self.async_create_entry(
                            title=f"华润燃气 ({cons_info.get('consNo', '未知户号')})",
                            data=final_data,
                        )
                    else:
                        err_key = result.get("error", "auth_failed")
                        error_msgs = {
                            "auth_failed": "Token验证失败，请检查是否过期",
                            "no_binding": "未找到绑定户号",
                            "session_timeout": "会话已超时，请重新获取Token",
                            "network_error": "无法连接到华润燃气服务器",
                        }
                        errors["base"] = error_msgs.get(err_key, "验证失败")
                except Exception as e:
                    _LOGGER.exception(f"验证 tokens 异常: {e}")
                    errors["base"] = "unknown_error"

        return self.async_show_form(
            step_id="user",
            data_schema=_build_interval_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """重新配置步骤"""
        reconfigure_entry = self._get_reconfigure_entry()
        if reconfigure_entry is None:
            return self.async_abort(reason="cannot_reconfigure")

        errors = {}

        if user_input is not None:
            refresh_token = user_input[CONF_REFRESH_TOKEN]
            bo_token = user_input[CONF_BO_TOKEN]
            wx_code = user_input[CONF_WX_CODE]

            # 验证扫描间隔
            interval_val = user_input.get(CONF_SCAN_INTERVAL, 1)
            interval_unit = user_input.get(CONF_SCAN_INTERVAL_UNIT, "month")
            validation_error = _validate_interval(interval_val, interval_unit)
            if validation_error:
                errors[CONF_SCAN_INTERVAL] = validation_error
            else:
                try:
                    result = await self._validate_and_get_cons(refresh_token, bo_token, wx_code)
                    if result.get("success"):
                        cons_info = result["cons_info"]
                        final_data = {
                            CONF_REFRESH_TOKEN: refresh_token,
                            CONF_BO_TOKEN: bo_token,
                            CONF_WX_CODE: wx_code,
                            CONF_CONS_NO: cons_info.get("consNo", ""),
                            CONF_CONS_NAME: cons_info.get("consName", ""),
                            CONF_CONS_ADDR: cons_info.get("consAddr", ""),
                            CONF_MOBILE: cons_info.get("mobile", ""),
                            CONF_AREA: cons_info.get("area", ""),
                            CONF_SCAN_INTERVAL: int(interval_val),
                            CONF_SCAN_INTERVAL_UNIT: interval_unit,
                        }
                        return self.async_update_reload_and_abort(
                            reconfigure_entry,
                            data_updates=final_data,
                        )
                    else:
                        errors["base"] = result.get("error", "auth_failed")
                except Exception as e:
                    _LOGGER.exception(f"重新配置异常: {e}")
                    errors["base"] = "unknown_error"

        # 读取当前值
        current_val = reconfigure_entry.data.get(CONF_SCAN_INTERVAL, 1)
        current_unit = reconfigure_entry.data.get(CONF_SCAN_INTERVAL_UNIT, "month")

        reconfigure_schema = vol.Schema(
            {
                vol.Required(
                    CONF_REFRESH_TOKEN,
                    default=reconfigure_entry.data.get(CONF_REFRESH_TOKEN, "")
                ): str,
                vol.Required(
                    CONF_BO_TOKEN,
                    default=reconfigure_entry.data.get(CONF_BO_TOKEN, "")
                ): str,
                vol.Required(
                    CONF_WX_CODE,
                    default=reconfigure_entry.data.get(CONF_WX_CODE, "")
                ): str,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current_val,
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(
                    CONF_SCAN_INTERVAL_UNIT,
                    default=current_unit,
                ): vol.In(SCAN_INTERVAL_UNITS),
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=reconfigure_schema,
            errors=errors,
        )

    async def _validate_and_get_cons(self, refresh_token, bo_token, wx_code):
        """验证 tokens 并获取户号信息"""
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "refresh-token": refresh_token,
            "bo-token": bo_token,
            "wxCode": wx_code,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 "
                "Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI"
            ),
            "xweb_xhr": "1",
            "Sec-Fetch-Site": "cross-site",
            "Referer": "https://servicewechat.com/wx34991921b0f92df7/46/page-frame.html",
        }

        url = f"{BASE_URL}{API_GET_BINDING_CONS}"

        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    _LOGGER.warning(f"绑定查询HTTP错误: {response.status}")
                    return {"success": False, "error": "network_error"}

                data = await response.json()

                msg = data.get("msg", "")
                status_code = data.get("statusCode", "")

                if "会话超时" in msg or "SESSION_TIMEOUT" in str(status_code).upper():
                    _LOGGER.warning(f"Token验证返回会话超时: {msg}")
                    return {"success": False, "error": "session_timeout"}

                if data.get("success") and data.get("statusCode") == "200":
                    cons_list = data.get("dataResult", [])
                    if isinstance(cons_list, list) and cons_list:
                        return {"success": True, "cons_info": cons_list[0]}
                    else:
                        _LOGGER.info(f"无绑定户号: {data}")
                        return {"success": False, "error": "no_binding"}
                else:
                    _LOGGER.warning(f"Token验证失败: success={data.get('success')}, msg={msg}, statusCode={status_code}")
                    return {"success": False, "error": "auth_failed"}

        except TimeoutError:
            _LOGGER.error("连接华润燃气服务器超时")
            return {"success": False, "error": "network_error"}
        except Exception as e:
            _LOGGER.exception(f"验证请求异常: {type(e).__name__}: {e}")
            return {"success": False, "error": "network_error"}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """返回选项配置流程"""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """选项配置流程 - 修改扫描间隔"""

    async def async_step_init(self, user_input=None):
        """扫描间隔设置步骤"""
        if user_input is not None:
            # 验证输入
            interval_val = user_input.get(CONF_SCAN_INTERVAL, 1)
            interval_unit = user_input.get(CONF_SCAN_INTERVAL_UNIT, "hour")
            error = _validate_interval(interval_val, interval_unit)
            if error:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_build_interval_schema(interval_val, interval_unit),
                    errors={CONF_SCAN_INTERVAL: error},
                )
            return self.async_create_entry(title="", data=user_input)

        # 读取当前值（优先 options，其次 data）
        current_val = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, 1)
        )
        current_unit = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_UNIT,
            self.config_entry.data.get(CONF_SCAN_INTERVAL_UNIT, "hour")
        )

        return self.async_show_form(
            step_id="init",
            data_schema=_build_interval_schema(current_val, current_unit),
        )
