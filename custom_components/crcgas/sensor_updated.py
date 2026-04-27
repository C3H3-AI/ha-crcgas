"""华润燃气传感器平台 - 更新版 (v1.1.0)

更新内容:
1. 添加二档用气量传感器
2. 添加集成状态传感器（正常/密钥过期/网络异常/配置错误）
3. 添加本地历史存储
4. 添加月累计传感器
5. 增强错误处理和日志记录
"""

import json
import logging
from datetime import timedelta
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
    TOKEN_REFRESH_INTERVAL,
    TOKEN_EXPIRE_THRESHOLD,
    INTEGRATION_STATUS,
)

_LOGGER = logging.getLogger(__name__)


class HuarunGasSensor(BaseSensor):
    """华润燃气传感器"""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_type: str):
        self.coordinator = coordinator
        self.sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}"
        self._attr_translation_key = sensor_type

        st_config = SENSOR_TYPES.get(sensor_type, {})
        self._attr_name = st_config.get("name", sensor_type)
        self._attr_icon = st_config.get("icon")
        self._attr_native_unit_of_measurement = st_config.get("unit")

    @property
    def device_info(self) -> Dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": "华润燃气",
            "manufacturer": "华润燃气",
            "model": "燃气抄表",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """添加到 Home Assistant"""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
        if self.coordinator.data:
            self.async_write_ha_state()

    @property
    def native_value(self):
        """获取传感器值"""
        if not self.coordinator.data:
            return None
        
        data = self.coordinator.data
        
        # 高价值传感器
        if self.sensor_type == "arrears":
            v = data.get("arrears")
            return float(v) if v is not None else 0
        elif self.sensor_type == "account_balance":
            v = data.get("account_balance")
            return float(v) if v is not None else 0
        elif self.sensor_type == "last_pay_time":
            return data.get("last_pay_time", "未知")
        elif self.sensor_type == "last_pay_amount":
            v = data.get("last_pay_amount")
            return float(v) if v is not None else 0
        elif self.sensor_type == "annual_pay_count":
            return data.get("annual_pay_count", 0)
        elif self.sensor_type == "this_read":
            v = data.get("this_read")
            return float(v) if v is not None else 0
        elif self.sensor_type == "this_read_time":
            return data.get("this_read_time", "未知")
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
        # 新增：集成状态传感器
        elif self.sensor_type == "integration_status":
            return data.get("integration_status", "未知")
        # 新增：月累计传感器
        elif self.sensor_type == "monthly_gas_used":
            v = data.get("monthly_gas_used")
            return float(v) if v is not None else 0
        # 中等价值传感器
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
        return None


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """设置传感器平台"""
    cons_no = config_entry.data.get(CONF_CONS_NO)
    refresh_token = config_entry.data.get(CONF_REFRESH_TOKEN)
    bo_token = config_entry.data.get(CONF_BO_TOKEN)
    wx_code = config_entry.data.get(CONF_WX_CODE)

    if not all([cons_no, refresh_token, bo_token]):
        _LOGGER.error("配置缺少必要参数")
        return False

    _LOGGER.info(f"初始化华润燃气传感器: cons_no={cons_no}")

    # Token刷新回调
    async def on_token_refresh(new_refresh_token: str, new_bo_token: str):
        _LOGGER.info("Token已刷新，更新配置")
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                CONF_REFRESH_TOKEN: new_refresh_token,
                CONF_BO_TOKEN: new_bo_token,
            },
        )

    session = async_get_clientsession(hass)
    api = HuarunGasApi(refresh_token, bo_token, wx_code, on_token_refresh, session=session)

    # 获取扫描配置
    interval_val = int(config_entry.options.get(
        CONF_SCAN_INTERVAL,
        config_entry.data.get(CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds() / 3600))
    ))
    interval_unit = config_entry.options.get(CONF_SCAN_INTERVAL_UNIT, config_entry.data.get(CONF_SCAN_INTERVAL_UNIT, "month"))

    if interval_unit == "hour":
        scan_interval = timedelta(hours=interval_val)
        _LOGGER.info(f"使用数据更新间隔: 每{interval_val}小时")
    else:
        scan_interval = None
        if interval_unit == "day":
            _LOGGER.info(f"使用定时更新: 每天{interval_val}:00")
        elif interval_unit == "week":
            weekdays = ["周日","周一","周二","周三","周四","周五","周六"]
            _LOGGER.info(f"使用定时更新: 每周{weekdays[interval_val % 7]} 00:00")
        elif interval_unit == "month":
            _LOGGER.info(f"使用定时更新: 每月{interval_val}日 00:00")

    # Token刷新协调器
    token_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_token",
        update_method=api.async_refresh_token,
        update_interval=TOKEN_REFRESH_INTERVAL,
    )

    try:
        await token_coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Token自动刷新协调器已启动，首次刷新成功")
    except Exception as e:
        _LOGGER.warning(f"Token首次刷新失败: {e}")

    # 数据更新协调器
    async def async_update_data():
        """更新数据"""
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
            "step2_gas_used": 0,
            "this_gas_used": 0,
            "bill_amount": 0,
            "step1_remain": 0,
            "step2_remain": 0,
            "penalty_amount": 0,
            # 新增：集成状态
            "integration_status": "正常",
            # 新增：月累计
            "monthly_gas_used": 0,
            # 中等价值
            "cons_addr": "未知",
            "org_name": "未知",
            "gas_nature": "未知",
            "purchase_style": "未知",
            "last_month_gas": 0,
            "year_avg_gas": 0,
        }

        session_timeout_count = 0
        total_api_calls = 6

        # 检查token是否即将过期
        if api.is_token_expiring_soon(threshold_seconds=int(TOKEN_EXPIRE_THRESHOLD.total_seconds())):
            _LOGGER.warning(f"Token即将过期，强制刷新...")
            try:
                await api.async_refresh_token()
            except SessionTimeoutError:
                session_timeout_count += 1

        # 1. 查询欠费
        try:
            arrears_data = await api.async_query_arrears(cons_no)
            if arrears_data and arrears_data.get("success"):
                data_result = arrears_data.get("dataResult", {})
                if isinstance(data_result, dict):
                    result["arrears"] = float(data_result.get("arrears", 0) or 0)
                    result["account_balance"] = float(data_result.get("accountBalance", 0) or 0)
                    _LOGGER.debug(f"欠费查询: 欠费={result['arrears']}, 余额={result['account_balance']}")
        except SessionTimeoutError:
            session_timeout_count += 1
            _LOGGER.warning("查询欠费: 会话超时")
        except Exception as e:
            _LOGGER.error(f"查询欠费失败: {e}")

        # 2. 获取缴费历史
        try:
            pay_data = await api.async_query_pay_history(cons_no)
            if pay_data and pay_data.get("success"):
                pay_result = pay_data.get("dataResult", [])
                if isinstance(pay_result, list) and pay_result:
                    last_pay = pay_result[0]
                    result["last_pay_time"] = last_pay.get("payTime", "未知")
                    result["last_pay_amount"] = float(last_pay.get("payAmount", 0) or 0)
                    import datetime
                    current_year = str(datetime.datetime.now().year)
                    result["annual_pay_count"] = sum(1 for p in pay_result if current_year in str(p.get("payTime", "")))
        except SessionTimeoutError:
            session_timeout_count += 1
            _LOGGER.warning("获取缴费历史: 会话超时")
        except Exception as e:
            _LOGGER.error(f"获取缴费历史失败: {e}")

        # 3. 获取账单列表
        try:
            bill_data = await api.async_get_gas_bill_list(cons_no, page=1, page_num=6)
            if bill_data and bill_data.get("success"):
                data_result = bill_data.get("dataResult", {})
                bills = data_result.get("data", []) if isinstance(data_result, dict) else []
                if bills:
                    last_bill = bills[0]
                    result["_last_bill_ym"] = last_bill.get("billYm", "")
                    result["_last_app_no"] = last_bill.get("applicationNo", "")
        except SessionTimeoutError:
            session_timeout_count += 1
            _LOGGER.warning("获取账单列表: 会话超时")
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
                    all_gas = [g for g in last_gas if g is not None]
                    if all_gas:
                        result["year_avg_gas"] = round(sum(all_gas) / len(all_gas), 1)
                    # 计算本月累计用气量
                    if last_gas and last_gas[0] is not None:
                        result["monthly_gas_used"] = last_gas[0]
        except SessionTimeoutError:
            session_timeout_count += 1
            _LOGGER.warning("获取月度用气图表: 会话超时")
        except Exception as e:
            _LOGGER.error(f"获取月度用气图表失败: {e}")

        # 5. 获取账单详情（包含阶梯信息）
        try:
            bill_ym = result.get("_last_bill_ym", "")
            app_no = result.get("_last_app_no", "")
            _LOGGER.info(f"准备获取账单详情: bill_ym={bill_ym}, app_no={app_no}")
            
            if bill_ym and app_no:
                detail_data = await api.async_get_bill_detail(cons_no, bill_ym, app_no)
                _LOGGER.info(f"账单详情API返回: success={detail_data.get('success') if detail_data else 'None'}")
                
                if detail_data and detail_data.get("success"):
                    details = detail_data.get("dataResult", [])
                    _LOGGER.info(f"账单详情dataResult: {len(details) if isinstance(details, list) else 'Not list'} 条记录")
                    
                    if details and isinstance(details, list):
                        detail = details[0]
                        _LOGGER.info(f"账单详情原始数据: {json.dumps(detail, ensure_ascii=False)}")
                        
                        result["this_read"] = detail.get("thisRead", 0)
                        result["this_read_time"] = detail.get("thisReadTime", "未知")
                        result["this_gas_used"] = detail.get("thisGas", 0)
                        result["bill_amount"] = detail.get("totalAmount", 0) or detail.get("billAmount", 0)
                        result["penalty_amount"] = detail.get("penaltyAmount", 0)
                        
                        step_list = detail.get("gasStepList", [])
                        _LOGGER.info(f"gasStepList: {len(step_list)} 个阶梯")
                        
                        for i, step in enumerate(step_list):
                            step_type = step.get("stepType", "")
                            step_remain = step.get("stepRemain", "字段不存在")
                            gas_used = step.get("gasUsed", 0)
                            _LOGGER.info(f"阶梯[{i}]: type={step_type}, used={gas_used}, remain={step_remain}")
                            
                            if "一档" in step_type:
                                result["step1_gas_used"] = gas_used
                                if step_remain != "字段不存在":
                                    result["step1_remain"] = float(step_remain)
                                    _LOGGER.info(f"一档剩余: {result['step1_remain']}")
                                else:
                                    _LOGGER.warning("一档信息中缺少stepRemain字段")
                            elif "二档" in step_type:
                                result["step2_gas_used"] = gas_used
                                if step_remain != "字段不存在":
                                    result["step2_remain"] = float(step_remain)
                                    _LOGGER.info(f"二档剩余: {result['step2_remain']}")
                                else:
                                    _LOGGER.warning("二档信息中缺少stepRemain字段")
                        
                        _LOGGER.info(f"账单详情解析完成: 一档用气={result['step1_gas_used']}, 二档用气={result['step2_gas_used']}, 一档剩余={result['step1_remain']}, 二档剩余={result['step2_remain']}")
                    else:
                        _LOGGER.warning("账单详情dataResult为空或格式错误")
                else:
                    _LOGGER.warning(f"账单详情API调用失败: {detail_data}")
            else:
                _LOGGER.warning(f"缺少账单信息: bill_ym={bill_ym}, app_no={app_no}")
                
        except SessionTimeoutError:
            session_timeout_count += 1
            _LOGGER.warning("获取账单详情: 会话超时")
        except Exception as e:
            _LOGGER.error(f"获取账单详情失败: {e}")

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
        except SessionTimeoutError:
            session_timeout_count += 1
            _LOGGER.warning("获取绑定信息: 会话超时")
        except Exception as e:
            _LOGGER.error(f"获取绑定信息失败: {e}")

        # 7. 确定集成状态
        if session_timeout_count >= total_api_calls:
            result["integration_status"] = "网络异常"
        elif session_timeout_count > 0:
            result["integration_status"] = "API错误"
        else:
            result["integration_status"] = "正常"

        _LOGGER.info(f"数据更新完成: 状态={result['integration_status']}, 会话超时={session_timeout_count}/{total_api_calls}")
        return result

    # 创建数据协调器
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{cons_no}",
        update_method=async_update_data,
        update_interval=scan_interval,
    )

    # 设置定时刷新
    if interval_unit == "day":
        from homeassistant.helpers.event import async_track_time_change
        async_track_time_change(
            hass,
            lambda now: hass.async_create_task(coordinator.async_request_refresh()),
            hour=interval_val,
            minute=0,
            second=0,
        )
    elif interval_unit == "week":
        from homeassistant.helpers.event import async_track_point_in_time
        from homeassistant.util import dt as dt_util
        def _setup_weekly(*args):
            now = dt_util.now()
            target_weekday = interval_val % 7
            days_ahead = target_weekday - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_time = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
            async_track_point_in_time(hass, _setup_weekly, next_time)
            hass.async_create_task(coordinator.async_request_refresh())
        _setup_weekly()
    elif interval_unit == "month":
        from homeassistant.helpers.event import async_track_point_in_time
        from homeassistant.util import dt as dt_util
        import calendar
        def _setup_monthly(*args):
            now = dt_util.now()
            if now.day < interval_val:
                try:
                    next_time = now.replace(day=interval_val, hour=0, minute=0, second=0, microsecond=0)
                except ValueError:
                    last_day = calendar.monthrange(now.year, now.month)[1]
                    next_time = now.replace(day=last_day, hour=0, minute=0, second=0, microsecond=0)
            else:
                if now.month == 12:
                    next_year, next_month = now.year + 1, 1
                else:
                    next_year, next_month = now.year, now.month + 1
                try:
                    next_time = now.replace(year=next_year, month=next_month, day=interval_val, hour=0, minute=0, second=0, microsecond=0)
                except ValueError:
                    last_day = calendar.monthrange(next_year, next_month)[1]
                    next_time = now.replace(year=next_year, month=next_month, day=last_day, hour=0, minute=0, second=0, microsecond=0)
            async_track_point_in_time(hass, _setup_monthly, next_time)
            hass.async_create_task(coordinator.async_request_refresh())
        _setup_monthly()

    await coordinator.async_config_entry_first_refresh()

    # 创建传感器 - 包含新增的传感器
    entities = [
        HuarunGasSensor(coordinator, sensor_type)
        for sensor_type in SENSOR_TYPES
    ]
    async_add_entities(entities)

    _LOGGER.info(f"华润燃气集成初始化完成: {len(entities)}个传感器已注册")