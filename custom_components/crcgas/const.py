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

# 传感器类型
SENSOR_TYPES = {
    "arrears": {
        "name": "欠费金额",
        "unit": "¥",
        "icon": "mdi:cash",
    },
    "last_bill_amount": {
        "name": "上期账单金额",
        "unit": "¥",
        "icon": "mdi:receipt",
    },
    "last_bill_gas": {
        "name": "上期用气量",
        "unit": "m³",
        "icon": "mdi:gas-cylinder",
    },
    "last_mr_date": {
        "name": "最近抄表日期",
        "icon": "mdi:calendar",
    },
    "total_consumption": {
        "name": "年度累计用气量",
        "unit": "m³",
        "icon": "mdi:chart-line",
    },
}

# 更新间隔（动态调整）
from datetime import timedelta
INITIAL_SCAN_INTERVAL = timedelta(minutes=30)  # 初始30分钟
MIN_SCAN_INTERVAL = timedelta(minutes=5)       # 最小5分钟
MAX_SCAN_INTERVAL = timedelta(minutes=60)       # 最大60分钟
INTERVAL_STEP = timedelta(minutes=10)          # 调整步长10分钟
SCAN_INTERVAL = INITIAL_SCAN_INTERVAL
