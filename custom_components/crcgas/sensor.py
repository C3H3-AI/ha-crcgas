"""华润燃气 传感器平台"""

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import HuarunGasApi
from .const import (
    CONF_BO_TOKEN,
    CONF_CONS_NO,
    CONF_REFRESH_TOKEN,
    CONF_WX_CODE,
    DOMAIN,
    SENSOR_TYPES,
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

    api = HuarunGasApi(refresh_token, bo_token, wx_code)

    async def async_update_data():
        """更新数据"""
        try:
            # 获取欠费信息
            arrears_data = await api.async_query_arrears(cons_no)

            # 获取账单列表
            bill_data = await api.async_get_gas_bill_list(cons_no)

            # 处理数据
            result = {
                "arrears": arrears_data.get("amount", 0),
                "last_bill_amount": 0,
                "last_bill_gas": 0,
                "last_mr_date": "未知",
                "total_consumption": 0,
            }

            # 解析账单详情
            bills = bill_data.get("list", [])
            if bills:
                last_bill = bills[0]
                result["last_bill_amount"] = last_bill.get("amount", 0)
                result["last_bill_gas"] = last_bill.get("gas", 0)
                result["last_mr_date"] = last_bill.get("mrDate", "未知")

            _LOGGER.debug(f"更新数据: {result}")
            return result

        except Exception as e:
            _LOGGER.error(f"更新数据失败: {e}")
            raise

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(minutes=30),
    )

    await coordinator.async_config_entry_first_refresh()

    # 创建传感器
    entities = [
        HuarunGasSensor(coordinator, sensor_type)
        for sensor_type in SENSOR_TYPES
    ]
    async_add_entities(entities)
