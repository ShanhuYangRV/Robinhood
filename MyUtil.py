import os

import numpy as np
from datetime import datetime
import pytz
import sys
from dateutil.tz import tzlocal
from os import path, path as path

tz = pytz.timezone("US/Eastern")


def moving_average_with_padding(a, n=3):
    """
    pad the beginning with n values that are same to the first value of the series, so that we do not have nan values
    based on https://stackoverflow.com/questions/14313510/how-to-calculate-moving-average-using-numpy
    :param a:
    :param n:
    :return:
    """
    a = np.array(a)
    a = np.concatenate([np.array([a[0]] * (n - 1)), a])
    ret = np.cumsum(a, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    return ret[n - 1:] / n


def get_time_now():
    """
    :return: Time in Eastern time, no matter where this computer is
    """
    return datetime.now(tzlocal()).astimezone(tz)

ticker_file = 'cfg/ticker_list.txt'
def get_tickers_from_file():
    if path.isfile(ticker_file):
        with open(ticker_file, 'r') as f:
            return list(set(f.read().split(',')))

    return None

def update_tickers_in_file(tickers):
    with open(ticker_file, 'w+') as f:
        f.write(','.join(tickers))




def check_ticker_folders(tickers, root_folder):
    """
    check if ticker subfolder exists, create if not
    :param tickers:
    :param root_folder:
    :return:
    """
    for ticker in tickers:
        folder = path.join(root_folder, ticker)
        if not path.isdir(folder):
            os.makedirs(folder)
