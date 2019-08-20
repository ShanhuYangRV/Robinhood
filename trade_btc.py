from Robinhood import Robinhood
import json
import sys
import time
from datetime import datetime
from os import path, remove

quantity = .01


def login():
    trader.login(username="", password="", qr_code='')


def get_order_status(order_info):
    order_id = json.loads(order_info._content.decode())['id']

    status_raw = trader.order_status_bitcoin(order_id)
    status = json.loads(status_raw.content.decode())
    print('Status: %s, at $%s' % (
        status['state'], status['executions'][0]['effective_price'] if status['state'] == 'filled' else 'NA'))
    return status


def buy_bitcoin(quantity=quantity, margin=.005):
    quote_info = trader.quote_data('BTCUSD')
    actual_ask_price = round(float(quote_info['mark_price']) * (1 + margin), 2)

    print('BUY %f- Mark price: %s, ask price: %s, bid price: %s, actual ask price: %f' % (quantity,
        quote_info['mark_price'], quote_info['ask_price'], quote_info['bid_price'], actual_ask_price))
    order_info = trader.trade_bitcoin('BTCUSD',
                                      price=actual_ask_price,
                                      quantity=str(quantity),  # "0.001",
                                      side="buy",
                                      time_in_force="gtc",
                                      type="market")

    return order_info


def sell_bitcoin(quantity=quantity, margin=.005):
    quote_info = trader.quote_data('BTCUSD')
    actual_bid_price = round(float(quote_info['mark_price']) * (1 - margin), 2)
    print('SELL %f - Mark price: %s, ask price: %s, bid price: %s, actual bid price: %f' % (quantity,
        quote_info['mark_price'], quote_info['ask_price'], quote_info['bid_price'], actual_bid_price))
    order_info = trader.trade_bitcoin('BTCUSD',
                                      price=actual_bid_price,
                                      quantity=str(quantity),  # "0.001",
                                      side="sell",
                                      time_in_force="gtc",
                                      type="market")

    return order_info


trader = Robinhood()
login()


# quote_info = my_trader.quote_data('BTCUSD')
# order_info = my_trader.trade_bitcoin('BTCUSD',
#                                      price=round(float(quote_info['mark_price']) * 1.005, 2),
#                                      quantity="0.001",
#                                      side="buy",
#                                      time_in_force="gtc",
#                                      type="market")

# order_info = my_trader.trade_bitcoin('BTCUSD',
#                                      price=round(float(quote_info['mark_price']) * .9, 2),
#                                      quantity="0.001",
#                                      side="sell",
#                                      time_in_force="gtc",
#                                      type="market")

def auto_trade(quantity, type, n_try=3):
    """
    Make sure to sell the quantity. Otherwise it will stuck in the following loop
    :param quantity: for sell, if set to 0, sell all
    :return:
    """
    error_count = 0
    while True:
        try:
            hold_quantity = get_holding_quantity()[0]
            if type == 'sell':
                if hold_quantity > 0:
                    sell_quantity = quantity if quantity > 0 else hold_quantity
                    order_info = sell_bitcoin(quantity=sell_quantity)
                else:
                    print('No bitcoin to sell. Exit auto sell.')
                    break
            else:
                if hold_quantity > 0:
                    print('Bitcoin already bought. Exit auto buy.')
                    break

                order_info = buy_bitcoin(quantity=quantity)
        except:
            print('{}: {} failed, try again'.format(datetime.now(), type))
            error_count += 1
            if error_count > n_try:
                print('Too many failed tries. Break.')
                break

            time.sleep(1)
            continue

        # after a few seconds, check the order status
        time.sleep(3)
        status = get_order_status(order_info)

        # if it's not filled, cancel it and try again
        if status['state'] != 'filled':
            print('{}: order not filled. attempt to cancel order.'.format(datetime.now()))
            trader.session.post(status['cancel_url'])
            continue

        # if it reaches here, it means that the sell is done
        print('{}: {} success.'.format(datetime.now(), type))
        return True

def get_holding_quantity():
    h = trader.get_url(trader.ENDPOINTS['holdings'])['results'][0]
    quantity = float(h['quantity'])
    total_cost = float(h['cost_bases'][0]['direct_cost_basis'])
    return quantity, total_cost/quantity

buy_lock_file = 'buy_lock_file.lock'
def check_buy_lock():
    if path.isfile(buy_lock_file):
        return True
    else:
        return False

def add_buy_lock():
    open(buy_lock_file, 'w+')

def remove_buy_lock():
    if path.isfile(buy_lock_file):
        remove(buy_lock_file)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        quantity_to_buy = float(sys.argv[1])
        sell_below_delta = float(sys.argv[2])
        sell_above_value = float(sys.argv[3])
        buy_below_value = float(sys.argv[4])

        print('Monitoring BTCUSD')

        last_alive_hour = -1
        action_filled = False
        while True:
            if action_filled:
                break

            quote = trader.quote_data('BTCUSD')
            mark_price, bid_price, ask_price = float(quote['mark_price']), float(quote['bid_price']), float(
                quote['ask_price'])

            now = datetime.now()
            if now.hour != last_alive_hour:
                print('{}: Alive, mark_price: {}'.format(datetime.now(), mark_price))
                last_alive_hour = now.hour

            # raise Exception('Test error')

            # handle actions
            quantity, per_cost = get_holding_quantity()
            if quantity == 0 and check_buy_lock():
                print('No BTC hold and buy lock activated. Quit.')
                break

            if quantity > 0 and sell_below_delta > 0 and bid_price <= per_cost - sell_below_delta:
                print('sell below')
                auto_trade(0, 'sell')

            if quantity > 0 and sell_above_value >0 and bid_price >= sell_above_value:
                print('sell above')
                auto_trade(0, 'sell')

            if quantity == 0 and buy_below_value > 0 and ask_price <= buy_below_value and not check_buy_lock():
                print('buy below')
                result = auto_trade(quantity_to_buy, 'buy')

                if result is not None and result:
                    add_buy_lock()


            time.sleep(5)
