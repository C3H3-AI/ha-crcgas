"""本地历史数据存储模块

功能：
1. 保存用气历史数据
2. 保存缴费历史记录
3. 保存账单历史记录
4. 提供数据查询接口
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, HISTORY_STORAGE_VERSION, HISTORY_RETENTION_MONTHS

_LOGGER = logging.getLogger(__name__)


class CRCGasHistoryStorage:
    """CRC GAS 历史数据存储管理器"""

    def __init__(self, hass: HomeAssistant, entry_id: str):
        self.hass = hass
        self.entry_id = entry_id
        self.store = Store(
            hass, 
            HISTORY_STORAGE_VERSION, 
            f"{DOMAIN}_history_{entry_id}"
        )
        self._data = {
            "usage_history": [],  # 用气历史
            "payment_history": [],  # 缴费历史
            "bill_history": [],  # 账单历史
            "last_update": None,
        }

    async def async_load(self):
        """加载历史数据"""
        stored = await self.store.async_load()
        if stored:
            self._data = stored
            _LOGGER.info(f"已加载历史数据: {len(self._data.get('usage_history', []))} 条用气记录")
        else:
            _LOGGER.info("没有找到历史数据，创建新的存储")

    async def async_save(self):
        """保存历史数据"""
        self._data["last_update"] = datetime.now().isoformat()
        await self.store.async_save(self._data)
        _LOGGER.debug("历史数据已保存")

    async def async_add_usage_record(self, record: Dict[str, Any]):
        """添加用气记录"""
        record["timestamp"] = datetime.now().isoformat()
        self._data["usage_history"].append(record)
        
        # 清理过期数据
        self._cleanup_old_data()
        await self.async_save()

    async def async_add_payment_record(self, record: Dict[str, Any]):
        """添加缴费记录"""
        record["timestamp"] = datetime.now().isoformat()
        self._data["payment_history"].append(record)
        await self.async_save()

    async def async_add_bill_record(self, record: Dict[str, Any]):
        """添加账单记录"""
        record["timestamp"] = datetime.now().isoformat()
        self._data["bill_history"].append(record)
        await self.async_save()

    async def async_fetch_all_bills(self, api, cons_no: str) -> Dict[str, Any]:
        """从API抓取所有历史账单
        
        Args:
            api: HuarunGasApi实例
            cons_no: 户号
            
        Returns:
            抓取结果统计
        """
        _LOGGER.info("开始抓取所有历史账单记录...")
        
        # 获取现有账单记录（用于去重）
        existing_bills = {
            b.get("applicationNo"): b 
            for b in self._data.get("bill_history", [])
            if b.get("applicationNo")
        }
        
        page = 1
        page_size = 20
        total_fetched = 0
        new_bills = 0
        updated_bills = 0
        
        while True:
            try:
                bill_data = await api.async_get_gas_bill_list(cons_no, page=page, page_num=page_size)
                if not bill_data or not bill_data.get("success"):
                    break
                    
                data_result = bill_data.get("dataResult", {})
                bills = data_result.get("data", []) if isinstance(data_result, dict) else []
                
                if not bills:
                    break
                    
                for bill in bills:
                    app_no = bill.get("applicationNo")
                    if not app_no:
                        continue
                        
                    # 构建账单记录
                    bill_record = {
                        "applicationNo": app_no,
                        "billYm": bill.get("billYm"),
                        "billAmt": float(bill.get("billAmt", 0) or 0),
                        "gasAmt": float(bill.get("gasAmt", 0) or 0),
                        "penaltyAmt": float(bill.get("penaltyAmt", 0) or 0),
                        "revblAmt": float(bill.get("revblAmt", 0) or 0),
                        "settleFlag": bill.get("settleFlag"),
                        "penaltyDate": bill.get("penaltyDate"),
                        "fetched_at": datetime.now().isoformat(),
                    }
                    
                    if app_no in existing_bills:
                        # 更新现有记录
                        existing_bills[app_no].update(bill_record)
                        updated_bills += 1
                    else:
                        # 新记录
                        existing_bills[app_no] = bill_record
                        new_bills += 1
                        
                total_fetched += len(bills)
                _LOGGER.info(f"第{page}页: 获取{len(bills)}条记录")
                
                if len(bills) < page_size:
                    break
                    
                page += 1
                
            except Exception as e:
                _LOGGER.error(f"获取第{page}页账单失败: {e}")
                break
        
        # 更新账单历史
        self._data["bill_history"] = list(existing_bills.values())
        # 按账期排序（最新的在前）
        self._data["bill_history"].sort(
            key=lambda x: x.get("billYm", ""), 
            reverse=True
        )
        
        # 同时更新用气历史（从账单中提取）
        await self._sync_usage_from_bills()
        
        # 保存
        await self.async_save()
        
        result = {
            "total_fetched": total_fetched,
            "new_bills": new_bills,
            "updated_bills": updated_bills,
            "total_stored": len(self._data["bill_history"]),
        }
        
        _LOGGER.info(
            f"历史账单抓取完成: "
            f"新增{new_bills}条, "
            f"更新{updated_bills}条, "
            f"总计{len(self._data['bill_history'])}条"
        )
        return result
        
    async def _sync_usage_from_bills(self):
        """从账单记录同步用气历史"""
        usage_history = []
        for bill in self._data.get("bill_history", []):
            if bill.get("billYm") and bill.get("gasAmt") is not None:
                usage_history.append({
                    "timestamp": f"{bill['billYm']}-01T00:00:00",
                    "gas_used": bill["gasAmt"],
                    "bill_amount": bill.get("billAmt", 0),
                    "applicationNo": bill.get("applicationNo"),
                })
        
        self._data["usage_history"] = usage_history
        _LOGGER.debug(f"用气历史已同步: {len(usage_history)} 条记录")
        
    def get_all_bills(self) -> List[Dict[str, Any]]:
        """获取所有账单记录"""
        return self._data.get("bill_history", [])
        
    def get_bills_by_year(self, year: int) -> List[Dict[str, Any]]:
        """获取指定年份的账单"""
        return [
            b for b in self._data.get("bill_history", [])
            if b.get("billYm", "").startswith(str(year))
        ]
        
    def get_yearly_summary(self, year: int) -> Dict[str, Any]:
        """获取年度汇总"""
        bills = self.get_bills_by_year(year)
        return {
            "year": year,
            "total_bills": len(bills),
            "total_gas": round(sum(b.get("gasAmt", 0) for b in bills), 2),
            "total_amount": round(sum(b.get("billAmt", 0) for b in bills), 2),
            "avg_gas": round(sum(b.get("gasAmt", 0) for b in bills) / len(bills), 2) if bills else 0,
        }

    def _cleanup_old_data(self):
        """清理过期数据"""
        cutoff_date = datetime.now() - timedelta(days=HISTORY_RETENTION_MONTHS * 30)
        
        for key in ["usage_history", "payment_history", "bill_history"]:
            self._data[key] = [
                record for record in self._data.get(key, [])
                if self._parse_timestamp(record.get("timestamp", "")) > cutoff_date
            ]

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """解析时间戳"""
        try:
            return datetime.fromisoformat(timestamp_str)
        except:
            return datetime.min

    def get_usage_history(self, limit: int = 12) -> List[Dict[str, Any]]:
        """获取用气历史"""
        return self._data.get("usage_history", [])[-limit:]

    def get_payment_history(self, limit: int = 12) -> List[Dict[str, Any]]:
        """获取缴费历史"""
        return self._data.get("payment_history", [])[-limit:]

    def get_bill_history(self, limit: int = 12) -> List[Dict[str, Any]]:
        """获取账单历史"""
        return self._data.get("bill_history", [])[-limit:]

    def get_monthly_usage(self, year: int, month: int) -> float:
        """获取指定月份用气量"""
        usage_records = self._data.get("usage_history", [])
        total = 0
        for record in usage_records:
            try:
                record_date = datetime.fromisoformat(record.get("timestamp", ""))
                if record_date.year == year and record_date.month == month:
                    total += float(record.get("gas_used", 0))
            except:
                continue
        return total

    def get_yearly_usage(self, year: int) -> float:
        """获取指定年度用气量"""
        usage_records = self._data.get("usage_history", [])
        total = 0
        for record in usage_records:
            try:
                record_date = datetime.fromisoformat(record.get("timestamp", ""))
                if record_date.year == year:
                    total += float(record.get("gas_used", 0))
            except:
                continue
        return total

    def get_usage_trend(self, months: int = 12) -> List[Dict[str, Any]]:
        """获取用气趋势数据"""
        usage_records = self._data.get("usage_history", [])
        
        # 按月份分组
        monthly_data = {}
        for record in usage_records:
            try:
                record_date = datetime.fromisoformat(record.get("timestamp", ""))
                key = f"{record_date.year}-{record_date.month:02d}"
                if key not in monthly_data:
                    monthly_data[key] = 0
                monthly_data[key] += float(record.get("gas_used", 0))
            except:
                continue
        
        # 转换为列表并排序
        trend = [
            {"month": month, "usage": usage}
            for month, usage in sorted(monthly_data.items())
        ]
        
        return trend[-months:]


async def async_setup_history_storage(hass: HomeAssistant, entry_id: str) -> CRCGasHistoryStorage:
    """设置历史数据存储"""
    storage = CRCGasHistoryStorage(hass, entry_id)
    await storage.async_load()
    return storage