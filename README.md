# 华润燃气 Home Assistant 集成

![Version](https://img.shields.io/badge/version-v2.0.1-blue)
![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-green)
[![HACS Badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![License](https://img.shields.io/github/license/C3H3-AI/ha-crcgas?color=orange)
![GitHub Stars](https://img.shields.io/github/stars/C3H3-AI/ha-crcgas)
![Downloads](https://img.shields.io/github/downloads/C3H3-AI/ha-crcgas/total)
![Last Commit](https://img.shields.io/github/last-commit/C3H3-AI/ha-crcgas)

通过 Home Assistant 集成查看燃气账单、欠费、用气量、气价等信息，支持能源面板。

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

## 传感器（28个）

### 账单与余额
| 传感器 | 说明 | 单位 | device_class |
|--------|------|:----:|:-----------:|
| 欠费金额 | 当前欠费 | CNY | monetary |
| 燃气账户余额 | 账户余额 | CNY | monetary |
| 最近缴费金额 | 上次缴费金额 | CNY | monetary |
| 违约金 | 逾期违约金 | CNY | monetary |
| 账单金额 | 本期账单金额 | CNY | monetary |
| 预估燃气账单 | 按阶梯价计算 | CNY | monetary |

### 用气量
| 传感器 | 说明 | 单位 | device_class |
|--------|------|:----:|:-----------:|
| 本期表读数 | 燃气表总读数 | m³ | gas |
| 本期用气量 | 本期用量 | m³ | gas |
| 本月累计用气量 | 当月累计 | m³ | gas |
| 一档用气量 | 第一阶梯用量 | m³ | gas |
| 二档用气量 | 第二阶梯用量 | m³ | gas |
| 上月用气量 | 上期用量(参考) | m³ | gas |
| 年度月均用气量 | 12月平均 | m³ | gas |

### 气价与档位
| 传感器 | 说明 | 单位 |
|--------|------|:----:|
| 一档气价 | 第一阶梯单价 | CNY/m³ |
| 二档气价 | 第二阶梯单价 | CNY/m³ |
| 一档剩余气量 | 第一阶梯余量 | m³ |
| 二档剩余气量 | 第二阶梯余量 | m³ |

### 时间信息
| 传感器 | 说明 |
|--------|------|
| 本期抄表时间 | 上次抄表日期 |
| 最近缴费时间 | 最近一次缴费时间 |
| 年度缴费次数 | 当年缴费次数 |

### 信息类
| 传感器 | 说明 |
|--------|------|
| 集成状态 | 当前状态（正常/密钥过期等） |
| 用气地址 | 用气地址 |
| 燃气公司 | 燃气公司名 |
| 燃气类型 | 天然气/液化气 |
| 购气方式 | 物联网表/IC卡 |
| **燃气表总读数** ⭐ | 能源面板专用累计值 |
| **燃气表历史累计** ⭐ | 历史完整累计 |
| **累计燃气费用** ⭐ | 历史账单+当前预估总和 |

### 按钮
| 按钮 | 说明 |
|------|------|
| 刷新数据 | 手动触发数据更新 |
| 抓取历史记录 | 拉取所有历史账单并注入能源面板统计 |

## 功能特性

### ⚡ 数据刷新
- **API 并行请求** — 4 个接口同时查询，刷新速度从 3-5 秒降至 1-2 秒
- **阶梯气价动态读取** — 从 API 实时获取阶梯上限，不硬编码

### 📊 能源面板
- 所有传感器正确设置 `device_class`（gas/monetary）
- `燃气表总读数` 累计传感器可接入 HA 能源面板作为燃气总表
- **`燃气表历史累计` 传感器** ⭐ — 将历史用气数据完整注入统计表，首次启动自动填充
- 历史账单数据自动导入 HA 统计系统，支持趋势图表
- **零外部依赖** — 使用 Python 内置 sqlite3 直写数据库，不依赖 SQLAlchemy

### 🔔 异常通知
- Token 过期或网络异常时自动推送 HA 通知
- 恢复后通知自动消除

### 🔄 Token 刷新
- 每小时主动刷新 Token，无需手动干预
- 过期前 5 分钟紧急刷新，避免服务中断
- 集成状态传感器实时显示当前 Token 状态

### ⏱ 自定义刷新间隔
| 单位 | 说明 | 示例 |
|------|------|------|
| 小时 | 每 N 小时更新 | 1, 2, 3, 6, 12, 24 |
| 天 | 每天指定时间 | 每天 08:00 |
| 周 | 每周指定星期 | 每周一、三、五 |
| 月 | 每月指定日期 | 每月 1, 15 号 |

## 仪表盘卡片

### 燃气统计卡片
v2.0.0 提供了一个专用 Lovelace 卡片，展示月度用气量和燃气费趋势。

**添加：**
1. 设置 → 仪表盘 → 资源 → 添加资源
2. URL: `/local/community/crcgas-card/crcgas-statistics-card.js`
3. 类型: JavaScript 模块
4. 编辑仪表盘 → + 添加卡片 → 搜索「华润燃气统计」

### 统计图卡片（单实例）
```yaml
type: statistics-graph
entities:
  - entity: crcgas:monthly_gas_usage
    name: 月度用气量
  - entity: crcgas:monthly_bill_amount
    name: 月度燃气费
title: 华润燃气 年度趋势
days_to_show: 365
period: month
chart_type: line
stat_types:
  - state
  - change
```

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

## 故障排除

### Token 相关错误
- 检查三个参数是否填写正确
- Token 过期后集成会自动推送通知提醒
- 重新配置即可获取新 Token

### 数据不更新
- 检查网络连接
- 查看 HA 日志中的集成错误信息
- 尝试重启 HA Core

## 更新日志

### v2.0.1 (2026-06-23)
- 🐛 **修复能源面板负数问题** — 本月账单未出时总表读数保持上次值，不再跌为0

### v2.0.0 (2026-06-22)
- ✨ **燃气表历史累计传感器** — 专为能源面板设计，显示完整历史趋势
- ✨ **SQLite 直写统计注入** — 零外部依赖，Python 内置 sqlite3 直写数据库
- ✨ **一键抓取+注入** — 按钮触发时自动删除旧统计并写入历史完整累计数据
- ✨ **启动安全** — `only_missing` 模式，已有统计时跳过，不删除历史数据
- 🐛 **修复 SQLAlchemy 兼容性问题** — HA 2026.6.4 不再依赖 recorder 引擎
- 🐛 **修复启动时数据丢失** — 避免重启时误删已注入的历史统计

### v1.3.0 (2026-06-22)
- ✨ **API 并行请求** — 4 个接口同时查询，刷新 1-2 秒
- ✨ **阶梯气价动态读取** — 从 API 实时获取，不硬编码
- ✨ **device_class/state_class** — 传感器正确分类，支持能源面板
- ✨ **燃气表总读数** — 累计传感器，可直接接入 HA 能源面板
- ✨ **历史数据导入统计系统** — 月度用气量/费用趋势图
- ✨ **集成异常通知** — Token 过期/网络异常自动推送通知
- ✨ **集成状态中文显示** — 正常/密钥过期/网络异常等
- ✨ **精度控制** — 金额固定显示 2 位小数
- 🐛 **余额修复** — 获取失败返回不可用，不误报为 0

### v1.2.7
- 🔧 修复 Token 刷新逻辑：每小时无条件刷新 + 剩余<5分钟紧急刷新
- ✨ 新增紧急刷新定时器（每1分钟检查）

### v1.2.6
- ✨ 新增独立 Token 刷新定时器，每小时主动检查并刷新 Token
- 🔧 共享 API 实例，Token 刷新状态在 `__init__.py` 和 `sensor.py` 间同步
- 🔧 集成启动时立即执行一次 Token 检查

### v1.2.5
- ✨ 首次启动自动抓取历史记录

### v1.2.4
- 🐛 修复：删除实体 async_update 避免刷屏

### v1.2.3
- 🐛 修复：按钮延迟加载 + 非阻塞首次刷新

### v1.2.0
- ✨ 预估燃气账单传感器
- ✨ native_value 统一返回 float
- ✨ 自动保存用气历史
