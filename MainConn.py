'''
    from terminal, run:
    python MainConn.py ticker1,ticker2,...,tickern root_folder
'''
from MyUtil import check_ticker_folders, get_time_now, get_tickers_from_file
from Robinhood import Robinhood
from datetime import datetime
import dateutil.parser
import time
import os.path as path
import pytz
import sys
import json

import pandas as pd
import math

my_trader = Robinhood()
AMD, BABA, BYND, TQQQ, TECL, ZM = 'AMD', 'BABA', 'BYND', 'TQQQ', 'TECL', 'ZM'


def login():
	logged_in = my_trader.login(username="", password="", qr_code='')
	print('Logged in')


login()

# stock_instrument = my_trader.instruments("GEVO")[0]
# quote = my_trader.quote_data('TQQQ')

tz = pytz.timezone("US/Eastern")


def quote2csv(quote):
	symbol = quote['symbol']
	update_time = get_time_now()
	if symbol == 'BTCUSD':
		fields = ('ask_price', 'bid_price', 'mark_price', 'high_price', 'low_price', 'volume')
	else:
		# update_time = dateutil.parser.parse(quote['updated_at']).astimezone(tz)
		fields = ('ask_price', 'ask_size', 'bid_price', 'bid_size', 'last_trade_price')

	seconds_since_midnight = (
			update_time - update_time.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()

	csv_str = str(round(seconds_since_midnight))
	for f in fields:
		if isinstance(quote[f], int):
			csv_str += ',' + str(quote[f])
		else:
			csv_str += ',' + quote[f]

	return csv_str, update_time

def cancel_ticker_order(ticker, require_confirm=True):
	orders = list_open_orders()
	orders = orders[orders.ticker == ticker]
	if require_confirm:
		confirm = input('Confirm cancelling {} orders for ticker {}:'.format(len(orders), ticker))
	else:
		confirm = 'yes'

	if confirm == 'yes':
		for i in range(len(orders)):
			my_trader.cancel_order(orders['id'].iloc[i])

def list_open_orders(do_print=False):
	orders = my_trader.order_history()['results']
	order_list = []
	fields_to_store_string = ['id', 'state', 'trigger', 'type', 'side', 'instrument']
	fields_to_store_num = ['price', 'quantity', 'stop_price']
	for order in orders:
		if order['state'] not in ['filled', 'cancelled', 'rejected']:
			this_instrument_symbol = get_ticker_from_instrument(url=order['instrument'])
			this_list = [this_instrument_symbol] + [order[key] for key in fields_to_store_string]
			this_list += [float(order[key]) if order[key] else None for key in fields_to_store_num]

			order_list.append(this_list)

	order_df = pd.DataFrame(order_list, columns=['ticker'] + fields_to_store_string+fields_to_store_num)
	if do_print:
		print(order_df.loc[:, ['ticker', 'side', 'trigger', 'stop_price']])

	return order_df


def get_ticker_from_instrument(id=None, url=None):
	if url is None:
		url = 'https://api.robinhood.com/instruments/{}/'.format(id)
	return my_trader.get_url(url)['symbol']


def get_holding_info(ticker):
	current_price = float(my_trader.quote_data(ticker)['last_trade_price'])

	instrument_id = my_trader.instruments(ticker)[0]['id']
	securities_owned = my_trader.securities_owned()['results']
	securities_owned_ids = [s['instrument'].split('/')[-2] for s in securities_owned]
	if instrument_id in securities_owned_ids:
		id = securities_owned_ids.index(instrument_id)
		quantity = int(float(securities_owned[id]['quantity']))
		buy_price = float(securities_owned[id]['average_buy_price'])

	else:
		quantity, buy_price = 0, 0

	print('Get holding info: ticker: {}, quantity: {}, buy: {}, current: {}, profit: {}'.format(ticker, quantity, buy_price, current_price,
																  (current_price - buy_price) * quantity))
	return quantity, buy_price

def buy_with_target_profit(ticker, total, target):
	order_info = buy_ticker(ticker, amount=total)


def limit_buy(ticker, price, total):
	quantity = math.floor(total/price)

	instrument = my_trader.instruments(ticker)[0]
	status = my_trader.place_limit_buy_order(instrument_URL=instrument['url'], symbol=ticker, time_in_force='GFD',
											  price=price, quantity=quantity)
	return status


def limit_sell(ticker, price=None, profit=None):
	quantity, buy_price = get_holding_info(ticker)
	if profit is not None:
		sell_price = round(profit / quantity + buy_price, 2)
	else:
		sell_price = price

	instrument = my_trader.instruments(ticker)[0]
	status = my_trader.place_limit_sell_order(instrument_URL=instrument['url'], symbol=ticker, time_in_force='GFD',
											  price=sell_price, quantity=quantity)
	return status


def stop_loss(ticker, price=None, margin=.01, quantity = None):
	if price is None:
		current_price = float(my_trader.quote_data(ticker)['last_trade_price'])
		price = round(current_price * (1-margin), 2)

	if quantity is None:
		quantity = get_holding_info(ticker)[0]

	status = my_trader.place_stop_loss_sell_order(instrument_URL=my_trader.instruments(ticker)[0]['url'], symbol=ticker, time_in_force='GFD',
										 stop_price=price, quantity=quantity)
	return status


def download_tickers(tickers, interval=1, root_folder='price_history2', get_tickers_from_file=False):
	print('Start to download tickers %s at %s with interval %d' % (tickers, get_time_now(), interval))

	check_ticker_folders(tickers, root_folder)

	last_time = get_time_now()
	last_last_trade_price = [0] * len(tickers)
	last_hour = -1
	while True:
		time_now = get_time_now()

		this_hour = time_now.hour
		if this_hour != last_hour:
			print('Alive signal for ticker %s' % tickers)
			last_hour = this_hour

		# bypass night time if no bitcoin
		if 'BTCUSD' not in tickers:
			if this_hour >= 18 or this_hour < 9:
				# pass
				time.sleep(60)
				continue

			if get_tickers_from_file:
				tickers_new = get_tickers_from_file()
				if tickers_new is not None and tickers_new != tickers:
					tickers = tickers_new
					check_ticker_folders(tickers, root_folder)
					last_last_trade_price = [0] * len(tickers)

			quotes = my_trader.quotes_data(tickers)
			last_price_field = 'last_trade_price'
		else:
			quotes = [my_trader.quote_data('BTCUSD')]
			tickers = ['BTCUSD']
			last_price_field = 'ask_price'

		for i, ticker in enumerate(tickers):
			quote = quotes[i]
			csv_str, this_time = quote2csv(quote)

			today_str = datetime.strftime(this_time, '%Y%m%d')
			today_file = path.join(root_folder, ticker, today_str + '.csv')

			if this_time != last_time and float(quote[last_price_field]) != last_last_trade_price[i]:
				# print(csv_str)
				with open(today_file, 'a+') as f:
					f.write(csv_str + '\r\n')

				last_time = this_time
				last_last_trade_price[i] = float(quote[last_price_field])

		time.sleep(interval)


def get_order_status_content(order_status):
	"""
	Extract the content of returned order status and make to json format
	:param order_status:
	:return:
	"""
	if order_status is not None:
		return json.loads(order_status.content.decode())
	else:
		return None


def buy_ticker(ticker, amount=1, n_shares=None, need_confirm=False, tolerance=.1):
	"""

	:param ticker:
	:param amount: total amount you want to pay. Will find the number of shares closest to this amount while not exceeding it
	:param n_shares: only used when amount is None
	:return:
	"""
	stock_instrument = my_trader.instrument(ticker)
	quote = my_trader.get_quote(ticker)
	last_trade_price = float(quote['last_trade_price'])

	if amount == None and n_shares == None:
		raise Exception('Amout and n_shares cannot be both None')
	elif amount is not None:
		n_shares = math.ceil(amount / last_trade_price)
		n_shares = n_shares if n_shares != 0 else 1

	df = pd.DataFrame({
		'shares to buy': n_shares,
		'price': last_trade_price,
		'total pay': last_trade_price * n_shares
	}, index=[0])
	print(df)

	if need_confirm:
		confirm = input('Confirm BUY {} for {}?'.format(n_shares, ticker))
	else:
		confirm = 'yes'

	if confirm == 'yes':
		status = my_trader.place_buy_order(stock_instrument, n_shares,
										   ask_price='{:.02f}'.format(last_trade_price * (1 + tolerance)))
	else:
		raise Exception('User cancel')

	order_status = get_order_status_content(status)

	buy_history = my_trader.buy_history.get(ticker)
	buy_history = buy_history if buy_history is not None else []
	buy_history.append(order_status)
	# TODO limit buy/sell history length
	my_trader.buy_history[ticker] = buy_history

	return order_status


def sell_ticker_quick(ticker, amount='all', skip_confirm=True):
	stock_instrument = my_trader.instrument(ticker)
	instrument_id = stock_instrument['id']

	# find this instrument id in my positions
	all_tickers_owned = my_trader.securities_owned()['results']
	found = False
	for ticker_owned in all_tickers_owned:
		this_id = ticker_owned['instrument'].split('/')[-2]
		if this_id == instrument_id:
			found = True
			break

	if not found:
		raise Exception('Could not find ticker in my portforlio')
	else:
		buy_price = float(ticker_owned['average_buy_price'])
		quantity = float(ticker_owned['quantity'])
		quote = my_trader.get_quote(ticker)
		sell_price = float(quote['last_trade_price'])

		if amount == 'all':
			amount = quantity
		elif amount > quantity:
			raise Exception('amount {} is bigger than total quantity {}.'.format(amount, quantity))

		df = pd.DataFrame({
			'total shares': quantity,
			'shares to sell': amount,
			'buy price': buy_price,
			'sell price': sell_price,
			'cash': amount * sell_price,
			'profit': (sell_price - buy_price) * amount
		}, index=[0])
		print(df)

		if not skip_confirm:
			confirm = input('Confirm SELL {} for {}?'.format(amount, ticker))
		else:
			confirm = 'yes'

		if confirm == 'yes':
			status = my_trader.place_sell_order(stock_instrument, amount, bid_price='{:.02f}'.format(sell_price * .95))
		else:
			raise Exception('User cancel')

	order_status = get_order_status_content(status)

	sell_history = my_trader.sell_hsitory.get(ticker)
	sell_history = sell_history if sell_history is not None else []
	sell_history.append(order_status)
	my_trader.sell_hsitory[ticker] = sell_history

	return order_status


if __name__ == '__main__':

	# if called by download script
	if len(sys.argv) > 1:
		tickers = sys.argv[1].split(',')
		if len(sys.argv) > 2:
			root_folder = sys.argv[2]
		else:
			root_folder = 'price_history2'

		if len(sys.argv) > 3:
			interval_sec = int(sys.argv[3])
		else:
			interval_sec = 5

		download_tickers(tickers, root_folder=root_folder, interval=interval_sec)
