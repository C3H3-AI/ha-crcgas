# 华润燃气 Home Assistant 集成

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

| 传感器 | 说明 | 单位 |
|--------|------|------|
| `sensor.crcgas_arrears` | 当前欠费金额 | ¥ |
| `sensor.crcgas_last_bill_amount` | 上期账单金额 | ¥ |
| `sensor.crcgas_last_bill_gas` | 上期用气量 | m³ |
| `sensor.crcgas_last_mr_date` | 最近抄表日期 | - |
| `sensor.crcgas_bill_list` | 账单数量 | N期 |
| `sensor.crcgas_account` | 户号信息 | - |

## 数据更新

- 更新间隔: 初始30分钟（自动调整：成功+10分钟，失败-10分钟）
- Token 自动刷新: 无需手动重新授权
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
- 更新: 动态调整间隔（5-60分钟）

## 故障排除

### Token 刷新失败
- 进入集成设置 → 重新授权
- 重新抓包获取新的 tokens

### 数据不更新
- 检查网络连接
- 重启 HA Core
