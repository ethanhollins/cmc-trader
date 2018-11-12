from CMCTrader import Constants
from enum import Enum
import datetime

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD],
	'INDIVIDUAL' : None,
	'risk' : 1.0,
	'PLAN' : None,
	'stoprange' : 17,
	'breakeven_point' : 34,
	'full_profit' : 200,
	'rounding' : 100,
	'breakeven_min_pips' : 2,
	'CLOSING SEQUENCE' : None,
	'no_more_trades_in_profit' : '15:00',
	'no_more_trades' : '15:30',
	'set_breakeven' : '15:50',
	'NEWS' : None,
	'time_threshold_breakeven' : 1,
	'time_threshold_no_trades' : 5.
	'RSI' : None,
	'rsi_overbought' : 75,
	'rsi_oversold' : 25,
	'rsi_threshold' : 50,
	'CCI' : None,
	'cci_threshold' : 0
}

utils = None

reg_sar = None
slow_sar = None
black_sar = None
cci = None

def init(utilities):
	global utils
	global reg_sar, slow_sar, black_sar, cci

	utils = utilities
	reg_sar = utils.SAR(1)
	black_sar = utils.SAR(2)
	slow_sar = utils.SAR(3)
	cci = utils.CCI(4, 1)

def backtest():
	