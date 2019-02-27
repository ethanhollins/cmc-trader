import datetime

# Pair constants
GBPUSD = 'GBPUSD'
EURUSD = 'EURUSD'
AUDUSD = 'AUDUSD'

# Period Constants
ONE_SECOND = -5
FIVE_SECONDS = -4
TEN_SECONDS = -3
THIRTY_SECONDS = -2
ONE_MINUTE = 0
TWO_MINUTES = 1
THREE_MINUTES = 2
FIVE_MINUTES = 3
TEN_MINUTES = 4
FIFTEEN_MINUTES = 5
THIRTY_MINUTES = 6
ONE_HOUR = 10
TWO_HOURS = 11
THREE_HOURS = 12
FOUR_HOURS = 13
ONE_DAY = 20
ONE_WEEK = 21
ONE_MONTH = 22

# Order type constants
ORDER_TYPE = 'ORDER_TYPE'
MARKET = 'MARKET'
LIMIT = 'LIMIT'
STOP_ENTRY = 'STOP_ENTRY'

# Ticket type constants
T_BUY = 'T_BUY'
T_SELL = 'T_SELL'

# Ticket price constants
PRICE_BUY = 'PRICE_BUY'
PRICE_SELL = 'PRICE_SELL'
SPREAD = 'SPREAD'

# Datetime start date
DT_START_DATE = datetime.datetime(year = 2018, month = 1, day = 1)

# Bar read X position
# READ_X = 1070 # zoom: 1
READ_X = 304 # zoom: 1.025
# READ_X_2 = 1350 # zoom: 1.05

# Collection Type
PIXEL_COLLECT = 0
DATA_POINT_COLLECT = 1

# Colours
BLACK = [0, 0, 0, 255]
WHITE = [255, 255, 255, 255]
PINK = [255, 0, 255, 255]
PURPLE = [128, 0, 255, 255]