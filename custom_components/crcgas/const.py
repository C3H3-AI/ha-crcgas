"""华润燃气 HA集成常量定义 - 更新版"""

from homeassistant.const import Platform

# 平台
DOMAIN = "crcgas"
PLATFORM_NAME = "华润燃气"  # 集成显示名称
PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

# API配置
BASE_URL = "https://wmp-svc.crcgas.com/wmp-wechat-rest"

# API端点
API_GET_LOGIN_INFO = "/public/mp/getMpLoginInfo"
API_GET_BINDING_CONS = "/binding/getMpBindingCons"
API_GET_GAS_BILL_LIST = "/bill/getGasBillList"
API_GET_BILL_DETAIL = "/bill/getBillDetail"
API_QUERY_ARREARS = "/mp/pay/queryArrears"
API_GET_BO_TOKEN = "/public/mp/getBoToken4Mp"
API_DO_REFRESH_TOKEN = "/public/doRefreshToken"
API_QUERY_PAY_HISTORY = "/mp/pay/queryPayHistory"
API_GET_GAS_BILL_LIST_4_CHART = "/bill/getGasBillList4Chart"

# 配置键
CONF_REFRESH_TOKEN = "refresh_token"
CONF_BO_TOKEN = "bo_token"
CONF_WX_CODE = "wx_code"
CONF_SERVICE_PASSWORD = "service_password"
CONF_AREA = "area"
CONF_CONS_NO = "cons_no"
CONF_CONS_NAME = "cons_name"
CONF_CONS_ADDR = "cons_addr"
CONF_MOBILE = "mobile"

# 自定义配置
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SCAN_INTERVAL_UNIT = "scan_interval_unit"
SCAN_INTERVAL_UNITS = {
    "hour": "小时（每N小时）",
    "day": "天（每天X点）",
    "week": "周（每周X，1=周一）",
    "month": "月（每月X号）",
}

# 传感器类型 - 更新版
SENSOR_TYPES = {
    # === 高价值 ===
    "arrears": {
        "name": "欠费金额",
        "unit": "¥",
        "icon": "mdi:cash",
    },
    "account_balance": {
        "name": "燃气账户余额",
        "unit": "¥",
        "icon": "mdi:wallet",
    },
    "last_pay_time": {
        "name": "最近缴费时间",
        "icon": "mdi:clock-outline",
    },
    "last_pay_amount": {
        "name": "最近缴费金额",
        "unit": "¥",
        "icon": "mdi:cash-multiple",
    },
    "annual_pay_count": {
        "name": "年度缴费次数",
        "icon": "mdi:counter",
    },
    "this_read": {
        "name": "本期表读数",
        "unit": "m³",
        "icon": "mdi:gauge",
    },
    "this_read_time": {
        "name": "本期抄表时间",
        "icon": "mdi:calendar-check",
    },
    "step1_gas_used": {
        "name": "一档用气量",
        "unit": "m³",
        "icon": "mdi:stairs-up",
    },
    "step2_gas_used": {
        "name": "二档用气量",
        "unit": "m³",
        "icon": "mdi:stairs-up",
    },
    "this_gas_used": {
        "name": "本期用气量",
        "unit": "m³",
        "icon": "mdi:fire",
    },
    "bill_amount": {
        "name": "账单金额",
        "unit": "¥",
        "icon": "mdi:receipt",
    },
    "step1_remain": {
        "name": "一档剩余气量",
        "unit": "m³",
        "icon": "mdi:tank",
    },
    "step2_remain": {
        "name": "二档剩余气量",
        "unit": "m³",
        "icon": "mdi:tank",
    },
    "penalty_amount": {
        "name": "违约金",
        "unit": "¥",
        "icon": "mdi:alert-circle",
    },
    # === 新增：状态传感器 ===
    "integration_status": {
        "name": "集成状态",
        "icon": "mdi:checkbox-marked-circle",
    },
    # === 新增：月累计传感器 ===
    "monthly_gas_used": {
        "name": "本月累计用气量",
        "unit": "m³",
        "icon": "mdi:calendar-month",
    },
    # === 中等价值 ===
    "cons_addr": {
        "name": "用气地址",
        "icon": "mdi:home-map-marker",
    },
    "org_name": {
        "name": "燃气公司",
        "icon": "mdi:domain",
    },
    "gas_nature": {
        "name": "燃气类型",
        "icon": "mdi:gas-cylinder",
    },
    "purchase_style": {
        "name": "购气方式",
        "icon": "mdi:cart",
    },
    "last_month_gas": {
        "name": "上月用气量",
        "unit": "m³",
        "icon": "mdi:chart-bar",
    },
    "year_avg_gas": {
        "name": "年度月均用气量",
        "unit": "m³",
        "icon": "mdi:chart-line-variant",
    },
}

# 集成状态定义
INTEGRATION_STATUS = {
    "normal": "正常",
    "token_expired": "密钥过期",
    "network_error": "网络异常",
    "config_error": "配置错误",
    "api_error": "API错误",
}

# Token有效期
from datetime import timedelta

TOKEN_REFRESH_INTERVAL = timedelta(hours=1)
TOKEN_EXPIRE_THRESHOLD = timedelta(minutes=5)
DEFAULT_SCAN_INTERVAL = timedelta(hours=1)

# 历史数据存储配置
HISTORY_STORAGE_VERSION = 1
HISTORY_RETENTION_MONTHS = 24


