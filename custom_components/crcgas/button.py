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
    """设置按钮实体"""
    # 从hass.data获取coordinator和api（使用独立key，与__init__.py解耦）
    hass_domain = hass.data.get(DOMAIN, {})
    coordinator = hass_domain.get(f"{config_entry.entry_id}_coordinator")
    api = hass_domain.get(f"{config_entry.entry_id}_api")
    cons_no = hass_domain.get(f"{config_entry.entry_id}_cons_no") or config_entry.data.get("cons_no", "")
    
    if not coordinator or not api:
        _LOGGER.warning("无法设置按钮实体: coordinator或api未初始化")
        return
        
    buttons = [
        FetchHistoryButton(hass, config_entry, coordinator, api, cons_no),
        RefreshDataButton(hass, config_entry, coordinator),
    ]
    
    async_add_entities(buttons)
    _LOGGER.info(f"华润燃气按钮实体已注册: {len(buttons)}个")


class FetchHistoryButton(ButtonEntity):
    """抓取历史记录按钮"""
    
    _attr_has_entity_name = True
    _attr_name = "抓取历史记录"
    _attr_icon = "mdi:history"
    
    def __init__(self, hass, config_entry, coordinator, api, cons_no):
        self.hass = hass
        self.coordinator = coordinator
        self.api = api
        self.cons_no = cons_no
        self.config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_fetch_history"
        
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
        
        from .history_storage import async_setup_history_storage
        
        storage = await async_setup_history_storage(self.hass, self.config_entry.entry_id)
        
        try:
            result = await storage.async_fetch_all_bills(self.api, self.cons_no)
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
    
    def __init__(self, hass, config_entry, coordinator):
        self.hass = hass
        self.coordinator = coordinator
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
        """按钮按下时触发"""
        _LOGGER.info("用户触发: 手动刷新数据")
        await self.coordinator.async_request_refresh()
