"""华润燃气 传感器平台 - 修复版 (v1.0.9)

修复: Entity -> SensorEntity, 字段名, 缩进
"""

import json
import logging
from datetime import timedelta, datetime
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

try:
    from homeassistant.components.sensor import SensorEntity as BaseSensor
except ImportError:
    from homeassistant.helpers.entity import Entity as BaseSensor

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
            v = data.get("arrears")
            return v if v is not None else 0
        elif self.sensor_type == "account_balance":
            v = data.get("account_balance")
            return v if v is not None else 0
        elif self.sensor_type == "last_pay_time":
            v = data.get("last_pay_time")
            return v if v and v != "未知" else "未知"
        elif self.sensor_type == "last_pay_amount":
            v = data.get("last_pay_amount")
            return v if v is not None else 0
        elif self.sensor_type == "annual_pay_count":
            v = data.get("annual_pay_count")
            return v if v is not None else 0
        elif self.sensor_type == "this_read":
            v = data.get("this_read")
            return int(v) if v is not None else 0
        elif self.sensor_type == "this_read_time":
            v = data.get("this_read_time")
            return v if v and v != "未知" else "未知"
        elif self.sensor_type == "step1_gas_used":
            v = data.get("step1_gas_used")
            return v if v is not None else 0
        elif self.sensor_type == "step2_gas_used":
            v = data.get("step2_gas_used")
            return v if v is not None else 0
        elif self.sensor_type == "this_gas_used":
            v = data.get("this_gas_used")
            return float(v) if v is not None else 0
        elif self.sensor_type == "bill_amount":
            v = data.get("bill_amount")
            return float(v) if v is not None else 0
        elif self.sensor_type == "step1_remain":
            v = data.get("step1_remain")
            return float(v) if v is not None else 0
        elif self.sensor_type == "step2_remain":
            v = data.get("step2_remain")
            return float(v) if v is not None else 0
        elif self.sensor_type == "penalty_amount":
            v = data.get("penalty_amount")
            return float(v) if v is not None else 0
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
            return float(v) if v is not None else 0
        elif self.sensor_type == "year_avg_gas":
            v = data.get("year_avg_gas")
            return float(v) if v is not None else 0
        elif self.sensor_type == "integration_status":
            v = data.get("integration_status")
            return v if v else "unknown"
        elif self.sensor_type == "monthly_gas_used":
            v = data.get("monthly_gas_used")
            return float(v) if v is not None else 0
        return None




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

    session = async_get_clientsession(hass)
    api = HuarunGasApi(refresh_token, bo_token, wx_code, on_token_refresh, session=session)

    # 获取配置的扫描间隔，默认1小时
    scan_interval_val = config_entry.data.get(CONF_SCAN_INTERVAL, 1)
    scan_interval_unit = config_entry.data.get(CONF_SCAN_INTERVAL_UNIT, "hour")

    # 计算实际刷新间隔（hour=小时数，day=固定1小时仅支持定时，week=固定1小时，month=固定1小时）
    # day/week/month 模式下实际刷新由 coordinator 内部逻辑决定，这里统一设为1小时兜底
    if scan_interval_unit == "hour":
        scan_interval = timedelta(hours=scan_interval_val)
    else:
        # 非小时模式：设为最小1小时，day/week/month 定时逻辑在刷新回调中处理
        scan_interval = timedelta(hours=1)
    _LOGGER.info(f"数据刷新间隔: {scan_interval_val} {scan_interval_unit}（实际: {scan_interval}）")

    # ========== 1. 初始Token验证 ==========
    try:
        _LOGGER.info("初始化Token验证...")
        result = await api.async_refresh_token()
        if result:
            _LOGGER.info("Token验证成功")
        else:
            _LOGGER.warning("Token验证返回空，可能已过期")
    except Exception as e:
        _LOGGER.error(f"Token初始化失败: {e}")

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
            "penalty_amount": 0,
            "cons_addr": "未知",
            "org_name": "未知",
            "gas_nature": "未知",
            "purchase_style": "未知",
            "last_month_gas": 0,
            "year_avg_gas": 0,
            "integration_status": "unknown",
            "monthly_gas_used": 0,
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
        
        _LOGGER.info(f"数据更新完成: 欠费¥{result['arrears']}, 读数{result['this_read']}, 状态={result['integration_status']}, 一档用气量={result['step1_gas_used']}, 二档用气量={result['step2_gas_used']}")
        return result

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    # 存储 coordinator 和 api 到 hass.data（供 button.py 使用）
    # 使用独立 key，避免 mappingproxy 只读问题（async_forward_entry_setups 是同步调用，
    # __init__.py 的 hass.data[DOMAIN][entry.entry_id] = dict(entry.data) 还未执行）
    hass.data[DOMAIN][f"{config_entry.entry_id}_coordinator"] = coordinator
    hass.data[DOMAIN][f"{config_entry.entry_id}_api"] = api
    hass.data[DOMAIN][f"{config_entry.entry_id}_cons_no"] = cons_no

    # 创建传感器
    entities = [
        HuarunGasSensor(coordinator, sensor_type)
        for sensor_type in SENSOR_TYPES
    ]
    async_add_entities(entities)
    
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
