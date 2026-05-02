"""华润燃气 Home Assistant 集成"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .api import HuarunGasApi, SessionTimeoutError
from .const import (
    CONF_BO_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_WX_CODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    TOKEN_EXPIRE_THRESHOLD,
    TOKEN_REFRESH_INTERVAL,
)
from . import sensor  # noqa: F401  # 预导入避免 Event Loop 阻塞

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info(f"设置华润燃气集成: {entry.title}")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = dict(entry.data)

    # ========== 独立 Token 刷新定时器 ==========
    # 创建 API 实例用于定时刷新 Token（与 sensor.py 中的是同一个引用，在 sensor setup 后共享）
    refresh_token = entry.data.get(CONF_REFRESH_TOKEN, "")
    bo_token = entry.data.get(CONF_BO_TOKEN, "")
    wx_code = entry.data.get(CONF_WX_CODE, "")

    async def on_token_refresh(new_refresh_token: str, new_bo_token: str):
        """Token刷新后持久化到 config_entry"""
        _LOGGER.info("独立定时器: 保存新Token到config_entry")
        new_data = {**entry.data}
        new_data[CONF_REFRESH_TOKEN] = new_refresh_token
        new_data[CONF_BO_TOKEN] = new_bo_token
        hass.config_entries.async_update_entry(entry, data=new_data)

    session = async_get_clientsession(hass)
    api = HuarunGasApi(refresh_token, bo_token, wx_code, on_token_refresh, session=session)

    # 存储到 hass.data，供 sensor.py 复用
    hass.data[DOMAIN][f"{entry.entry_id}_api"] = api

    async def _async_refresh_token(now=None):
        """独立定时器回调：每小时主动刷新 Token"""
        try:
            # 先检查是否即将过期，避免无谓请求
            if api.is_token_expiring_soon(threshold_seconds=int(TOKEN_EXPIRE_THRESHOLD.total_seconds())):
                _LOGGER.info("独立定时器: Token即将过期，开始刷新...")
                await api.async_refresh_token()
                _LOGGER.info("独立定时器: Token刷新成功")
            else:
                remaining = api.get_token_remaining_seconds()
                _LOGGER.debug(f"独立定时器: Token仍有效，剩余{remaining}秒，跳过刷新")
        except SessionTimeoutError:
            _LOGGER.error("独立定时器: Token刷新失败(会话超时)，Token已完全失效，需要重新登录")
        except Exception as e:
            _LOGGER.error(f"独立定时器: Token刷新异常: {e}")

    # 启动独立定时器：每小时执行一次
    cancel_timer = async_track_time_interval(
        hass,
        _async_refresh_token,
        TOKEN_REFRESH_INTERVAL,
    )
    hass.data[DOMAIN][f"{entry.entry_id}_token_timer_cancel"] = cancel_timer
    _LOGGER.info(f"独立Token刷新定时器已启动，间隔: {TOKEN_REFRESH_INTERVAL}")

    # 启动后立即执行一次 Token 检查
    hass.async_create_task(_async_refresh_token())

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info(f"卸载华润燃气集成: {entry.title}")

    # 取消独立 Token 刷新定时器
    cancel_timer = hass.data[DOMAIN].pop(f"{entry.entry_id}_token_timer_cancel", None)
    if cancel_timer:
        cancel_timer()
        _LOGGER.info("独立Token刷新定时器已取消")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_coordinator", None)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_api", None)
    return unload_ok
