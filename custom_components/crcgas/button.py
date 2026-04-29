"""华润燃气 按钮平台

提供按钮实体用于手动触发操作：
1. 抓取所有历史记录
2. 刷新数据
"""

import logging
from typing import Any, Dict, Optional

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
    """设置按钮实体 - 延迟加载模式，不在此时获取coordinator/api"""
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
        self._api: Optional[Any] = None
        self._cons_no: Optional[str] = None
        self._attr_unique_id = f"{config_entry.entry_id}_fetch_history"

    async def async_added_to_hass(self) -> None:
        """添加到 Home Assistant 后获取依赖"""
        await super().async_added_to_hass()
        # 延迟获取 api 和 cons_no（等待 sensor.py 初始化完成）
        hass_domain = self.hass.data.get(DOMAIN, {})
        self._api = hass_domain.get(f"{self.config_entry.entry_id}_api")
        self._cons_no = hass_domain.get(f"{self.config_entry.entry_id}_cons_no") or self.config_entry.data.get("cons_no", "")

        if not self._api:
            _LOGGER.warning(f"按钮 {self.unique_id} 初始化时 api 未就绪，将在工作第一次触发时获取")

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "华润燃气",
            "manufacturer": "华润燃气",
            "model": "燃气抄表",
        }

    async def async_press(self) -> None:
        """按钮按下时触发"""
        _LOGGER.info("用户触发: 抓取所有历史记录")

        # 动态获取 api（如果之前未获取）
        if not self._api:
            hass_domain = self.hass.data.get(DOMAIN, {})
            self._api = hass_domain.get(f"{self.config_entry.entry_id}_api")

        if not self._api:
            _LOGGER.error("api 未初始化，请稍后重试或重启 Home Assistant")
            return

        # 动态获取 cons_no（如果之前未获取）
        if not self._cons_no:
            hass_domain = self.hass.data.get(DOMAIN, {})
            self._cons_no = hass_domain.get(f"{self.config_entry.entry_id}_cons_no") or self.config_entry.data.get("cons_no", "")

        from .history_storage import async_setup_history_storage

        storage = await async_setup_history_storage(self.hass, self.config_entry.entry_id)

        try:
            result = await storage.async_fetch_all_bills(self._api, self._cons_no)
            _LOGGER.info(
                f"历史记录抓取完成: "
                f"新增{result['new_bills']}条, "
                f"更新{result['updated_bills']}条, "
                f"总计{result['total_stored']}条"
            )

            # 触发事件通知前端
            self.hass.bus.async_fire("crcgas_history_fetched", {
                "config_entry_id": self.config_entry.entry_id,
                "result": result,
            })

        except Exception as e:
            _LOGGER.error(f"抓取历史记录失败: {e}")


class RefreshDataButton(ButtonEntity):
    """刷新数据按钮"""

    _attr_has_entity_name = True
    _attr_name = "刷新数据"
    _attr_icon = "mdi:refresh"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self.hass = hass
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_refresh_data"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "华润燃气",
            "manufacturer": "华润燃气",
            "model": "燃气抄表",
        }

    async def async_press(self) -> None:
        """按钮按下时触发 - 动态获取coordinator"""
        _LOGGER.info("用户触发: 手动刷新数据")

        hass_domain = self.hass.data.get(DOMAIN, {})
        coordinator = hass_domain.get(f"{self.config_entry.entry_id}_coordinator")

        if not coordinator:
            _LOGGER.error("coordinator 未初始化，请稍后重试或重启 Home Assistant")
            return

        await coordinator.async_request_refresh()
