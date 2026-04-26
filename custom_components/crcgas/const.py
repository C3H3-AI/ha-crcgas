"""华润燃气 HA集成常量定义"""

from homeassistant.const import Platform

# 平台
DOMAIN = "crcgas"
PLATFORM_NAME = "华润燃气"  # 集成显示名称
PLATFORMS = [Platform.SENSOR]

# API配置
BASE_URL = "https://wmp-svc.crcgas.com/wmp-wechat-rest"

# API端点
API_GET_LOGIN_INFO = "/public/mp/getMpLoginInfo"
API_GET_BINDING_CONS = "/binding/getMpBindingCons"  # 修正：抓包确认路径
API_GET_GAS_BILL_LIST = "/bill/getGasBillList"
API_GET_BILL_DETAIL = "/bill/getBillDetail"
API_QUERY_ARREARS = "/mp/pay/queryArrears"
API_GET_BO_TOKEN = "/public/mp/getBoToken4Mp"
API_DO_REFRESH_TOKEN = "/public/doRefreshToken"  # GET请求，非POST
API_QUERY_PAY_HISTORY = "/mp/pay/queryPayHistory"  # 缴费历史

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
CONF_SCAN_INTERVAL = "scan_interval"  # 数据更新间隔（小时）

# 传感器类型
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

# Token有效期（bo-token约3小时，refresh-token约4.5小时）
from datetime import timedelta
TOKEN_REFRESH_INTERVAL = timedelta(hours=1)    # Token刷新间隔（与小程序一致）
TOKEN_EXPIRE_THRESHOLD = timedelta(minutes=5)   # 剩余时间少于5分钟时强制刷新
DEFAULT_SCAN_INTERVAL = timedelta(hours=1)     # 默认数据更新间隔
SCAN_INTERVAL_OPTIONS = [
    (1, "1小时"),
    (2, "2小时"),
    (3, "3小时"),
    (6, "6小时"),
    (12, "12小时"),
    (24, "24小时"),
]
