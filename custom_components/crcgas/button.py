"""华润燃气 按钮平台

提供按钮实体用于手动触发操作：
1. 抓取所有历史记录
2. 刷新数据
"""

import logging
from typing import Any, Dict

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """设置按钮实体 - 延迟加载模式
    
    不再在 setup 时立即获取 coordinator/api，改为在实体添加到 hass 后
    或按钮按下时才获取，彻底解决平台并行加载时的时序问题。
    """
    buttons = [
        FetchHistoryButton(hass, config_entry),
        RefreshDataButton(hass, config_entry),
    ]

    async_add_entities(buttons)
    _LOGGER.info(f"华润燃气按钮实体已注册: {len(buttons)}个")


class FetchHistoryButton(ButtonEntity):
    """抓取历史记录按钮"""

    _attr_has_entity_name = True
    _attr_name = "抓取历史记录"
    _attr_icon = "mdi:history"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self.hass = hass
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_fetch_history"
        self._api = None
        self._cons_no = None

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "华润燃气",
            "manufacturer": "华润燃气",
            "model": "燃气抄表",
        }

    async def async_added_to_hass(self) -> None:
        """实体添加到 HA 后，获取 api 和 cons_no"""
        hass_domain = self.hass.data.get(DOMAIN, {})
        self._api = hass_domain.get(f"{self.config_entry.entry_id}_api")
        self._cons_no = hass_domain.get(
            f"{self.config_entry.entry_id}_cons_no"
        ) or self.config_entry.data.get("cons_no", "")

    async def async_press(self) -> None:
        """按钮按下时触发"""
        if not self._api:
            _LOGGER.error("api 未初始化，请稍后重试或重启 Home Assistant")
            return

        _LOGGER.info("用户触发：抓取历史记录")
        try:
            from .history_storage import async_setup_history_storage

            storage = await async_setup_history_storage(
                self.hass, self.config_entry.entry_id
            )
            if self._cons_no:
                result = await storage.async_fetch_all_bills(self._api, self._cons_no)
                self.hass.bus.async_fire(
                    "crcgas_history_updated",
                    {"success": True, "count": len(result) if result else 0},
                )
                _LOGGER.info(f"历史记录抓取完成: {len(result) if result else 0}条")
            else:
                _LOGGER.warning("cons_no 为空，跳过历史记录抓取")
        except Exception as e:
            _LOGGER.error(f"抓取历史记录失败: {e}")
            self.hass.bus.async_fire(
                "crcgas_history_updated", {"success": False, "error": str(e)}
            )


class RefreshDataButton(ButtonEntity):
    """刷新数据按钮"""

    _attr_has_entity_name = True
    _attr_name = "刷新数据"
    _attr_icon = "mdi:refresh"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self.hass = hass
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_refresh"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "华润燃气",
            "manufacturer": "华润燃气",
            "model": "燃气抄表",
        }

    async def async_press(self) -> None:
        """按钮按下时触发 - 延迟获取 coordinator"""
        hass_domain = self.hass.data.get(DOMAIN, {})
        coordinator = hass_domain.get(f"{self.config_entry.entry_id}_coordinator")

        if not coordinator:
            _LOGGER.error("coordinator 未初始化，请稍后重试或重启 Home Assistant")
            return

        _LOGGER.info("用户触发：刷新数据")
        await coordinator.async_request_refresh()
