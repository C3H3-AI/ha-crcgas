"""
CRC GAS传感器修复补丁
添加详细的日志记录和错误处理
"""

# 在async_update_data函数中添加以下日志

# 在获取账单详情后添加：
"""
        # 5. 获取账单详情（一档用气量、本期读数、用气量、账单金额、阶梯剩余）
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
                                if step_remain != "字段不存在":
                                    result["step2_remain"] = float(step_remain)
                                    _LOGGER.info(f"二档剩余: {result['step2_remain']}")
                                else:
                                    _LOGGER.warning("二档信息中缺少stepRemain字段")
                        
                        _LOGGER.info(f"账单详情解析完成: 一档剩余={result['step1_remain']}, 二档剩余={result['step2_remain']}")
                    else:
                        _LOGGER.warning("账单详情dataResult为空或格式错误")
                else:
                    _LOGGER.warning(f"账单详情API调用失败: {detail_data}")
            else:
                _LOGGER.warning(f"缺少账单信息: bill_ym={bill_ym}, app_no={app_no}")
                
        except SessionTimeoutError:
            session_timeout_count += 1
            _LOGGER.warning(f"获取账单详情: 会话超时")
        except Exception as e:
            _LOGGER.error(f"获取账单详情失败: {e}")
"""