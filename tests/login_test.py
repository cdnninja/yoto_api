from pathlib import Path
import logging
import sys
import os

path_root = r"C:\Users\jayde\OneDrive\Documents\GitHub\main\yoto_api\yoto_api"
sys.path.append(str(path_root))

from yoto_api import *

def login():
    username = os.environ["USERNAME"]
    password = os.environ["PASSWORD"]
    yotomanager = YotoManager(username=username, password=password)
    assert yotomanager
