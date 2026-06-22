"""华润燃气 传感器平台 - v2.0.0

v2.0.0 新增：历史累计传感器、SQLite直写统计注入、依赖零外部库、一键抓取按钮
"""

import asyncio
import json
import logging
from datetime import timedelta, datetime
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from homeassistant.components.sensor.const import SensorStateClass as _SSC

from homeassistant.components.sensor import SensorEntity as BaseSensor

from homeassistant.helpers import entity_registry as er

from .api import HuarunGasApi, SessionTimeoutError
_STATE_CLASS_MAP = {
    "this_gas_used": _SSC.TOTAL_INCREASING,
    "monthly_gas_used": _SSC.TOTAL_INCREASING,
    "step1_gas_used": _SSC.TOTAL_INCREASING,
    "step2_gas_used": _SSC.TOTAL_INCREASING,
    "annual_pay_count": _SSC.TOTAL_INCREASING,
    "this_read": _SSC.TOTAL_INCREASING,
    "total_gas_consumption": _SSC.TOTAL_INCREASING,
    "total_gas_cost": _SSC.TOTAL_INCREASING,
    "arrears": _SSC.MEASUREMENT,
    "account_balance": _SSC.MEASUREMENT,
    "last_pay_amount": _SSC.MEASUREMENT,
    "bill_amount": _SSC.MEASUREMENT,
    "estimated_gas_bill_amount": _SSC.MEASUREMENT,
    "penalty_amount": _SSC.MEASUREMENT,
    "step1_remain": _SSC.MEASUREMENT,
    "step2_remain": _SSC.MEASUREMENT,
    "year_avg_gas": _SSC.MEASUREMENT,
    "last_month_gas": _SSC.MEASUREMENT,
    "gas_price_step1": _SSC.MEASUREMENT,
    "gas_price_step2": _SSC.MEASUREMENT,
}

_DEVICE_CLASS_MAP = {
    "monthly_gas_used": "gas",
    "total_gas_consumption": "gas",
    "total_gas_cost": "monetary",
    "step1_gas_used": "gas",
    "step2_gas_used": "gas",
    "this_read": "gas",
}


from .const import (
    CONF_BO_TOKEN,
    CONF_CONS_NO,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_UNIT,
    CONF_WX_CODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    INTEGRATION_STATUS,
    SENSOR_TYPES,
    TOKEN_EXPIRE_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)


class HuarunGasSensor(BaseSensor):
    """华润燃气传感器基类"""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_type: str):
        self.coordinator = coordinator
        self.sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}"
        self._attr_name = SENSOR_TYPES[sensor_type]["name"]
        self._attr_icon = SENSOR_TYPES[sensor_type].get("icon")
        self._attr_native_unit_of_measurement = SENSOR_TYPES[sensor_type].get("unit")
        self._attr_state_class = _STATE_CLASS_MAP.get(sensor_type)
        self._attr_device_class = _DEVICE_CLASS_MAP.get(sensor_type)
        # Monetary sensors: 2 decimal places
        if _DEVICE_CLASS_MAP.get(sensor_type) == "monetary":
            self._attr_suggested_display_precision = 2

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
        # 如果协调器已有数据，立即写入状态，避免实体永远 unknown
        if self.coordinator.data is not None:
            self.async_write_ha_state()

    def _get_total_gas_consumption(self, data) -> float | None:
        """返回燃气表总表读数（持续递增，用于能源面板）"""
        this_read = data.get("this_read")
        if this_read is not None:
            return float(this_read)
        return None

    @property
    def native_value(self):
        """获取传感器值"""
        data = self.coordinator.data
        if not data:
            return None

        if self.sensor_type == "arrears":
            v = data.get("arrears")
            return float(v) if v is not None else None
        elif self.sensor_type == "account_balance":
            v = data.get("account_balance")
            return float(v) if v is not None else None
        elif self.sensor_type == "last_pay_time":
            v = data.get("last_pay_time")
            return v if v and v != "未知" else "未知"
        elif self.sensor_type == "last_pay_amount":
            v = data.get("last_pay_amount")
            return float(v) if v is not None else None
        elif self.sensor_type == "annual_pay_count":
            v = data.get("annual_pay_count")
            return float(v) if v is not None else None
        elif self.sensor_type == "this_read":
            v = data.get("this_read")
            return float(v) if v is not None else None
        elif self.sensor_type == "this_read_time":
            v = data.get("this_read_time")
            return v if v and v != "未知" else "未知"
        elif self.sensor_type == "step1_gas_used":
            v = data.get("step1_gas_used")
            return float(v) if v is not None else None
        elif self.sensor_type == "step2_gas_used":
            v = data.get("step2_gas_used")
            return float(v) if v is not None else None
        elif self.sensor_type == "this_gas_used":
            v = data.get("this_gas_used")
            return float(v) if v is not None else None
        elif self.sensor_type == "bill_amount":
            v = data.get("bill_amount")
            return float(v) if v is not None else None
        elif self.sensor_type == "step1_remain":
            v = data.get("step1_remain")
            return float(v) if v is not None else None
        elif self.sensor_type == "step2_remain":
            v = data.get("step2_remain")
            return float(v) if v is not None else None
        elif self.sensor_type == "penalty_amount":
            v = data.get("penalty_amount")
            return float(v) if v is not None else None
        elif self.sensor_type == "cons_addr":
            v = data.get("cons_addr")
            return v if v and v != "未知" else "未知"
        elif self.sensor_type == "org_name":
            v = data.get("org_name")
            return v if v and v != "未知" else "未知"
        elif self.sensor_type == "gas_nature":
            v = data.get("gas_nature")
            return v if v and v != "未知" else "天然气"
        elif self.sensor_type == "purchase_style":
            v = data.get("purchase_style")
            style_map = {"01": "IC卡", "02": "物联网表", "03": "普通表"}
            return style_map.get(v, v) if v else "未知"
        elif self.sensor_type == "last_month_gas":
            v = data.get("last_month_gas")
            return float(v) if v is not None else None
        elif self.sensor_type == "year_avg_gas":
            v = data.get("year_avg_gas")
            return float(v) if v is not None else None
        elif self.sensor_type == "integration_status":
            v = data.get("integration_status")
            return INTEGRATION_STATUS.get(v, v) if v else "unknown"
        elif self.sensor_type == "monthly_gas_used":
            v = data.get("monthly_gas_used")
            return float(v) if v is not None else None
        elif self.sensor_type == "total_gas_consumption":
            return self._get_total_gas_consumption(data)
        elif self.sensor_type == "total_gas_cost":
            v = data.get("total_gas_cost")
            return float(v) if v is not None else None
        elif self.sensor_type == "gas_price_step1":
            v = data.get("gas_price_step1")
            return float(v) if v is not None else None
        elif self.sensor_type == "gas_price_step2":
            v = data.get("gas_price_step2")
            return float(v) if v is not None else None
        elif self.sensor_type == "estimated_gas_bill_amount":
            v = data.get("estimated_gas_bill_amount")
            return float(v) if v is not None else None
        return None


class HuarunGasMeterHistorySensor(BaseSensor):
    """燃气表历史累计传感器 — 用于能源面板显示完整历史数据"""

    def __init__(self, coordinator, entry_id):
        self._coordinator = coordinator
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_gas_meter_history"
        self._attr_name = "燃气表历史累计"
        self._attr_icon = "mdi:counter"
        self._attr_native_unit_of_measurement = "m³"
        self._attr_state_class = _SSC.TOTAL_INCREASING
        self._attr_device_class = "gas"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "华润燃气",
            "manufacturer": "华润燃气",
        }

    @property
    def available(self):
        return self._coordinator.last_update_success

    @property
    def native_value(self):
        data = self._coordinator.data
        if data:
            v = data.get("this_read")
            return float(v) if v is not None else None
        return None

    async def async_added_to_hass(self):
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
        if self._coordinator.data is not None:
            self.async_write_ha_state()


async def _calculate_step_usage(result, api, cons_no):
    """计算阶梯用气量（备用方案）- 使用本月用气量"""
    try:
        this_gas_used = result.get("this_gas_used", 0)
        step1_remain = result.get("step1_remain", 0)
        step2_remain = result.get("step2_remain", 0)
        step1_gas_limit = result.get("step1_gas_limit", 330)
        step2_gas_limit = result.get("step2_gas_limit", 170)
        
        if step1_remain > 0:
            # 所有用气量都在第一档
            result["step1_gas_used"] = this_gas_used
            result["step2_gas_used"] = 0
        else:
            # 部分用气量进入第二档
            result["step1_gas_used"] = min(this_gas_used, step1_gas_limit)
            result["step2_gas_used"] = max(0, this_gas_used - step1_gas_limit)
        
        _LOGGER.info(f"计算本月阶梯用气量: 本期={this_gas_used}, 一档={result['step1_gas_used']}, 二档={result['step2_gas_used']}")
    except Exception as e:
        _LOGGER.error(f"计算阶梯用气量失败: {e}")


async def _import_history_statistics(hass, entry, bill_history, current_reading=None):
    """将历史账单数据导入 HA 统计系统，形成趋势图"""
    try:
        from homeassistant.components.recorder.statistics import (
            async_add_external_statistics,
            StatisticMetaData,
            StatisticMeanType,
        )
    except ImportError:
        _LOGGER.warning("recorder 组件不可用，无法导入历史统计")
        return

    sorted_bills = sorted(bill_history, key=lambda b: b.get("billYm", ""))
    if not sorted_bills:
        return

    from datetime import datetime, timezone, timedelta

    # 燃气用量统计
    gas_metadata = StatisticMetaData(
        has_mean=False, has_sum=True,
        name="历史月度用气量", source=DOMAIN,
        statistic_id=f"{DOMAIN}:monthly_gas_usage",
        unit_of_measurement="m³",
        mean_type=StatisticMeanType.NONE,
    )
    gas_stats = []
    cumulative_gas = 0.0
    for bill in sorted_bills:
        ym = bill.get("billYm", "")
        if not ym or len(ym) < 7: continue
        year, month = int(ym[:4]), int(ym[5:7])
        gas_amt = float(bill.get("gasAmt", 0) or 0)
        cumulative_gas += gas_amt
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        gas_stats.append({
            "start": start, "state": gas_amt, "sum": cumulative_gas,
            "min": gas_amt, "max": gas_amt, "mean": 0.0, "mean_weight": 0.0,
            "last_reset": start,
        })
    async_add_external_statistics(hass, gas_metadata, gas_stats)
    _LOGGER.info("已导入 %d 条历史用气量统计", len(gas_stats))

    # 燃气费用统计
    bill_metadata = StatisticMetaData(
        has_mean=False, has_sum=True,
        name="历史月度燃气费", source=DOMAIN,
        statistic_id=f"{DOMAIN}:monthly_bill_amount",
        unit_of_measurement="CNY",
        mean_type=StatisticMeanType.NONE,
    )
    bill_stats = []
    cumulative_bill = 0.0
    for bill in sorted_bills:
        ym = bill.get("billYm", "")
        if not ym or len(ym) < 7: continue
        year, month = int(ym[:4]), int(ym[5:7])
        bill_amt = float(bill.get("billAmt", 0) or 0)
        cumulative_bill += bill_amt
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        bill_stats.append({
            "start": start, "state": bill_amt, "sum": cumulative_bill,
            "min": bill_amt, "max": bill_amt, "mean": 0.0, "mean_weight": 0.0,
            "last_reset": start,
        })
    async_add_external_statistics(hass, bill_metadata, bill_stats)
    _LOGGER.info("已导入 %d 条历史燃气费统计", len(bill_stats))


async def _import_meter_history_to_entity(hass, entry, bill_history, only_missing=False):
    """通过 sqlite3 直接写入历史累计统计到 recorder 数据库
    only_missing=True: 只检查数据库中是否有记录，无记录时才注入（启动时用，不删除已有数据）
    only_missing=False: 先删后插（按钮触发时用）
    """
    import sqlite3
    from datetime import datetime, timezone
    import time as time_mod

    history_unique_id = f"{DOMAIN}_{entry.entry_id}_gas_meter_history"
    entity_reg = er.async_get(hass)
    entity_id = entity_reg.async_get_entity_id("sensor", DOMAIN, history_unique_id)
    if not entity_id:
        _LOGGER.warning("燃气表历史累计传感器尚未注册，跳过")
        return

    sorted_bills = sorted(bill_history, key=lambda b: b.get("billYm", ""))
    stats_data = []
    cumulative = 0.0
    for bill in sorted_bills:
        ym = bill.get("billYm", "")
        if not ym or len(ym) < 7:
            continue
        year, month = int(ym[:4]), int(ym[5:7])
        gas_amt = float(bill.get("gasAmt", 0) or 0)
        cumulative += gas_amt
        start_ts = datetime(year, month, 1, tzinfo=timezone.utc).timestamp()
        stats_data.append((start_ts, cumulative))

    if not stats_data:
        _LOGGER.warning("无账单数据，跳过历史累计注入")
        return

    db_path = hass.config.path("home-assistant_v2.db")
    now = time_mod.time()

    def _do_inject():
        conn = None
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")

            if only_missing:
                row = conn.execute(
                    "SELECT id FROM statistics_meta WHERE statistic_id = ?",
                    (entity_id,),
                ).fetchone()
                if row:
                    existing = conn.execute(
                        "SELECT COUNT(*) FROM statistics WHERE metadata_id = ?",
                        (row[0],),
                    ).fetchone()
                    if existing and existing[0] >= 10:
                        _LOGGER.info("已有 %d 条历史累计记录，跳过自动注入", existing[0])
                        conn.rollback()
                        return
                _LOGGER.info("未发现历史累计记录，执行首次自动注入")

            conn.execute(
                "INSERT OR IGNORE INTO statistics_meta "
                "(statistic_id, source, unit_of_measurement, has_mean, has_sum, name) "
                "VALUES (?, ?, ?, 0, 1, '燃气表历史累计')",
                (entity_id, DOMAIN, "m³"),
            )

            row = conn.execute(
                "SELECT id FROM statistics_meta WHERE statistic_id = ?",
                (entity_id,),
            ).fetchone()
            if row is None:
                _LOGGER.error("无法获取 statistics_meta id（statistic_id=%s）", entity_id)
                conn.rollback()
                return

            mid = row[0]
            conn.execute("DELETE FROM statistics WHERE metadata_id = ?", (mid,))
            conn.execute("DELETE FROM statistics_short_term WHERE metadata_id = ?", (mid,))

            rows = [(mid, ts, val, val, val, val, 0.0, ts, now) for ts, val in stats_data]
            conn.executemany(
                "INSERT INTO statistics "
                "(metadata_id, start_ts, state, sum, min, max, mean, last_reset_ts, created_ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

            conn.commit()
            _LOGGER.info("已注入 %d 条历史累计到 %s", len(stats_data), entity_id)
        except sqlite3.Error as e:
            _LOGGER.error("SQLite 写入历史累计失败: %s", e)
            if conn:
                conn.rollback()
        except Exception as e:
            _LOGGER.error("注入历史累计时发生意外错误: %s", e)
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    await hass.async_add_executor_job(_do_inject)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """设置传感器"""
    cons_no = config_entry.data.get(CONF_CONS_NO, "")

    # 复用 __init__.py 中创建的 API 实例（共享 Token 刷新状态）
    api = hass.data[DOMAIN].get(f"{config_entry.entry_id}_api")
    if api is None:
        # 兜底：如果 __init__ 未创建（不应发生），本地创建
        _LOGGER.warning("未找到共享API实例，本地创建（Token刷新可能不同步）")
        refresh_token = config_entry.data[CONF_REFRESH_TOKEN]
        bo_token = config_entry.data[CONF_BO_TOKEN]
        wx_code = config_entry.data[CONF_WX_CODE]

        async def on_token_refresh(new_refresh_token: str, new_bo_token: str):
            """Token刷新后保存"""
            _LOGGER.info("保存新Token到config_entry")
            new_data = {**config_entry.data}
            new_data[CONF_REFRESH_TOKEN] = new_refresh_token
            new_data[CONF_BO_TOKEN] = new_bo_token
            hass.config_entries.async_update_entry(config_entry, data=new_data)

        session = async_get_clientsession(hass)
        api = HuarunGasApi(refresh_token, bo_token, wx_code, on_token_refresh, session=session)

    # 获取配置的扫描间隔，默认1小时
    # 优先读取 options（用户通过选项流程修改），其次 data（初始配置）
    scan_interval_val = config_entry.options.get(CONF_SCAN_INTERVAL, config_entry.data.get(CONF_SCAN_INTERVAL, 1))
    scan_interval_unit = config_entry.options.get(CONF_SCAN_INTERVAL_UNIT, config_entry.data.get(CONF_SCAN_INTERVAL_UNIT, "hour"))

    # 计算实际刷新间隔（hour=小时数，day=固定1小时仅支持定时，week=固定1小时，month=固定1小时）
    # day/week/month 模式下实际刷新由 coordinator 内部逻辑决定，这里统一设为1小时兜底
    if scan_interval_unit == "hour":
        scan_interval = timedelta(hours=scan_interval_val)
    else:
        # 非小时模式：设为最小1小时，day/week/month 定时逻辑在刷新回调中处理
        scan_interval = timedelta(hours=1)
    _LOGGER.info("数据刷新间隔: %s %s（实际: %s）", scan_interval_val, scan_interval_unit, scan_interval)

    # ========== 2. 数据更新协调器 ==========
    async def async_update_data():
        """
        更新数据 - 各接口独立容错，任一失败不影响其他。
        """
        result = {
            "arrears": None,
            "account_balance": None,
            "last_pay_time": "未知",
            "last_pay_amount": None,
            "annual_pay_count": None,
            "this_read": None,
            "this_read_time": "未知",
            "step1_gas_used": None,
            "step2_gas_used": None,
            "this_gas_used": None,
            "bill_amount": None,
            "step1_remain": None,
            "step2_remain": None,
            "penalty_amount": None,
            "cons_addr": "未知",
            "org_name": "未知",
            "gas_nature": "未知",
            "purchase_style": "未知",
            "last_month_gas": None,
            "year_avg_gas": None,
            "integration_status": "unknown",
            "monthly_gas_used": None,
            "total_gas_cost": None,
        "step1_gas_limit": None,
        "step2_gas_limit": None,
        "gas_price_step1": None,
        "gas_price_step2": None,
        }
        session_timeout_count = 0
        total_api_calls = 6

        # 检查token是否即将过期
        if api.is_token_expiring_soon(threshold_seconds=int(TOKEN_EXPIRE_THRESHOLD.total_seconds())):
            _LOGGER.warning(f"Token即将过期，强制刷新...")
            try:
                await api.async_refresh_token()
            except Exception as e:
                _LOGGER.error(f"强制刷新Token失败: {e}")

        # 并行获取独立数据（欠费/缴费历史/月度图表/绑定信息）
        async def _fetch_arrears():
            try:
                d = await api.async_query_arrears(cons_no)
                if d:
                    dr = d.get("dataResult", {})
                    if isinstance(dr, dict):
                        result["arrears"] = float(dr.get("totalAmt", 0) or 0)
                        result["account_balance"] = float(dr.get("totalBal", 0) or 0)
            except Exception as e:
                _LOGGER.error("获取欠费信息失败: %s", e)
                if "SESSION_TIMEOUT" in str(e) or "会话超时" in str(e):
                    nonlocal session_timeout_count
                    session_timeout_count += 1

        async def _fetch_pay_history():
            try:
                d = await api.async_query_pay_history(cons_no)
                if d and d.get("success"):
                    pr = d.get("dataResult", [])
                    if isinstance(pr, list) and pr:
                        result["last_pay_time"] = pr[0].get("payTime", "未知")
                        result["last_pay_amount"] = float(pr[0].get("payAmount", 0) or 0)
                        result["annual_pay_count"] = sum(1 for p in pr if str(datetime.now().year) in str(p.get("payTime", "")))
            except Exception as e:
                _LOGGER.error("获取缴费历史失败: %s", e)
                if "SESSION_TIMEOUT" in str(e) or "会话超时" in str(e):
                    nonlocal session_timeout_count
                    session_timeout_count += 1

        async def _fetch_chart():
            try:
                d = await api.async_get_gas_bill_list4chart(cons_no)
                if d and d.get("success"):
                    dr = d.get("dataResult", {})
                    if isinstance(dr, dict):
                        lg = dr.get("lastGas", [])
                        if len(lg) > 1:
                            result["last_month_gas"] = lg[1]
                        valid = [g for g in lg if g is not None]
                        if valid:
                            result["year_avg_gas"] = round(sum(valid) / len(valid), 1)
            except Exception as e:
                _LOGGER.error("获取月度用气图表失败: %s", e)
                if "SESSION_TIMEOUT" in str(e) or "会话超时" in str(e):
                    nonlocal session_timeout_count
                    session_timeout_count += 1

        async def _fetch_binding():
            try:
                d = await api.async_get_binding_cons()
                if d and d.get("success"):
                    cl = d.get("dataResult", [])
                    if isinstance(cl, list) and cl:
                        result["cons_addr"] = cl[0].get("consAddr", "未知")
                        result["org_name"] = cl[0].get("orgName", "未知")
                        result["gas_nature"] = cl[0].get("gasNature", "未知") or "天然气"
                        result["purchase_style"] = cl[0].get("purchaseGasStyle", "未知")
            except Exception as e:
                _LOGGER.error("获取绑定信息失败: %s", e)
                if "SESSION_TIMEOUT" in str(e) or "会话超时" in str(e):
                    nonlocal session_timeout_count
                    session_timeout_count += 1

        await asyncio.gather(
            _fetch_arrears(), _fetch_pay_history(), _fetch_chart(), _fetch_binding(),
            return_exceptions=True,
        )

        # 3. 获取账单列表（获取抄表日期和阶梯剩余气量）
        try:
            bill_data = await api.async_get_gas_bill_list(cons_no, page=1, page_num=6)
            if bill_data and bill_data.get("success"):
                data_result = bill_data.get("dataResult", {})
                bills = data_result.get("data", []) if isinstance(data_result, dict) else []
                cons_prc_info = data_result.get("consPrcInfo", {}) if isinstance(data_result, dict) else {}
                prc_detail_list = cons_prc_info.get("consPrcDetailList", [])
                for prc_detail in prc_detail_list:
                    rule_code = prc_detail.get("ruleCode", "")
                    lev_gq_remain = prc_detail.get("levGqRemain", "")
                    if isinstance(lev_gq_remain, str):
                        lev_gq_remain = lev_gq_remain.replace(",", "")
                    if rule_code == "0201":
                        result["step1_remain"] = float(lev_gq_remain) if lev_gq_remain else 0
                        result["step1_gas_limit"] = float(prc_detail.get("levGq", 0))
                        result["step1_price"] = float(prc_detail.get("catPrc", 0))
                        result["gas_price_step1"] = float(prc_detail.get("catPrc", 0))
                    elif rule_code == "0202":
                        result["step2_remain"] = float(lev_gq_remain) if lev_gq_remain else 0
                        result["step2_gas_limit"] = float(prc_detail.get("levGq", 0))
                        result["step2_price"] = float(prc_detail.get("catPrc", 0))
                        result["gas_price_step2"] = float(prc_detail.get("catPrc", 0))
                if bills:
                    last_bill = bills[0]
                    result["_last_bill_ym"] = last_bill.get("billYm", "")
                    result["_last_app_no"] = last_bill.get("applicationNo", "")
                    result["last_bill_gas_amt"] = float(last_bill.get("gasAmt", 0) or 0)
                    result["last_bill_penalty"] = float(last_bill.get("penaltyAmt", 0) or 0)
        except Exception as e:
            _LOGGER.error(f"获取账单列表失败: {e}")
            if "SESSION_TIMEOUT" in str(e) or "会话超时" in str(e):
                session_timeout_count += 1

        # 5. 获取账单详情（本期读数、用气量、账单金额）
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
                        result["this_gas_used"] = detail.get("gasUsed", 0) or result.get("last_bill_gas_amt", 0)
                        result["bill_amount"] = detail.get("totalAmount", 0) or detail.get("billAmount", 0)
                        result["penalty_amount"] = detail.get("penaltyAmount", 0)
                        step_list = detail.get("gasStepList", [])
                        if step_list:
                            for step in step_list:
                                step_type = step.get("stepType", "")
                                gas_used = step.get("gasUsed", 0)
                                if "一阶" in step_type:
                                    result["step1_gas_used"] = gas_used
                                elif "二阶" in step_type:
                                    result["step2_gas_used"] = gas_used
                        else:
                            _LOGGER.info("gasStepList为空，尝试计算阶梯用气量")
                            await _calculate_step_usage(result, api, cons_no)
                    else:
                        result["this_gas_used"] = result.get("last_bill_gas_amt", 0)
                else:
                    result["this_gas_used"] = result.get("last_bill_gas_amt", 0)
                    result["penalty_amount"] = result.get("last_bill_penalty", 0)
            else:
                _LOGGER.warning(f"缺少账单信息: bill_ym={bill_ym}, app_no={app_no}")
        except Exception as e:
            _LOGGER.error(f"获取账单详情失败: {e}")
            if "SESSION_TIMEOUT" in str(e) or "会话超时" in str(e):
                session_timeout_count += 1
            result["this_gas_used"] = result.get("last_bill_gas_amt", 0)

        # ========== 状态判断 ==========
        if session_timeout_count >= total_api_calls:
            _LOGGER.critical(f"全部{total_api_calls}个API返回会话超时！Token已完全失效。")
            result["integration_status"] = "token_expired"
        else:
            # 简单状态判断
            if session_timeout_count > 0:
                result["integration_status"] = "token_expired"
            else:
                result["integration_status"] = "normal"

        # ========== 异常通知（通过服务调用，避免 hass.components 不可用） ==========
        status_str = hass.data.get(f"{DOMAIN}_last_status_{config_entry.entry_id}")
        new_status = result["integration_status"]
        if new_status != "normal" and new_status != status_str:
            msg = INTEGRATION_STATUS.get(new_status, new_status)
            try:
                hass.services.async_call("persistent_notification", "create", {
                    "title": "华润燃气 - 集成异常",
                    "message": f"华润燃气集成状态异常: {msg}\n\n请检查 Token 是否过期或网络是否正常。",
                    "notification_id": f"crcgas_error_{config_entry.entry_id}",
                }, blocking=False)
            except Exception:
                _LOGGER.warning("发送异常通知失败")
        elif new_status == "normal" and status_str and status_str != "normal":
            try:
                hass.services.async_call("persistent_notification", "dismiss", {
                    "notification_id": f"crcgas_error_{config_entry.entry_id}",
                }, blocking=False)
            except Exception:
                pass
        hass.data[f"{DOMAIN}_last_status_{config_entry.entry_id}"] = new_status

        # 设置月度累计用气量（暂时用本期用气量代替）
        result["monthly_gas_used"] = result.get("this_gas_used", 0)

        # 修复阶梯用气量逻辑：如果一档剩余量>0，二档用气量必须为0
        step1_remain = result.get("step1_remain", 0)
        step2_remain = result.get("step2_remain", 0)
        this_gas_used = result.get("this_gas_used", 0)
        step1_gas_limit = result.get("step1_gas_limit") or 330
        step2_gas_limit = result.get("step2_gas_limit") or 170

        # 如果gasStepList为空或数据异常，重新计算本月阶梯用气量
        if result.get("step1_gas_used", 0) == 0 and result.get("step2_gas_used", 0) == 0:
            if step1_remain > 0:
                # 所有用气量都在第一档
                result["step1_gas_used"] = this_gas_used
                result["step2_gas_used"] = 0
            else:
                # 部分用气量进入第二档
                result["step1_gas_used"] = min(this_gas_used, step1_gas_limit)
                result["step2_gas_used"] = max(0, this_gas_used - step1_gas_limit)
        else:
            # 如果已有阶梯用气量数据，确保逻辑一致性
            if step1_remain > 0 and result["step2_gas_used"] != 0:
                _LOGGER.warning(f"数据不一致：一档剩余量={step1_remain}>0，但二档用气量={result['step2_gas_used']}，强制设为0")
                result["step2_gas_used"] = 0
                # 调整一档用气量，确保总和等于本期用气量
                result["step1_gas_used"] = this_gas_used

        # 计算预估燃气账单（基于阶梯用气量和气价）
        step1_gas = result.get("step1_gas_used", 0)
        step2_gas = result.get("step2_gas_used", 0)
        price_step1 = result.get("gas_price_step1", 0)
        price_step2 = result.get("gas_price_step2", 0)
        if step1_gas + step2_gas > 0 and price_step1 > 0:
            estimated_water = step1_gas * price_step1 + step2_gas * price_step2
            result["estimated_gas_bill_amount"] = round(estimated_water, 2)
        else:
            result["estimated_gas_bill_amount"] = 0.0

        # 累计燃气费用（能源面板用）= 历史账单总和 + 当前预估账单
        try:
            from .history_storage import CRCGasHistoryStorage
            cost_storage = CRCGasHistoryStorage(hass, config_entry.entry_id)
            await cost_storage.async_load()
            cost_history = cost_storage.get_bill_history(limit=999)
            historical_cost = sum(float(b.get("billAmt", 0) or 0) for b in cost_history)
            current_cost = float(result.get("estimated_gas_bill_amount", 0) or 0)
            result["total_gas_cost"] = round(historical_cost + current_cost, 2)
        except Exception as e:
            _LOGGER.warning(f"计算累计燃气费用失败: {e}")
            result["total_gas_cost"] = None
        
        _LOGGER.info(f"数据更新完成: 欠费¥{result['arrears']}, 读数{result['this_read']}, 状态={result['integration_status']}, 一档用气量={result['step1_gas_used']}, 二档用气量={result['step2_gas_used']}")
        return result

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=scan_interval,
    )

    # 立即存储 coordinator 和 api（供 button.py 使用）
    # 必须在创建传感器之前存储，这样即使平台并行加载，按钮也能获取到
    hass.data[DOMAIN][f"{config_entry.entry_id}_coordinator"] = coordinator
    hass.data[DOMAIN][f"{config_entry.entry_id}_api"] = api
    hass.data[DOMAIN][f"{config_entry.entry_id}_cons_no"] = cons_no

    # 创建传感器
    entities = [
        HuarunGasSensor(coordinator, sensor_type)
        for sensor_type in SENSOR_TYPES
    ]
    # 新增：燃气表历史累计传感器（能源面板用）
    entities.append(HuarunGasMeterHistorySensor(coordinator, config_entry.entry_id))
    async_add_entities(entities)

    # 异步执行首次刷新 + 自动抓取历史记录
    async def async_initial_setup():
        """首次初始化：先刷新传感器数据，再自动抓取历史记录"""
        try:
            await coordinator.async_config_entry_first_refresh()
            _LOGGER.info("首次传感器数据刷新完成")
        except Exception as e:
            _LOGGER.error(f"首次传感器数据刷新失败: {e}")
            return

        # 自动抓取历史记录（仅限首次安装/无历史数据时）
        try:
            from .history_storage import async_setup_history_storage
            storage = await async_setup_history_storage(hass, config_entry.entry_id)

            bill_history = storage.get_bill_history()
            if bill_history:
                _LOGGER.debug(f"已有 {len(bill_history)} 条历史账单，跳过自动抓取")
            else:
                _LOGGER.info("首次启动，自动抓取历史记录...")
                result = await storage.async_fetch_all_bills(api, cons_no)
                _LOGGER.info(
                    f"首次自动抓取完成: "
                    f"新增{result['new_bills']}条, "
                    f"更新{result['updated_bills']}条, "
                    f"总计{result['total_stored']}条"
                )
                bill_history = storage.get_bill_history()

            if bill_history:
                current_reading = coordinator.data.get("this_read") if coordinator.data else None
                await _import_history_statistics(hass, config_entry, bill_history, current_reading)
                # 自动注入历史累计数据到统计表（首次无数据时才执行）
                try:
                    await _import_meter_history_to_entity(hass, config_entry, bill_history, only_missing=True)
                except Exception as e:
                    _LOGGER.warning(f"历史累计传感器注入失败（重启后自动重试）: {e}")
        except Exception as e:
            _LOGGER.warning(f"首次自动抓取历史记录失败（按钮可补救）: {e}")

    hass.async_create_task(async_initial_setup())
    
    # 注册服务：抓取历史记录
    async def async_fetch_history_service(call):
        """服务：抓取所有历史账单"""
        _LOGGER.info("服务触发: 抓取所有历史记录")
        from .history_storage import async_setup_history_storage
        
        storage = await async_setup_history_storage(hass, config_entry.entry_id)
        try:
            result = await storage.async_fetch_all_bills(api, cons_no)
            _LOGGER.info(
                f"历史记录抓取完成: "
                f"新增{result['new_bills']}条, "
                f"更新{result['updated_bills']}条, "
                f"总计{result['total_stored']}条"
            )
            # 导入历史统计数据（面板趋势图用）
            bill_history = storage.get_bill_history()
            if bill_history:
                coordinator = hass.data[DOMAIN].get(f"{config_entry.entry_id}_coordinator")
                current_reading = coordinator.data.get("this_read") if coordinator and coordinator.data else None
                try:
                    await _import_history_statistics(hass, config_entry, bill_history, current_reading)
                except Exception as e:
                    _LOGGER.warning("导入月度统计失败（不影响历史累计传感器）: %s", e)
                # 向历史累计传感器注入数据（能源面板用）
                try:
                    await _import_meter_history_to_entity(hass, config_entry, bill_history)
                except Exception as e:
                    _LOGGER.error(f"注入历史累计传感器失败: {e}")
            return {"success": True, "result": result}
        except Exception as e:
            _LOGGER.error(f"抓取历史记录失败: {e}")
            return {"success": False, "error": str(e)}
    
    hass.services.async_register(DOMAIN, "fetch_history", async_fetch_history_service)
    _LOGGER.info(f"已注册服务: {DOMAIN}.fetch_history")
