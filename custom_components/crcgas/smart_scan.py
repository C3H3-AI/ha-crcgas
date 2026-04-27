"""
CRC GAS 智能扫描服务

功能：
1. 智能扫描间隔推荐
2. 节假日模式
3. 数据变化检测
4. 通知系统
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    SMART_SCAN_ENABLED,
    SMART_SCAN_MODE,
    HOLIDAY_MODE_ENABLED,
    NOTIFICATION_ENABLED,
    NOTIFICATION_TYPES,
    RECOMMENDATION_THRESHOLDS,
    CHANGE_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_UNIT,
    SCAN_INTERVAL_UNITS
)

_LOGGER = logging.getLogger(__name__)


class SmartScanService:
    """智能扫描服务"""
    
    def __init__(self, hass: HomeAssistant, config_entry):
        self.hass = hass
        self.config_entry = config_entry
        self.history: Dict[str, Any] = {}
        self.last_scan_data: Optional[Dict] = None
        
    async def async_setup(self):
        """设置智能扫描服务"""
        if not self.config_entry.options.get(SMART_SCAN_ENABLED, True):
            _LOGGER.info("智能扫描功能已禁用")
            return
            
        # 启动历史数据加载
        await self._load_history()
        
        # 启动智能分析定时器（每24小时）
        async_track_time_interval(
            self.hass,
            self._analyze_usage_patterns,
            timedelta(hours=24)
        )
        
        _LOGGER.info("智能扫描服务已启动")
    
    async def get_recommended_scan_config(self, current_data: Dict) -> Dict[str, Any]:
        """获取推荐的扫描配置"""
        if not self.config_entry.options.get(SMART_SCAN_ENABLED, True):
            return {"use_smart": False}
            
        # 分析用气模式
        monthly_usage = current_data.get("this_gas_used", 0) or current_data.get("last_month_gas", 0)
        scan_mode = self.config_entry.options.get(SMART_SCAN_MODE, "balanced")
        
        # 基础推荐逻辑
        if monthly_usage < RECOMMENDATION_THRESHOLDS["low_usage"]:
            # 低用气量：推荐月更新
            recommended = {"unit": "month", "value": 1}
            reason = f"月用气量{monthly_usage}m³较低，推荐每月更新"
        elif monthly_usage < RECOMMENDATION_THRESHOLDS["medium_usage"]:
            # 中等用气量：推荐周更新
            recommended = {"unit": "week", "value": 1}
            reason = f"月用气量{monthly_usage}m³中等，推荐每周更新"
        else:
            # 高用气量：推荐日更新
            recommended = {"unit": "day", "value": 20}  # 每天20点更新
            reason = f"月用气量{monthly_usage}m³较高，推荐每日更新"
        
        # 根据模式调整
        if scan_mode == "conservative":
            # 保守模式：降低频率
            if recommended["unit"] == "day":
                recommended = {"unit": "week", "value": 1}
            elif recommended["unit"] == "week":
                recommended = {"unit": "month", "value": 1}
            reason += "（保守模式）"
        elif scan_mode == "aggressive":
            # 积极模式：提高频率
            if recommended["unit"] == "month":
                recommended = {"unit": "week", "value": 1}
            elif recommended["unit"] == "week":
                recommended = {"unit": "day", "value": 20}
            reason += "（积极模式）"
        
        # 检查节假日
        if self._is_holiday() and self.config_entry.options.get(HOLIDAY_MODE_ENABLED, True):
            recommended = {"unit": "day", "value": 12}  # 节假日每天中午更新
            reason = "节假日期间，每天中午更新"
        
        return {
            "use_smart": True,
            "recommended": recommended,
            "reason": reason,
            "current_monthly_usage": monthly_usage
        }
    
    async def check_data_changes(self, new_data: Dict) -> Optional[Dict[str, Any]]:
        """检查数据变化，返回需要通知的变化"""
        if not self.last_scan_data:
            self.last_scan_data = new_data
            return None
            
        changes = {}
        
        for key, threshold in CHANGE_THRESHOLD.items():
            old_val = self.last_scan_data.get(key)
            new_val = new_data.get(key)
            
            if old_val is not None and new_val is not None:
                try:
                    old_val = float(old_val)
                    new_val = float(new_val)
                    change = abs(new_val - old_val)
                    
                    if change > threshold:
                        changes[key] = {
                            "old": old_val,
                            "new": new_val,
                            "change": change,
                            "threshold": threshold
                        }
                except (ValueError, TypeError):
                    # 非数值类型跳过
                    pass
        
        self.last_scan_data = new_data
        
        if changes and self.config_entry.options.get(NOTIFICATION_ENABLED, True):
            return {
                "changes": changes,
                "timestamp": dt_util.now().isoformat()
            }
        
        return None
    
    async def _analyze_usage_patterns(self, now=None):
        """分析用气模式（定时任务）"""
        try:
            # 分析月度用气趋势
            monthly_avg = await self._calculate_monthly_average()
            
            # 检测用气高峰时段
            peak_hours = await self._detect_peak_hours()
            
            # 生成用气报告
            report = {
                "monthly_average": monthly_avg,
                "peak_hours": peak_hours,
                "last_analyzed": dt_util.now().isoformat(),
                "recommendations": await self._generate_recommendations(monthly_avg, peak_hours)
            }
            
            # 保存分析结果
            await self._save_analysis_report(report)
            
            _LOGGER.debug(f"用气模式分析完成: 月均{monthly_avg}m³, 高峰时段{peak_hours}")
            
        except Exception as e:
            _LOGGER.error(f"用气模式分析失败: {e}")
    
    async def _calculate_monthly_average(self) -> float:
        """计算月度平均用气量"""
        if not self.history:
            return 0.0
        
        monthly_data = []
        for record in self.history.get("monthly_records", []):
            if "this_gas_used" in record:
                monthly_data.append(record["this_gas_used"])
        
        if not monthly_data:
            return 0.0
            
        return sum(monthly_data) / len(monthly_data)
    
    async def _detect_peak_hours(self) -> list:
        """检测用气高峰时段（简化版）"""
        # 这里可以实现更复杂的算法，暂时返回固定值
        return [18, 19, 20]  # 晚上6-9点
    
    async def _generate_recommendations(self, monthly_avg: float, peak_hours: list) -> list:
        """生成节能建议"""
        recommendations = []
        
        if monthly_avg > RECOMMENDATION_THRESHOLDS["high_usage"]:
            recommendations.append({
                "type": "usage_high",
                "message": "您的用气量较高，建议检查燃气设备是否有泄漏",
                "priority": "high"
            })
        
        if peak_hours and len(peak_hours) > 2:
            recommendations.append({
                "type": "peak_hours",
                "message": f"用气高峰集中在{','.join(map(str, peak_hours))}点，建议错峰使用",
                "priority": "medium"
            })
            
        return recommendations
    
    def _is_holiday(self) -> bool:
        """检查是否为节假日（简化版）"""
        now = dt_util.now()
        
        # 检查周末
        if now.weekday() >= 5:  # 5=周六, 6=周日
            return True
            
        # 检查法定节假日（简化版）
        holidays = [
            (1, 1),   # 元旦
            (5, 1),   # 劳动节
            (10, 1),  # 国庆节
            (10, 2),
            (10, 3),
        ]
        
        return (now.month, now.day) in holidays
    
    async def _load_history(self):
        """加载历史数据"""
        try:
            # 可以从文件或HA存储加载历史数据
            # 这里简化实现
            self.history = {"monthly_records": []}
        except Exception as e:
            _LOGGER.warning(f"加载历史数据失败: {e}")
            self.history = {"monthly_records": []}
    
    async def _save_analysis_report(self, report: Dict):
        """保存分析报告"""
        try:
            # 保存到HA存储或文件
            # 这里简化实现
            pass
        except Exception as e:
            _LOGGER.error(f"保存分析报告失败: {e}")


async def setup_smart_scan(hass: HomeAssistant, config_entry) -> SmartScanService:
    """设置智能扫描服务"""
    service = SmartScanService(hass, config_entry)
    await service.async_setup()
    return service