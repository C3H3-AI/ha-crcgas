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

        if self.sensor_type == "arrears":
            return data.get("arrears", 0)
        elif self.sensor_type == "last_bill_amount":
            return data.get("last_bill_amount", 0)
        elif self.sensor_type == "last_bill_gas":
            return data.get("last_bill_gas", 0)
        elif self.sensor_type == "last_mr_date":
            return data.get("last_mr_date", "未知")
        elif self.sensor_type == "total_consumption":
            return data.get("total_consumption", 0)
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
            "arrears": 0,
            "last_bill_amount": 0,
            "last_bill_gas": 0,
            "last_mr_date": "未知",
            "total_consumption": 0,
        }

        # 检查token是否即将过期（少于5分钟），如果是则强制刷新
        if api.is_token_expiring_soon(threshold_seconds=int(TOKEN_EXPIRE_THRESHOLD.total_seconds())):
            _LOGGER.warning(f"Token即将过期（剩余{api.get_token_remaining_seconds()}秒），强制刷新...")
            try:
                await api.async_refresh_token()
            except Exception as e:
                _LOGGER.error(f"强制刷新Token失败: {e}")

        # 获取欠费信息（独立容错）
        try:
            arrears_data = await api.async_query_arrears(cons_no)
            if arrears_data:
                result["arrears"] = arrears_data.get("amount", arrears_data.get("arrears", 0))
        except Exception as e:
            _LOGGER.error(f"获取欠费信息失败: {e}")

        # 获取账单列表（独立容错）
        try:
            bill_data = await api.async_get_gas_bill_list(cons_no, page=1, page_num=6)
            if bill_data:
                bills = bill_data.get("dataResult", []) or bill_data.get("list", [])
                if bills:
                    last_bill = bills[0]
                    result["last_bill_amount"] = last_bill.get("amount", 0)
                    result["last_bill_gas"] = last_bill.get("gas", 0)
                    result["last_mr_date"] = last_bill.get("mrDate", "未知")
        except Exception as e:
            _LOGGER.error(f"获取账单列表失败: {e}")

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
