"""华润燃气 传感器平台"""

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_time_interval

from .api import HuarunGasApi
from .const import (
    CONF_BO_TOKEN,
    CONF_CONS_NO,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_WX_CODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SENSOR_TYPES,
    TOKEN_REFRESH_INTERVAL,
    TOKEN_EXPIRE_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)


class HuarunGasSensor(Entity):
    """华润燃气传感器基类"""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_type: str):
        self.coordinator = coordinator
        self.sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}"
        self._attr_name = SENSOR_TYPES[sensor_type]["name"]
        self._attr_icon = SENSOR_TYPES[sensor_type].get("icon")
        self._attr_native_unit_of_measurement = SENSOR_TYPES[sensor_type].get("unit")

    @property
    def device_info(self) -> Dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": "华润燃气",
            "manufacturer": "华润燃气",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """添加到 Home Assistant"""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """更新状态"""
        await self.coordinator.async_request_refresh()

    @property
    def native_value(self):
        """获取传感器值"""
        data = self.coordinator.data
        if not data:
            return None

        # 高价值传感器
        if self.sensor_type == "arrears":
            return data.get("arrears", 0)
        elif self.sensor_type == "account_balance":
            return data.get("account_balance", 0)
        elif self.sensor_type == "last_pay_time":
            return data.get("last_pay_time", "未知")
        elif self.sensor_type == "last_pay_amount":
            return data.get("last_pay_amount", 0)
        elif self.sensor_type == "annual_pay_count":
            return data.get("annual_pay_count", 0)
        elif self.sensor_type == "this_read":
            return data.get("this_read", 0)
        elif self.sensor_type == "this_read_time":
            return data.get("this_read_time", "未知")
        elif self.sensor_type == "step1_gas_used":
            return data.get("step1_gas_used", 0)
        # 中等价值传感器
        elif self.sensor_type == "cons_addr":
            return data.get("cons_addr", "未知")
        elif self.sensor_type == "org_name":
            return data.get("org_name", "未知")
        elif self.sensor_type == "gas_nature":
            return data.get("gas_nature", "未知")
        elif self.sensor_type == "purchase_style":
            return data.get("purchase_style", "未知")
        elif self.sensor_type == "last_month_gas":
            return data.get("last_month_gas", 0)
        elif self.sensor_type == "year_avg_gas":
            return data.get("year_avg_gas", 0)
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """设置传感器"""
    refresh_token = config_entry.data[CONF_REFRESH_TOKEN]
    bo_token = config_entry.data[CONF_BO_TOKEN]
    wx_code = config_entry.data[CONF_WX_CODE]
    cons_no = config_entry.data.get(CONF_CONS_NO, "")

    # Token刷新回调：保存新token到config_entry
    async def on_token_refresh(new_refresh_token: str, new_bo_token: str):
        """Token刷新后保存"""
        _LOGGER.info("保存新Token到config_entry")
        new_data = {**config_entry.data}
        new_data[CONF_REFRESH_TOKEN] = new_refresh_token
        new_data[CONF_BO_TOKEN] = new_bo_token
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    api = HuarunGasApi(refresh_token, bo_token, wx_code, on_token_refresh)

    # 获取配置的扫描间隔，默认1小时
    scan_interval_hours = config_entry.data.get(
        CONF_SCAN_INTERVAL,
        int(DEFAULT_SCAN_INTERVAL.total_seconds() / 3600)
    )
    scan_interval = timedelta(hours=scan_interval_hours)
    _LOGGER.info(f"使用数据更新间隔: {scan_interval_hours}小时")

    # ========== 1. Token刷新协调器（每10分钟） ==========
    token_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_token",
        update_method=api.async_refresh_token,
        update_interval=TOKEN_REFRESH_INTERVAL,
    )

    # 启动Token刷新定时器
    await token_coordinator.async_config_entry_first_refresh()
    _LOGGER.info("Token自动刷新协调器已启动")

    # 初始Token验证和刷新
    try:
        _LOGGER.info("初始化Token验证...")
        result = await api.async_refresh_token()
        if result:
            _LOGGER.info("Token验证成功")
        else:
            _LOGGER.warning("Token验证返回空，可能已过期")
    except Exception as e:
        _LOGGER.error(f"Token初始化失败: {e}")
        # 继续启动，让定时器继续尝试刷新

    # ========== 2. 数据更新协调器 ==========
    async def async_update_data():
        """更新数据 - 各接口独立容错，任一失败不影响其他"""
        result = {
            # 高价值
            "arrears": 0,
            "account_balance": 0,
            "last_pay_time": "未知",
            "last_pay_amount": 0,
            "annual_pay_count": 0,
            "this_read": 0,
            "this_read_time": "未知",
            "step1_gas_used": 0,
            # 中等价值
            "cons_addr": "未知",
            "org_name": "未知",
            "gas_nature": "未知",
            "purchase_style": "未知",
            "last_month_gas": 0,
            "year_avg_gas": 0,
        }

        # 检查token是否即将过期（少于5分钟），如果是则强制刷新
        if api.is_token_expiring_soon(threshold_seconds=int(TOKEN_EXPIRE_THRESHOLD.total_seconds())):
            _LOGGER.warning(f"Token即将过期（剩余{api.get_token_remaining_seconds()}秒），强制刷新...")
            try:
                await api.async_refresh_token()
            except Exception as e:
                _LOGGER.error(f"强制刷新Token失败: {e}")

        # 1. 获取欠费信息
        try:
            arrears_data = await api.async_query_arrears(cons_no)
            if arrears_data:
                data = arrears_data.get("dataResult", {})
                result["arrears"] = float(data.get("totalAmt", 0) or 0)
                result["account_balance"] = float(data.get("totalBal", 0) or 0)
        except Exception as e:
            _LOGGER.error(f"获取欠费信息失败: {e}")

        # 2. 获取缴费历史
        try:
            pay_data = await api.async_query_pay_history(cons_no)
            if pay_data and pay_data.get("success"):
                pay_result = pay_data.get("dataResult", [])
                if isinstance(pay_result, list) and pay_result:
                    # 最近缴费
                    last_pay = pay_result[0]
                    result["last_pay_time"] = last_pay.get("payTime", "未知")
                    result["last_pay_amount"] = float(last_pay.get("payAmount", 0) or 0)
                    # 年度缴费次数（今年）
                    import datetime
                    current_year = str(datetime.datetime.now().year)
                    result["annual_pay_count"] = sum(1 for p in pay_result if current_year in str(p.get("payTime", "")))
        except Exception as e:
            _LOGGER.error(f"获取缴费历史失败: {e}")

        # 3. 获取账单列表（获取抄表日期）
        try:
            bill_data = await api.async_get_gas_bill_list(cons_no, page=1, page_num=6)
            if bill_data and bill_data.get("success"):
                data_result = bill_data.get("dataResult", {})
                bills = data_result.get("data", []) if isinstance(data_result, dict) else []
                if bills:
                    last_bill = bills[0]
                    # 本期表读数和抄表时间从 getBillDetail 获取，这里只记录账单年月
                    result["_last_bill_ym"] = last_bill.get("billYm", "")
                    result["_last_app_no"] = last_bill.get("applicationNo", "")
        except Exception as e:
            _LOGGER.error(f"获取账单列表失败: {e}")

        # 4. 获取月度用气图表数据
        try:
            chart_data = await api.async_get_gas_bill_list4chart(cons_no)
            if chart_data and chart_data.get("success"):
                dr = chart_data.get("dataResult", {})
                if isinstance(dr, dict):
                    last_gas = dr.get("lastGas", [])
                    if len(last_gas) > 1:
                        result["last_month_gas"] = last_gas[1]
                    # 计算年度月均（取有数据的月份）
                    all_gas = [g for g in last_gas if g is not None]
                    if all_gas:
                        result["year_avg_gas"] = round(sum(all_gas) / len(all_gas), 1)
        except Exception as e:
            _LOGGER.error(f"获取月度用气图表失败: {e}")

        # 5. 获取账单详情（一档用气量、本期读数）
        try:
            bill_ym = result.get("_last_bill_ym", "")
            app_no = result.get("_last_app_no", "")
            if bill_ym and app_no:
                detail_data = await api.async_get_bill_detail(cons_no, bill_ym, app_no)
                if detail_data and detail_data.get("success"):
                    details = detail_data.get("dataResult", [])
                    if details and isinstance(details, list):
                        detail = details[0]
                        result["this_read"] = detail.get("thisRead", 0)
                        result["this_read_time"] = detail.get("thisReadTime", "未知")
                        step_list = detail.get("gasStepList", [])
                        for step in step_list:
                            if "一档" in step.get("stepType", ""):
                                result["step1_gas_used"] = step.get("gasUsed", 0)
                                break
        except Exception as e:
            _LOGGER.error(f"获取账单详情失败: {e}")

        # 6. 获取绑定信息（地址、公司等）
        try:
            binding_data = await api.async_get_binding_cons()
            if binding_data and binding_data.get("success"):
                cons_list = binding_data.get("dataResult", [])
                if isinstance(cons_list, list) and cons_list:
                    cons_info = cons_list[0]
                    result["cons_addr"] = cons_info.get("consAddr", "未知")
                    result["org_name"] = cons_info.get("orgName", "未知")
                    result["gas_nature"] = cons_info.get("gasNature", "未知") or "天然气"
                    result["purchase_style"] = cons_info.get("purchaseGasStyle", "未知")
        except Exception as e:
            _LOGGER.error(f"获取绑定信息失败: {e}")

        _LOGGER.debug(f"更新数据: {result}")
        return result

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    # 创建传感器
    entities = [
        HuarunGasSensor(coordinator, sensor_type)
        for sensor_type in SENSOR_TYPES
    ]
    async_add_entities(entities)
