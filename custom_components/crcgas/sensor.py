"""华润燃气 传感器平台 - v1.2.7+

基于v1.2.7 | 新增: 三档用气量/气价, 上期读数/时间, 结算状态, 燃气表总读数(能源面板),
保持上次有效值, 历史数据注入(HA统计+SQLite), 燃气累计用量传感器
"""

import json
import logging
import sqlite3
import time as time_mod
from datetime import timedelta, datetime, timezone
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

try:
    from homeassistant.components.sensor import SensorEntity as BaseSensor
except ImportError:
    from homeassistant.helpers.entity import Entity as BaseSensor

from homeassistant.components.sensor.const import SensorStateClass as _SSC

from .api import HuarunGasApi, SessionTimeoutError
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


def _safe_float(value, default=0):
    """安全转换数字为float，去除千分位逗号"""
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return default


_STATE_CLASS_MAP = {
    "this_read": _SSC.TOTAL_INCREASING,
    "total_gas_consumption": _SSC.TOTAL_INCREASING,
    "total_gas_cost": _SSC.TOTAL_INCREASING,
    "monthly_gas_used": _SSC.TOTAL_INCREASING,
    "step1_gas_used": _SSC.TOTAL_INCREASING,
    "step2_gas_used": _SSC.TOTAL_INCREASING,
    "step3_gas_used": _SSC.TOTAL_INCREASING,
    "annual_pay_count": _SSC.TOTAL_INCREASING,
    "gas_energy_dashboard": _SSC.TOTAL_INCREASING,
}

_DEVICE_CLASS_MAP = {
    "this_read": "gas",
    "total_gas_consumption": "gas",
    "total_gas_cost": "monetary",
    "monthly_gas_used": "gas",
    "step1_gas_used": "gas",
    "step2_gas_used": "gas",
    "step3_gas_used": "gas",
    "gas_energy_dashboard": "gas",
}


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
        self._last_good_value = None

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
        if self.coordinator.data is not None:
            self.async_write_ha_state()

    @property
    def native_value(self):
        """获取传感器值"""
        data = self.coordinator.data
        if not data:
            if self.sensor_type in ("total_gas_consumption", "total_gas_cost"):
                return self._last_good_value
            return None

        if self.sensor_type == "arrears":
            v = data.get("arrears")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "account_balance":
            v = data.get("account_balance")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "last_pay_time":
            v = data.get("last_pay_time")
            return v if v and v != "未知" else "未知"

        elif self.sensor_type == "last_pay_amount":
            v = data.get("last_pay_amount")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "annual_pay_count":
            v = data.get("annual_pay_count")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "this_read":
            v = data.get("this_read")
            val = float(v) if v is not None else 0.0
            if val > 0:
                self._last_good_value = val
                return val
            return self._last_good_value if self._last_good_value is not None else 0.0

        elif self.sensor_type == "total_gas_consumption":
            v = data.get("this_read")
            val = float(v) if v is not None else 0.0
            if val > 0:
                self._last_good_value = val
                return val
            return self._last_good_value if self._last_good_value is not None else 0.0

        elif self.sensor_type == "total_gas_cost":
            v = data.get("total_gas_cost")
            val = float(v) if v is not None else 0.0
            if val > 0:
                self._last_good_value = val
                return val
            return self._last_good_value if self._last_good_value is not None else 0.0

        elif self.sensor_type == "this_read_time":
            v = data.get("this_read_time")
            return v if v and v != "未知" else "未知"

        elif self.sensor_type == "step1_gas_used":
            v = data.get("step1_gas_used")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "step2_gas_used":
            v = data.get("step2_gas_used")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "step3_gas_used":
            v = data.get("step3_gas_used")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "this_gas_used":
            v = data.get("this_gas_used")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "bill_amount":
            v = data.get("bill_amount")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "step1_remain":
            v = data.get("step1_remain")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "step2_remain":
            v = data.get("step2_remain")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "step3_remain":
            v = data.get("step3_remain")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "step1_gas_limit":
            v = data.get("step1_gas_limit")
            return float(v) if v is not None else 330.0

        elif self.sensor_type == "step1_gas_sum":
            v = data.get("step1_gas_sum")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "step2_gas_limit":
            v = data.get("step2_gas_limit")
            return float(v) if v is not None else 170.0

        elif self.sensor_type == "penalty_amount":
            v = data.get("penalty_amount")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "last_read":
            v = data.get("last_read")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "last_read_time":
            v = data.get("last_read_time")
            return v if v and v != "未知" else "未知"

        elif self.sensor_type == "settle_flag":
            v = data.get("settle_flag")
            return v if v and v != "未知" else "未知"

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
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "year_avg_gas":
            v = data.get("year_avg_gas")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "integration_status":
            v = data.get("integration_status")
            return INTEGRATION_STATUS.get(v, v) if v else "未知"

        elif self.sensor_type == "monthly_gas_used":
            v = data.get("monthly_gas_used")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "gas_energy_dashboard":
            v = data.get("this_read")
            val = float(v) if v is not None else 0.0
            if val > 0:
                self._last_good_value = val
                return val
            return self._last_good_value if self._last_good_value is not None else 0.0

        elif self.sensor_type == "gas_price_step1":
            v = data.get("gas_price_step1")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "gas_price_step2":
            v = data.get("gas_price_step2")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "gas_price_step3":
            v = data.get("gas_price_step3")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "step2_gas_sum":
            v = data.get("step2_gas_sum")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "step3_gas_sum":
            v = data.get("step3_gas_sum")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "step3_gas_limit":
            v = data.get("step3_gas_limit")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "estimated_gas_bill_amount":
            v = data.get("estimated_gas_bill_amount")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "cons_name":
            v = data.get("cons_name")
            return v if v and v != "未知" else "未知"

        elif self.sensor_type == "mobile":
            v = data.get("mobile")
            return v if v and v != "未知" else "未知"

        elif self.sensor_type == "meter_no":
            v = data.get("meter_no")
            return v if v and v != "未知" else "未知"

        elif self.sensor_type == "area_name":
            v = data.get("area_name")
            return v if v and v != "未知" else "未知"

        elif self.sensor_type == "account_status":
            v = data.get("account_status")
            return v if v and v != "未知" else "未知"

        elif self.sensor_type == "revbl_amount":
            v = data.get("revbl_amount")
            return float(v) if v is not None else 0.0

        elif self.sensor_type == "penalty_date":
            v = data.get("penalty_date")
            return v if v and v != "未知" else "未知"

        elif self.sensor_type == "last_fetch_time":
            v = data.get("last_fetch_time")
            return v if v and v != "未知" else "未知"

        elif self.sensor_type == "bill_month":
            v = data.get("bill_month")
            return v if v and v != "未知" else "未知"

        return None


    # === 补充传感器类型（数据从API现有字段提取） ===
    def _is_missing_sensor(self):
        return self.sensor_type in ("cons_name", "mobile", "meter_no", "area_name",
                                     "account_status", "revbl_amount", "penalty_date",
                                     "last_fetch_time", "bill_month")


class HuarunGasMeterHistorySensor(BaseSensor):
    """燃气累计用量传感器 — 用于能源面板显示完整历史数据"""

    def __init__(self, coordinator, entry_id):
        self._coordinator = coordinator
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_gas_meter_history"
        self._attr_name = "燃气累计用量"
        self._attr_icon = "mdi:counter"
        self._attr_native_unit_of_measurement = "m\u00b3"
        self._attr_state_class = _SSC.TOTAL_INCREASING
        self._attr_device_class = "gas"
        self._last_good_value = None

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
            val = float(v) if v is not None else None
            if val is not None and val > 0:
                self._last_good_value = val
                return val
        return self._last_good_value

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



def _import_history_statistics(hass, entry, bill_history, current_reading=None):
    """将历史账单数据导入 HA 统计系统，形成趋势图（增量：从DB已有累计值继续）"""
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

    from datetime import datetime, timezone
    import sqlite3, os

    db_path = os.path.join(hass.config.path(), "home-assistant_v2.db")
    last_gas_sum = 0.0
    last_bill_sum = 0.0
    existing_months = set()

    try:
        db_conn = sqlite3.connect(db_path)
        c = db_conn.cursor()

        # Read existing data
        meta_gas = c.execute("SELECT id FROM statistics_meta WHERE statistic_id='crcgas:monthly_gas_usage'").fetchone()
        if meta_gas:
            existing = c.execute("SELECT start_ts, sum FROM statistics WHERE metadata_id=?", (meta_gas[0],)).fetchall()
            for ts, s in existing:
                existing_months.add(datetime.fromtimestamp(ts).strftime("%Y-%m"))
                if ts > last_ts:
                    last_gas_sum = s

        meta_bill = c.execute("SELECT id FROM statistics_meta WHERE statistic_id='crcgas:monthly_bill_amount'").fetchone()
        if meta_bill:
            existing_bills = c.execute("SELECT start_ts, sum FROM statistics WHERE metadata_id=? ORDER BY start_ts DESC LIMIT 1", (meta_bill[0],)).fetchone()
            if existing_bills:
                last_bill_sum = existing_bills[1]

        db_conn.close()
    except Exception:
        pass

    # Find the last gas cumulative from the existing data
    if existing_months:
        # Use the existing last gas sum
        pass  # last_gas_sum already set above

    new_gas_stats = []
    new_bill_stats = []
    cumulative_gas = last_gas_sum
    cumulative_bill = last_bill_sum

    for bill in sorted_bills:
        ym = bill.get("billYm", "")
        if not ym or len(ym) < 7:
            continue
        if ym in existing_months:
            # Skip existing months but keep updating cumulative
            pass  # keep going
        year, month = int(ym[:4]), int(ym[5:7])
        gas_amt = float(bill.get("gasAmt", 0) or 0)
        bill_amt = float(bill.get("billAmt", 0) or 0)
        cumulative_gas += gas_amt
        cumulative_bill += bill_amt
        start = datetime(year, month, 1, tzinfo=timezone.utc)

        new_gas_stats.append({
            "start": start, "state": gas_amt, "sum": cumulative_gas,
            "min": gas_amt, "max": gas_amt, "mean": 0.0, "mean_weight": 0.0,
            "last_reset": start,
        })
        new_bill_stats.append({
            "start": start, "state": bill_amt, "sum": cumulative_bill,
            "min": bill_amt, "max": bill_amt, "mean": 0.0, "mean_weight": 0.0,
            "last_reset": start,
        })

    # Only inject if we have data
    if new_gas_stats:
        gas_metadata = StatisticMetaData(
            has_mean=False, has_sum=True,
            name="历史月度用气量", source=DOMAIN,
            statistic_id=f"{DOMAIN}:monthly_gas_usage",
            unit_of_measurement="m³",
            mean_type=StatisticMeanType.NONE,
        )
        async_add_external_statistics(hass, gas_metadata, new_gas_stats)
        _LOGGER.info("已导入 %d 条用气量统计（累计从 %.1f 开始）", len(new_gas_stats), last_gas_sum)

    if new_bill_stats:
        bill_metadata = StatisticMetaData(
            has_mean=False, has_sum=True,
            name="历史月度燃气费", source=DOMAIN,
            statistic_id=f"{DOMAIN}:monthly_bill_amount",
            unit_of_measurement="CNY",
            mean_type=StatisticMeanType.NONE,
        )
        async_add_external_statistics(hass, bill_metadata, new_bill_stats)
        _LOGGER.info("已导入 %d 条燃气费统计（累计从 %.1f 开始）", len(new_bill_stats), last_bill_sum)


async def _import_meter_history_to_entity(hass, entry, bill_history, only_missing=False):
    """通过 sqlite3 直接写入历史累计统计到 recorder 数据库
    only_missing=True: 只检查数据库中是否有记录，无记录时才注入（启动时用，不删除已有数据）
    only_missing=False: 先删后插（按钮触发时用）
    """
    import sqlite3
    from datetime import datetime, timezone
    import time as time_mod

    history_unique_id = f"{DOMAIN}_total_gas_consumption"
    entity_reg = er.async_get(hass)
    entity_id = entity_reg.async_get_entity_id("sensor", DOMAIN, history_unique_id)
    if not entity_id:
        entity_id = "sensor.hua_run_ran_qi_ran_qi_zong_xiao_hao_liang"
        _LOGGER.info("使用 fallback entity_id: %s", entity_id)

    # 同时获取累计燃气费用传感器的ID
    cost_history_unique_id = f"{DOMAIN}_total_gas_cost"
    cost_entity_id = entity_reg.async_get_entity_id("sensor", DOMAIN, cost_history_unique_id)
    # fallback: 如果 registry 还没注册，直接构造已知的 entity_id
    if not cost_entity_id:
        cost_entity_id = "sensor.hua_run_ran_qi_lei_ji_ran_qi_fei_yong"

    sorted_bills = sorted(bill_history, key=lambda b: b.get("billYm", ""))
    stats_data = []
    cost_stats_data = []
    cumulative = 0.0
    cumulative_cost = 0.0
    for bill in sorted_bills:
        ym = bill.get("billYm", "")
        if not ym or len(ym) < 7:
            continue
        year, month = int(ym[:4]), int(ym[5:7])
        gas_amt = float(bill.get("gasAmt", 0) or 0)
        cumulative += gas_amt
        start_ts = datetime(year, month, 1, tzinfo=timezone.utc).timestamp()
        stats_data.append((start_ts, cumulative))
        # 费用累计
        bill_amt = float(bill.get("billAmt", 0) or 0)
        cumulative_cost += bill_amt
        cost_stats_data.append((start_ts, cumulative_cost))

    if not stats_data:
        _LOGGER.warning("无账单数据，跳过历史累计注入")
        return

    db_path = hass.config.path("home-assistant_v2.db")
    now = time_mod.time()

    # 计算统一的 last_reset_ts：取最早的月份开始时间
    common_reset_ts = stats_data[0][0] if stats_data else now

    async def _inject_cost():
        if not cost_entity_id or not cost_stats_data:
            return

        def _do_cost_inject():
            conn2 = None
            try:
                conn2 = sqlite3.connect(db_path, timeout=10)
                conn2.execute("PRAGMA journal_mode=WAL")
                conn2.execute("BEGIN IMMEDIATE")

                # 清理旧的 source=crcgas 残留
                for old_id in [
                    r[0] for r in conn2.execute(
                        "SELECT id FROM statistics_meta WHERE statistic_id = ? AND source = ?",
                        (cost_entity_id, DOMAIN),
                    ).fetchall()
                ]:
                    conn2.execute("DELETE FROM statistics WHERE metadata_id = ?", (old_id,))
                    conn2.execute("DELETE FROM statistics_meta WHERE id = ?", (old_id,))

                conn2.execute(
                    "INSERT OR IGNORE INTO statistics_meta "
                    "(statistic_id, source, unit_of_measurement, has_mean, has_sum, name) "
                    "VALUES (?, 'recorder', ?, 0, 1, '累计燃气费用')",
                    (cost_entity_id, "¥"),
                )
                cost_row = conn2.execute(
                    "SELECT id FROM statistics_meta WHERE statistic_id = ? AND source = 'recorder'",
                    (cost_entity_id,),
                ).fetchone()
                if cost_row:
                    cost_mid = cost_row[0]
                    conn2.execute("DELETE FROM statistics WHERE metadata_id = ?", (cost_mid,))
                    conn2.execute("DELETE FROM statistics_short_term WHERE metadata_id = ?", (cost_mid,))
                    cost_rows = [(cost_mid, ts, val, val, val, val, 0.0, common_reset_ts, now) for ts, val in cost_stats_data]
                    conn2.executemany(
                        "INSERT INTO statistics "
                        "(metadata_id, start_ts, state, sum, min, max, mean, last_reset_ts, created_ts) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        cost_rows,
                    )
                    _LOGGER.info("已注入 %d 条历史费用到 %s", len(cost_stats_data), cost_entity_id)
                conn2.commit()
            except sqlite3.Error as e:
                _LOGGER.error("SQLite写入费用统计失败: %s", e)
            except Exception as e:
                _LOGGER.error("注入费用统计意外错误: %s", e)
            finally:
                if conn2:
                    conn2.close()

        await hass.async_add_executor_job(_do_cost_inject)

    def _do_inject():
        conn = None
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("BEGIN IMMEDIATE")

            # === 注入燃气累计用量（总读数）===
            if only_missing:
                row = conn.execute(
                    "SELECT id FROM statistics_meta WHERE statistic_id = ? AND source = 'recorder'",
                    (entity_id,),
                ).fetchone()
                if row:
                    existing = conn.execute(
                        "SELECT COUNT(*) FROM statistics WHERE metadata_id = ?",
                        (row[0],),
                    ).fetchone()
                    if existing and existing[0] >= 10:
                        _LOGGER.info("已有 %d 条历史累计记录(气量)，跳过", existing[0])
                        conn.rollback()
                        return
                _LOGGER.info("未发现历史累计记录，执行首次自动注入")

            # 清理旧的 source=crcgas 残留
            for old_id in [
                r[0] for r in conn.execute(
                    "SELECT id FROM statistics_meta WHERE statistic_id = ? AND source = ?",
                    (entity_id, DOMAIN),
                ).fetchall()
            ]:
                conn.execute("DELETE FROM statistics WHERE metadata_id = ?", (old_id,))
                conn.execute("DELETE FROM statistics_meta WHERE id = ?", (old_id,))

            conn.execute(
                "INSERT OR IGNORE INTO statistics_meta "
                "(statistic_id, source, unit_of_measurement, has_mean, has_sum, name) "
                "VALUES (?, 'recorder', ?, 0, 1, '燃气表总读数')",
                (entity_id, "m³"),
            )

            row = conn.execute(
                "SELECT id FROM statistics_meta WHERE statistic_id = ? AND source = 'recorder'",
                (entity_id,),
            ).fetchone()
            if row is None:
                _LOGGER.error("无法获取 statistics_meta id（statistic_id=%s）", entity_id)
                conn.rollback()
                return

            mid = row[0]
            conn.execute("DELETE FROM statistics WHERE metadata_id = ?", (mid,))
            conn.execute("DELETE FROM statistics_short_term WHERE metadata_id = ?", (mid,))

            rows = [(mid, ts, val, val, val, val, 0.0, common_reset_ts, now) for ts, val in stats_data]
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
    await _inject_cost()




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

    _LOGGER.info(f"数据刷新间隔: {scan_interval_val} {scan_interval_unit}（实际: {scan_interval}）")



    # ========== 2. 数据更新协调器 ==========

    async def async_update_data():

        """

        更新数据 - 各接口独立容错，任一失败不影响其他。

        """

        result = {

            "arrears": 0,

            "account_balance": 0,

            "last_pay_time": "未知",

            "last_pay_amount": 0,

            "annual_pay_count": 0,

            "this_read": 0,

            "this_read_time": "未知",

            "step1_gas_used": 0,

            "step2_gas_used": 0,

            "this_gas_used": 0,

            "bill_amount": 0,

            "step1_remain": 0,

            "step2_remain": 0,
            "step3_remain": 0,

            "penalty_amount": 0,
            "last_read": 0,
            "last_read_time": "未知",
            "settle_flag": "未知",

            "cons_addr": "未知",

            "org_name": "未知",

            "gas_nature": "未知",

            "purchase_style": "未知",

            "last_month_gas": 0,

            "year_avg_gas": 0,

            "integration_status": "unknown",

            "monthly_gas_used": 0,

            "cons_name": "未知",
            "mobile": "未知",
            "meter_no": "未知",
            "area_name": "未知",
            "account_status": "未知",
            "revbl_amount": 0.0,
            "penalty_date": "未知",
            "last_fetch_time": "未知",
            "bill_month": "未知",

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



        # 1. 获取欠费信息

        try:

            arrears_data = await api.async_query_arrears(cons_no)

            if arrears_data:

                data = arrears_data.get("dataResult", {})

                if isinstance(data, dict):

                    result["arrears"] = float(data.get("totalAmt", 0) or 0)

                    result["account_balance"] = float(data.get("totalBal", 0) or 0)

        except Exception as e:

            _LOGGER.error(f"获取欠费信息失败: {e}")

            if "SESSION_TIMEOUT" in str(e) or "会话超时" in str(e):

                session_timeout_count += 1



        # 2. 获取缴费历史

        try:

            pay_data = await api.async_query_pay_history(cons_no)

            if pay_data and pay_data.get("success"):

                pay_result = pay_data.get("dataResult", [])

                if isinstance(pay_result, list) and pay_result:

                    last_pay = pay_result[0]

                    result["last_pay_time"] = last_pay.get("payTime", "未知")

                    result["last_pay_amount"] = float(last_pay.get("payAmount", 0) or 0)

                    current_year = str(datetime.now().year)

                    result["annual_pay_count"] = sum(1 for p in pay_result if current_year in str(p.get("payTime", "")))

        except Exception as e:

            _LOGGER.error(f"获取缴费历史失败: {e}")

            if "SESSION_TIMEOUT" in str(e) or "会话超时" in str(e):

                session_timeout_count += 1



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
                    lev_gq_sum = prc_detail.get("levGqSum", "0")

                    if isinstance(lev_gq_remain, str):
                        lev_gq_remain = lev_gq_remain.replace(",", "")

                    if rule_code == "0201":

                        result["step1_remain"] = _safe_float(lev_gq_remain) if lev_gq_remain else 0

                        result["step1_gas_limit"] = _safe_float(prc_detail.get("levGq", 0))

                        result["step1_price"] = _safe_float(prc_detail.get("catPrc", 0))

                        result["gas_price_step1"] = _safe_float(prc_detail.get("catPrc", 0))

                    elif rule_code == "0202":

                        result["step2_remain"] = _safe_float(lev_gq_remain) if lev_gq_remain else 0

                        result["step2_gas_limit"] = _safe_float(prc_detail.get("levGq", 0))

                        result["step2_price"] = _safe_float(prc_detail.get("catPrc", 0))

                        result["gas_price_step2"] = _safe_float(prc_detail.get("catPrc", 0))
                        result["step2_gas_sum"] = _safe_float(lev_gq_sum) if lev_gq_sum else 0

                    elif rule_code == "0203":

                        result["gas_price_step3"] = _safe_float(prc_detail.get("catPrc", 0))
                        result["step3_remain"] = _safe_float(lev_gq_remain) if lev_gq_remain else 0
                        result["step3_gas_limit"] = _safe_float(prc_detail.get("levGq", 0))
                        result["step3_gas_sum"] = _safe_float(lev_gq_sum) if lev_gq_sum else 0

                if bills:

                    last_bill = bills[0]

                    result["_last_bill_ym"] = last_bill.get("billYm", "")

                    result["_last_app_no"] = last_bill.get("applicationNo", "")

                    result["last_bill_gas_amt"] = float(last_bill.get("gasAmt", 0) or 0)

                    result["last_bill_penalty"] = float(last_bill.get("penaltyAmt", 0) or 0)

                    result["settle_flag"] = last_bill.get("settleFlag", "未知")
                    result["revbl_amount"] = float(last_bill.get("revblAmt", 0) or 0)
                    result["penalty_date"] = last_bill.get("penaltyDate", "未知")
                    result["bill_month"] = last_bill.get("billYm", "未知")

                    # 保存新账单到历史存储（自动更新统计）
                    try:
                        from .history_storage import CRCGasHistoryStorage
                        hs = CRCGasHistoryStorage(hass, config_entry.entry_id)
                        await hs.async_load()
                        existing_app_nos = {b["applicationNo"] for b in hs.get_bill_history(limit=999) if b.get("applicationNo")}
                        new_bills = [b for b in bills if b.get("applicationNo") not in existing_app_nos]
                        if new_bills:
                            for nb in new_bills:
                                await hs.async_add_bill_record(nb)
                            _LOGGER.info(f"账单历史更新: 新增{len(new_bills)}条新账单")
                            # 增量注入：只追加新月份
                            try:
                                from homeassistant.components.recorder.statistics import (
                                    async_add_external_statistics, StatisticMetaData, StatisticMeanType)
                                import sqlite3, os
                                db_path = os.path.join(hass.config.path(), "home-assistant_v2.db")
                                db_conn = sqlite3.connect(db_path)
                                c = db_conn.cursor()
                                
                                # 获取最新累计值
                                meta_gas = c.execute("SELECT id FROM statistics_meta WHERE statistic_id='crcgas:monthly_gas_usage'").fetchone()
                                meta_bill = c.execute("SELECT id FROM statistics_meta WHERE statistic_id='crcgas:monthly_bill_amount'").fetchone()
                                last_gas_sum = float(c.execute("SELECT sum FROM statistics WHERE metadata_id=? ORDER BY start_ts DESC LIMIT 1", (meta_gas[0],)).fetchone()[0]) if meta_gas else 0
                                last_bill_sum = float(c.execute("SELECT sum FROM statistics WHERE metadata_id=? ORDER BY start_ts DESC LIMIT 1", (meta_bill[0],)).fetchone()[0]) if meta_bill else 0
                                db_conn.close()
                                
                                for nb in new_bills:
                                    ym = nb.get("billYm", "")
                                    if len(ym) < 7: continue
                                    year, month = int(ym[:4]), int(ym[5:7])
                                    gas_amt = float(nb.get("gasAmt", 0) or 0)
                                    bill_amt = float(nb.get("billAmt", 0) or 0)
                                    start = datetime(year, month, 1, tzinfo=timezone.utc)
                                    
                                    last_gas_sum += gas_amt
                                    last_bill_sum += bill_amt
                                    
                                    # 用气量
                                    async_add_external_statistics(hass, StatisticMetaData(
                                        has_mean=False, has_sum=True,
                                        name="历史月度用气量", source="crcgas",
                                        statistic_id="crcgas:monthly_gas_usage",
                                        unit_of_measurement="m\u00b3",
                                        mean_type=StatisticMeanType.NONE,
                                    ), [{
                                        "start": start, "state": gas_amt, "sum": last_gas_sum,
                                        "min": gas_amt, "max": gas_amt, "mean": 0.0, "mean_weight": 0.0,
                                        "last_reset": start,
                                    }])
                                    
                                    # 费用
                                    async_add_external_statistics(hass, StatisticMetaData(
                                        has_mean=False, has_sum=True,
                                        name="历史月度燃气费", source="crcgas",
                                        statistic_id="crcgas:monthly_bill_amount",
                                        unit_of_measurement="CNY",
                                        mean_type=StatisticMeanType.NONE,
                                    ), [{
                                        "start": start, "state": bill_amt, "sum": last_bill_sum,
                                        "min": bill_amt, "max": bill_amt, "mean": 0.0, "mean_weight": 0.0,
                                        "last_reset": start,
                                    }])
                                    _LOGGER.info(f"增量注入: {ym} 用气={gas_amt}m\u00b3 累计={last_gas_sum}m\u00b3")
                            except Exception as e_inc:
                                _LOGGER.warning(f"增量注入失败: {e_inc}")
                    except Exception as e_h:
                        _LOGGER.debug(f"账单历史更新跳过: {e_h}")

        except Exception as e:

            _LOGGER.error(f"获取账单列表失败: {e}")

            if "SESSION_TIMEOUT" in str(e) or "会话超时" in str(e):

                session_timeout_count += 1



        # 4. 获取月度用气图表

        try:

            chart_data = await api.async_get_gas_bill_list4chart(cons_no)

            if chart_data and chart_data.get("success"):

                dr = chart_data.get("dataResult", {})

                if isinstance(dr, dict):

                    last_gas = dr.get("lastGas", [])

                    if len(last_gas) > 1:

                        result["last_month_gas"] = last_gas[1]

                    all_gas = [g for g in last_gas if g is not None]

                    if all_gas:

                        result["year_avg_gas"] = round(sum(all_gas) / len(all_gas), 1)

                    # 统计本年累计用气（thisGas 前几个非空值之和）
                    this_gas = dr.get("thisGas", [])
                    valid_this = [g for g in this_gas if g is not None and g > 0]
                    if valid_this:
                        result["step1_gas_sum"] = sum(valid_this)
                    else:
                        result["step1_gas_sum"] = 0

        except Exception as e:

            _LOGGER.error(f"获取月度用气图表失败: {e}")

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

                        result["last_read"] = detail.get("lastRead", 0)

                        result["last_read_time"] = detail.get("lastReadTime", "未知")

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

                                elif "三阶" in step_type:

                                    result["step3_gas_used"] = gas_used

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



        # 6. 获取绑定信息

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
                    result["cons_name"] = cons_info.get("consName", "未知")
                    result["mobile"] = cons_info.get("mobile", "未知")

        except Exception as e:

            _LOGGER.error(f"获取绑定信息失败: {e}")

            if "SESSION_TIMEOUT" in str(e) or "会话超时" in str(e):

                session_timeout_count += 1



        if session_timeout_count >= total_api_calls:

            _LOGGER.critical(f"全部{total_api_calls}个API返回会话超时！Token已完全失效。")

            result["integration_status"] = "token_expired"

        else:

            # 简单状态判断

            if session_timeout_count > 0:

                result["integration_status"] = "token_expired"

            else:

                result["integration_status"] = "normal"



        # 设置月度累计用气量（暂时用本期用气量代替）

        result["monthly_gas_used"] = result.get("this_gas_used", 0)



        # 修复阶梯用气量逻辑：如果一档剩余量>0，二档用气量必须为0

        step1_remain = result.get("step1_remain", 0)

        step2_remain = result.get("step2_remain", 0)

        this_gas_used = result.get("this_gas_used", 0)

        step1_gas_limit = result.get("step1_gas_limit", 330)  # 默认值

        step2_gas_limit = result.get("step2_gas_limit", 170)  # 默认值



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

        # 累计燃气费用 = 历史账单总和
        try:
            from .history_storage import CRCGasHistoryStorage
            cost_store = CRCGasHistoryStorage(hass, config_entry.entry_id)
            await cost_store.async_load()
            cost_history = cost_store.get_bill_history(limit=999)
            historical_cost = sum(float(b.get("billAmt", 0) or 0) for b in cost_history)
            current_cost = float(result.get("estimated_gas_bill_amount", 0) or 0)
            result["total_gas_cost"] = round(historical_cost + current_cost, 2)
        except Exception:
            result["total_gas_cost"] = result.get("total_gas_cost", 0.0)

        _LOGGER.info(f"数据更新完成: 欠费¥{result['arrears']}, 读数{result['this_read']}, 状态={result['integration_status']}")

        result["last_fetch_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

    async_add_entities(entities)



    # 异步执行首次刷新 + 自动抓取历史记录

    def _fix_statis_sum():
        """修正短期统计冷启动 sum=0 问题"""
        sensor_ids = [
            "sensor.hua_run_ran_qi_ran_qi_zong_xiao_hao_liang",
            "sensor.hua_run_ran_qi_lei_ji_ran_qi_fei_yong",
        ]
        db_path = hass.config.path("home-assistant_v2.db")
        try:
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                updated = 0
                for sid in sensor_ids:
                    meta = c.execute(
                        "SELECT id FROM statistics_meta WHERE statistic_id = ?", (sid,)
                    ).fetchone()
                    if not meta:
                        continue
                    latest = c.execute(
                        "SELECT sum, state FROM statistics_short_term "
                        "WHERE metadata_id = ? ORDER BY start_ts DESC LIMIT 1",
                        (meta[0],),
                    ).fetchone()
                    if not latest:
                        continue
                    short_sum, state_val = float(latest[0]), float(latest[1])
                    if state_val > 0 and abs(short_sum - state_val) > 0.01:
                        c.execute(
                            "UPDATE statistics_short_term SET sum = state WHERE metadata_id = ?",
                            (meta[0],),
                        )
                        rows = c.rowcount
                        updated += rows
                        _LOGGER.info(
                            "修正短期统计 sum: %s %.1f→%.1f (%d条)",
                            sid, short_sum, state_val, rows,
                        )
                if updated:
                    conn.commit()
                    _LOGGER.info("短期统计 sum 修正完成: 共 %d 条", updated)
        except Exception as e:
            _LOGGER.warning("短期统计 sum 修正失败: %s", e)

    async def async_initial_setup():

        """首次初始化：先刷新传感器数据，再自动抓取历史记录"""

        try:

            await coordinator.async_config_entry_first_refresh()

            _LOGGER.info("首次传感器数据刷新完成")

        except Exception as e:

            _LOGGER.error(f"首次传感器数据刷新失败: {e}")

            return

        # 修正短期统计 sum 冷启动问题
        try:
            await hass.async_add_executor_job(_fix_statis_sum)
        except Exception as e:
            _LOGGER.warning("短期统计 sum 修正异常: %s", e)



        # 导入历史数据到能源面板
        try:
            from .history_storage import CRCGasHistoryStorage
            store = CRCGasHistoryStorage(hass, config_entry.entry_id)
            await store.async_load()
            bill_history = store.get_bill_history(limit=999)
            if bill_history:
                _LOGGER.info(f"历史数据注入: {len(bill_history)} 条账单")
                await _import_meter_history_to_entity(hass, config_entry, bill_history, only_missing=True)
                _LOGGER.info("历史数据注入完成")
        except Exception as e:
            _LOGGER.warning(f"历史数据注入失败（按钮可补救）: {e}")

        # 自动抓取历史记录（仅限首次安装/无历史数据时）

        try:

            from .history_storage import async_setup_history_storage

            storage = await async_setup_history_storage(hass, config_entry.entry_id)



            # 检查是否已有历史数据

            bill_history = storage.get_bill_history()

            if bill_history:

                _LOGGER.debug(f"已有 {len(bill_history)} 条历史账单，跳过自动抓取")

                return



            _LOGGER.info("首次启动，自动抓取历史记录...")

            result = await storage.async_fetch_all_bills(api, cons_no)

            _LOGGER.info(

                f"首次自动抓取完成: "

                f"新增{result['new_bills']}条, "

                f"更新{result['updated_bills']}条, "

                f"总计{result['total_stored']}条"

            )
            # 抓取完成后立即注入统计（无需重启）
            if result.get("total_stored", 0) > 0:
                bill_history = storage.get_bill_history(limit=999)
                if bill_history:
                    try:
                        await _import_meter_history_to_entity(hass, config_entry, bill_history, only_missing=True)
                        _import_history_statistics(hass, config_entry, bill_history)
                        _LOGGER.info(f"首次统计注入完成: {len(bill_history)}条账单")
                    except Exception as e_inj:
                        _LOGGER.warning(f"首次统计注入失败: {e_inj}")

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

            return {"success": True, "result": result}

        except Exception as e:

            _LOGGER.error(f"抓取历史记录失败: {e}")

            return {"success": False, "error": str(e)}

    

    hass.services.async_register(DOMAIN, "fetch_history", async_fetch_history_service)

    _LOGGER.info(f"已注册服务: {DOMAIN}.fetch_history")


