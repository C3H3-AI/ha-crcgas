# 华润燃气 Home Assistant 集成

![Version](https://img.shields.io/badge/version-v1.10-blue)
![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.4%2B-green)
![License](https://img.shields.io/badge/license-MIT-orange)

通过 Home Assistant 集成查看燃气账单、欠费、用气量等信息。

## 安装

### 方法1: HACS 安装
1. 打开 HACS
2. 点击 Integrations
3. 点击右上角 ⋮ → Custom repositories
4. 添加: `https://github.com/C3H3-AI/ha-crcgas`
5. 搜索并安装 "华润燃气"

### 方法2: 手动安装
```bash
# 复制到 custom_components 目录
cp -r ha-crcgas ~/.homeassistant/custom_components/
```

## 配置

### 1. 获取 Tokens（通过 HAR 抓包）
1. 打开浏览器开发者工具 → Network → 勾选 Preserve log
2. 打开微信 **华润燃气** 小程序并登录
3. 登录后，在 Network 中找到任意一个 `wmp-svc.crcgas.com` 的请求
4. 复制请求头中的：
   - `refresh-token` 的值
   - `bo-token` 的值
   - `wxCode` 的值
5. 或导出 HAR 文件，从请求头中提取 tokens

### 2. 添加集成
1. HA → 设置 → 设备与服务 → 添加集成
2. 搜索 **华润燃气**
3. 粘贴 `refresh-token`、`bo-token` 和 `wxCode`
4. 完成配置

## 传感器

安装后会创建以下传感器:

| 传感器实体 | 说明 | 单位 |
|------------|------|------|
| `sensor.crcgas_arrears` | 欠费金额 | ¥ |
| `sensor.crcgas_account_balance` | 燃气账户余额 | ¥ |
| `sensor.crcgas_last_pay_time` | 最近缴费时间 | - |
| `sensor.crcgas_last_pay_amount` | 最近缴费金额 | ¥ |
| `sensor.crcgas_annual_pay_count` | 年度缴费次数 | 次 |
| `sensor.crcgas_this_read` | 本期表读数 | m³ |
| `sensor.crcgas_this_read_time` | 本期抄表时间 | - |
| `sensor.crcgas_step1_gas_used` | 一档用气量 | m³ |
| `sensor.crcgas_step2_gas_used` | 二档用气量 | m³ |
| `sensor.crcgas_this_gas_used` | 本期用气量 | m³ |
| `sensor.crcgas_bill_amount` | 账单金额 | ¥ |
| `sensor.crcgas_step1_remain` | 一档剩余气量 | m³ |
| `sensor.crcgas_step2_remain` | 二档剩余气量 | m³ |
| `sensor.crcgas_penalty_amount` | 违约金 | ¥ |
| `sensor.crcgas_integration_status` | 集成状态 | - |
| `sensor.crcgas_monthly_gas_used` | 本月累计用气量 | m³ |
| `sensor.crcgas_cons_addr` | 用气地址 | - |
| `sensor.crcgas_org_name` | 燃气公司 | - |
| `sensor.crcgas_gas_nature` | 燃气类型 | - |
| `sensor.crcgas_purchase_style` | 购气方式 | - |
| `sensor.crcgas_last_month_gas` | 上月用气量 | m³ |
| `sensor.crcgas_year_avg_gas` | 年度月均用气量 | m³ |

## 数据更新

- 更新间隔: 可自定义（1/2/3/6/12/24小时），默认1小时
- Token 自动刷新: 无需手动重新授权（自动每1小时刷新一次）
- 欠费提醒: 可配合 HA Automation 实现

## 示例 Automation

```yaml
# 欠费提醒
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

## 技术信息

- API: `wmp-svc.crcgas.com`
- 认证: JWT Token（从 HAR 抓包提取）
- 平台: cloud_polling
- 更新: 可配置间隔（1-24小时）

## 配置选项

### 数据更新间隔

支持多种更新频率：

| 单位 | 说明 | 示例 |
|------|------|------|
| **小时** | 每N小时更新一次 | 1, 2, 3, 6, 12, 20, 24 |
| **天** | 每天指定时间更新 | 每天 08:00 |
| **周** | 每周指定星期几更新 | 每周一、周三、周五 |
| **月** | 每月指定日期更新 | 每月 1, 15 号 |

### Token刷新

- 自动刷新：每1小时自动刷新Token，无需手动操作
- 状态监控：`sensor.crcgas_integration_status` 可查看Token状态

| 选项 | 说明 | 默认值 |
|------|------|--------|
| 数据更新间隔 | 多久抓取一次数据 | 1小时 |
| Token刷新 | 自动每1小时刷新Token | 开启 |

## 故障排除

### Token 刷新失败
- 进入集成设置 → 重新授权
- 重新抓包获取新的 tokens

### 数据不更新
- 检查网络连接
- 重启 HA Core
