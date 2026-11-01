# Changelog

## 2.1.1 (2026-11-01)

### 修复
- **Token 失效时日志刷屏**：`refresh-token` 失效（会话超时）是不可自愈的终态，
  但原实现里「整点刷新」和「每分钟紧急检查」各自打 ERROR，实测 **每分钟 6 行**，
  一小时 360+ 行，把 HA 的日志窗口（默认 100 行）完全占满，
  导致其它集成的真实故障被冲掉、无从排查。

  现在同一种失败**只在首次和每 30 分钟各报一次 ERROR**，其余降为 DEBUG；
  刷新成功时打一条「Token 已恢复（此前累计失败 N 次）」并复位计数。
  定时器的「开始刷新」「剩余 N 秒，立即刷新」也从 INFO 降为 DEBUG。

  实测：改动前 2 分钟 6+ 行 crcgas 日志，改动后 2 分钟 0 行。

## 2.1.0 (2026-09-21)

### 修复
- **统计重复累计**：月度统计导入对已存在月份改用 continue 跳过，
  以 recorder 数据库中的 last sum 作为初值，消除 sum 重复累计
- **statistics_meta 修正**：修复 has_mean/has_sum 为 null 的记录，
  并在启动 5 分钟后（recorder 编译完成）延时二次修正
- **bill_amount 兜底**：detail API 返回 0 时使用 revbl_amount 兜底

### 新增
- 24 个传感器的 state_class（MEASUREMENT/TOTAL），使长期统计正常生成
- 扫描周期 day/week/month 真正生效（原实现只有小时模式有效）

### 其他
- 全量文件与生产实测版对齐（api/config_flow/sensor_v1xx/前端卡片/中文文案）

## 2.0.7
- bootstrap CI + HACS validation workflow

## 2.0.6
- cold-start sum=0 fix for short-term statistic
