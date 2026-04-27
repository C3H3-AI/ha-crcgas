"""华润燃气 历史记录管理器

功能:
1. 一键抓取所有历史账单记录
2. 保存到本地JSON文件
3. 支持增量更新（只获取新月份）
4. 提供数据导出功能
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class HistoryManager:
    """历史记录管理器"""
    
    def __init__(self, hass, config_entry_id: str):
        self.hass = hass
        self.config_entry_id = config_entry_id
        # 存储路径: <config>/.storage/crcgas_history/<entry_id>.json
        self.storage_dir = hass.config.path(".storage", "crcgas_history")
        self.storage_file = os.path.join(self.storage_dir, f"{config_entry_id}.json")
        
    def _ensure_storage(self):
        """确保存储目录存在"""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)
            
    def load_history(self) -> Dict:
        """加载历史记录"""
        self._ensure_storage()
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                _LOGGER.error(f"加载历史记录失败: {e}")
        return {
            "version": 1,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "bills": [],  # 账单列表
            "monthly_summary": {},  # 月度汇总
            "stats": {
                "total_bills": 0,
                "total_gas_used": 0,
                "total_amount": 0,
                "first_bill_date": None,
                "last_bill_date": None,
            }
        }
        
    def save_history(self, data: Dict):
        """保存历史记录"""
        self._ensure_storage()
        data["updated_at"] = datetime.now().isoformat()
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            _LOGGER.info(f"历史记录已保存: {self.storage_file}")
        except Exception as e:
            _LOGGER.error(f"保存历史记录失败: {e}")
            
    async def fetch_all_history(self, api, cons_no: str) -> Dict:
        """抓取所有历史记录
        
        Args:
            api: HuarunGasApi实例
            cons_no: 户号
            
        Returns:
            抓取结果统计
        """
        _LOGGER.info("开始抓取所有历史账单记录...")
        
        # 加载现有历史
        history = self.load_history()
        existing_bills = {b["applicationNo"]: b for b in history["bills"]}
        
        # 获取所有账单
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
                
        # 更新历史记录
        history["bills"] = list(existing_bills.values())
        history["bills"].sort(key=lambda x: x.get("billYm", ""), reverse=True)
        
        # 计算统计信息
        self._update_stats(history)
        
        # 生成月度汇总
        self._generate_monthly_summary(history)
        
        # 保存
        self.save_history(history)
        
        result = {
            "total_fetched": total_fetched,
            "new_bills": new_bills,
            "updated_bills": updated_bills,
            "total_stored": len(history["bills"]),
            "stats": history["stats"],
        }
        
        _LOGGER.info(f"历史记录抓取完成: 新增{new_bills}条, 更新{updated_bills}条, 总计{len(history['bills'])}条")
        return result
        
    def _update_stats(self, history: Dict):
        """更新统计信息"""
        bills = history["bills"]
        if not bills:
            return
            
        stats = {
            "total_bills": len(bills),
            "total_gas_used": round(sum(b.get("gasAmt", 0) for b in bills), 2),
            "total_amount": round(sum(b.get("billAmt", 0) for b in bills), 2),
            "first_bill_date": bills[-1].get("billYm"),
            "last_bill_date": bills[0].get("billYm"),
        }
        history["stats"] = stats
        
    def _generate_monthly_summary(self, history: Dict):
        """生成月度汇总"""
        monthly = {}
        for bill in history["bills"]:
            ym = bill.get("billYm")
            if not ym:
                continue
                
            year = ym[:4]
            month = ym[5:7]
            
            if year not in monthly:
                monthly[year] = {}
                
            monthly[year][month] = {
                "gasAmt": bill.get("gasAmt", 0),
                "billAmt": bill.get("billAmt", 0),
                "applicationNo": bill.get("applicationNo"),
            }
            
        history["monthly_summary"] = monthly
        
    async def fetch_monthly_increment(self, api, cons_no: str, year_month: str) -> Optional[Dict]:
        """抓取指定月份的增量数据
        
        Args:
            api: HuarunGasApi实例
            cons_no: 户号
            year_month: 年月格式 YYYY-MM
            
        Returns:
            该月账单数据或None
        """
        _LOGGER.info(f"抓取 {year_month} 的账单数据...")
        
        try:
            bill_data = await api.async_get_gas_bill_list(cons_no, page=1, page_num=20)
            if not bill_data or not bill_data.get("success"):
                return None
                
            data_result = bill_data.get("dataResult", {})
            bills = data_result.get("data", []) if isinstance(data_result, dict) else []
            
            for bill in bills:
                if bill.get("billYm") == year_month:
                    return {
                        "applicationNo": bill.get("applicationNo"),
                        "billYm": bill.get("billYm"),
                        "billAmt": float(bill.get("billAmt", 0) or 0),
                        "gasAmt": float(bill.get("gasAmt", 0) or 0),
                        "penaltyAmt": float(bill.get("penaltyAmt", 0) or 0),
                        "settleFlag": bill.get("settleFlag"),
                    }
                    
        except Exception as e:
            _LOGGER.error(f"抓取 {year_month} 数据失败: {e}")
            
        return None
        
    def get_history_data(self) -> Dict:
        """获取历史数据（供传感器读取）"""
        return self.load_history()
