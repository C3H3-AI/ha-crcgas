# 华润燃气 Home Assistant 集成

![Version](https://img.shields.io/badge/version-v1.2.0-blue)
![HA Version](https://img.shields.io/badge/Home%20Assistant-2026.4%2B-green)
![License](https://img.shields.io/badge/license-MIT-orange)

通过 Home Assistant 集成查看燃气账单、欠费、用气量、气价等信息。

## 安装

### 方法1: HACS 安装（推荐）
1. 打开 HACS
2. 点击 Integrations
3. 点击右上角 `?` → Custom repositories
4. 添加仓库地址: `https://github.com/C3H3-AI/ha-crcgas`
5. 类别选择 `Integration`
6. 搜索并安装 "华润燃气"

### 方法2: 手动安装
```bash
# 复制到 custom_components 目录
cp -r crcgas ~/.homeassistant/custom_components/
```

## 配置

### 获取认证参数
登录微信 **华润燃气** 小程序，从网络请求头中提取以下三个参数：

| 参数 | 说明 | 来源 |
|------|------|------|
| `refresh-token` | 刷新令牌 | 请求头 |
| `bo-token` | 运营令牌 | 请求头 |
| `wxCode` | 微信授权码 | 请求头 |

### 添加集成
1. HA → 设置 → 设备与服务 → 添加集成
2. 搜索 **华润燃气**
3. 填写 `refresh-token`、`bo-token`、`wxCode`
4. 完成配置

## 传感器

安装后创建以下传感器：

### 账单与余额
| 传感器实体 | 说明 | 单位 |
|------------|------|------|
| `sensor.crcgas_arrears` | 欠费金额 | ¥ |
| `sensor.crcgas_account_balance` | 燃气账户余额 | ¥ |
| `sensor.crcgas_bill_amount` | 账单金额 | ¥ |
| `sensor.crcgas_penalty_amount` | 违约金 | ¥ |
| `sensor.crcgas_estimated_gas_bill_amount` | 预估燃气账单 | ¥ |

### 用气量
| 传感器实体 | 说明 | 单位 |
|------------|------|------|
| `sensor.crcgas_this_gas_used` | 本期用气量 | m³ |
| `sensor.crcgas_step1_gas_used` | 一档用气量 | m³ |
| `sensor.crcgas_step2_gas_used` | 二档用气量 | m³ |
| `sensor.crcgas_monthly_gas_used` | 本月累计用气量 | m³ |
| `sensor.crcgas_last_month_gas` | 上月用气量 | m³ |
| `sensor.crcgas_year_avg_gas` | 年度月均用气量 | m³ |

### 气价
| 传感器实体 | 说明 | 单位 |
|------------|------|------|
| `sensor.crcgas_gas_price_step1` | 一档气价 | ¥/m³ |
| `sensor.crcgas_gas_price_step2` | 二档气价 | ¥/m³ |

### 档位
| 传感器实体 | 说明 | 单位 |
|------------|------|------|
| `sensor.crcgas_step1_remain` | 一档剩余气量 | m³ |
| `sensor.crcgas_step2_remain` | 二档剩余气量 | m³ |

### 抄表信息
| 传感器实体 | 说明 | 单位 |
|------------|------|------|
| `sensor.crcgas_this_read` | 本期表读数 | m³ |
| `sensor.crcgas_this_read_time` | 本期抄表时间 | - |

### 缴费记录
| 传感器实体 | 说明 | 单位 |
|------------|------|------|
| `sensor.crcgas_last_pay_time` | 最近缴费时间 | - |
| `sensor.crcgas_last_pay_amount` | 最近缴费金额 | ¥ |
| `sensor.crcgas_annual_pay_count` | 年度缴费次数 | - |

### 信息类
| 传感器实体 | 说明 |
|------------|------|
| `sensor.crcgas_cons_addr` | 用气地址 |
| `sensor.crcgas_org_name` | 燃气公司 |
| `sensor.crcgas_gas_nature` | 燃气类型 |
| `sensor.crcgas_purchase_style` | 购气方式 |
| `sensor.crcgas_integration_status` | 集成状态 |

### 按钮
| 按钮实体 | 说明 |
|----------|------|
| `button.crcgas_fetch_history` | 抓取所有历史记录 |
| `button.crcgas_refresh_data` | 刷新数据 |

## 配置选项

### 数据更新间隔
| 单位 | 说明 | 示例 |
|------|------|------|
| 小时 | 每 N 小时更新 | 1, 2, 3, 6, 12, 24 |
| 天 | 每天指定时间 | 每天 08:00 |
| 周 | 每周指定星期 | 每周一、三、五 |
| 月 | 每月指定日期 | 每月 1, 15 号 |

### Token 刷新
- Token 约每 4.5 小时自动刷新（refresh-token），bo-token 约 3 小时
- 状态传感器 `sensor.crcgas_integration_status` 可查看当前状态

## Automation 示例

```yaml
# 燃气欠费提醒
automation:
  - alias: "燃气欠费提醒"
    trigger:
      - platform: state
        entity_id: sensor.crcgas_arrears
    condition:
      - condition: numeric_state
        entity_id: sensor.crcgas_arrears
        above: 0
    action:
      - service: notify.notify
        data:
          message: "您有燃气欠费 ¥{{ states('sensor.crcgas_arrears') }}"
```

## 仪表盘卡片

### 统一账单卡片（推荐）

推荐使用 [统一账单卡片](https://github.com/C3H3-AI/ha-utility-bill-card)，同时支持华润燃气和温州水务。

1. **添加资源引用**
   - 进入 设置 → 仪表盘 → 资源
   - 点击"添加资源"
   - URL: `/local/community/utility-bill-card/utility-bill-card.js`
   - 类型: 选择 **JavaScript 模块**

2. **添加卡片到仪表盘**
   - 打开任意仪表盘，点击右上角"编辑"
   - 点击"添加卡片"
   - 选择"手动配置"（或在搜索中搜索）
   - 粘贴以下配置：

   ```yaml
   type: custom:utility-bill-card
   entity: sensor.crcgas_account_balance
   title: 华润燃气
   ```

## 故障排除

### Token 相关错误
- 检查三个参数是否填写正确
- Token 过期后需重新获取并重新配置集成

### 数据不更新
- 检查网络连接
- 查看 HA 日志中的集成错误信息
- 尝试重启 HA Core
