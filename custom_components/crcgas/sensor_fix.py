"""华润燃气传感器修复 - 添加详细日志和错误处理"""

import logging
from typing import Any, Dict

_LOGGER = logging.getLogger(__name__)


def parse_step_remain(detail_data: Dict[str, Any]) -> Dict[str, float]:
    """
    解析账单详情中的阶梯剩余气量
    
    处理多种API返回格式：
    1. 标准格式: {'gasStepList': [{'stepType': '一档', 'stepRemain': 200}]}
    2. 无stepRemain: {'gasStepList': [{'stepType': '一档', 'gasUsed': 100}]}
    3. 无gasStepList: {}
    """
    result = {
        'step1_remain': 0,
        'step2_remain': 0,
        'step1_gas_used': 0,
    }
    
    if not detail_data or not detail_data.get('success'):
        _LOGGER.warning("账单详情数据为空或失败")
        return result
    
    details = detail_data.get('dataResult', [])
    if not details or not isinstance(details, list):
        _LOGGER.warning("账单详情dataResult为空或格式错误")
        return result
    
    detail = details[0]
    _LOGGER.debug(f"账单详情原始数据: {detail}")
    
    # 获取基本读数信息
    result['this_read'] = detail.get('thisRead', 0)
    result['this_read_time'] = detail.get('thisReadTime', '未知')
    result['this_gas_used'] = detail.get('thisGas', 0)
    result['bill_amount'] = detail.get('totalAmount', 0) or detail.get('billAmount', 0)
    result['penalty_amount'] = detail.get('penaltyAmount', 0)
    
    # 解析阶梯信息
    step_list = detail.get('gasStepList', [])
    if not step_list:
        _LOGGER.warning("账单详情中没有gasStepList字段或为空")
        return result
    
    _LOGGER.debug(f"找到 {len(step_list)} 个阶梯信息")
    
    for step in step_list:
        step_type = step.get('stepType', '')
        gas_used = step.get('gasUsed', 0)
        step_remain = step.get('stepRemain', None)  # 使用None检查字段是否存在
        
        _LOGGER.debug(f"阶梯信息: type={step_type}, used={gas_used}, remain={step_remain}")
        
        if '一档' in step_type:
            result['step1_gas_used'] = gas_used
            if step_remain is not None:
                result['step1_remain'] = float(step_remain)
            else:
                _LOGGER.warning(f"一档信息中没有stepRemain字段: {step}")
        elif '二档' in step_type:
            if step_remain is not None:
                result['step2_remain'] = float(step_remain)
            else:
                _LOGGER.warning(f"二档信息中没有stepRemain字段: {step}")
    
    return result


def safe_float(value: Any, default: float = 0) -> float:
    """安全转换为float"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        _LOGGER.warning(f"无法转换为float: {value}")
        return default