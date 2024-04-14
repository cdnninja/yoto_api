""""""

import os

from yoto_api.YotoManager import YotoManager


def login():
    username = os.environ["CDNINJA_USERNAME"]
    password = os.environ["CDNINJA_PASSWORD"]
    yotomanager = YotoManager(username=username, password=password)
    assert yotomanager
