Introduction
============

Early days of this API. Plan is to use this for home assistant. So far basic device data comes back including online.   The library of cards is also populated.  Next up I need to figure out MQTT to enable the useful items.

To run this code for test I am doing::

    from pathlib import Path
    import logging
    import sys
    import os

    path_root = r"C:path to files GitHub\main\yoto_api"
    sys.path.append(str(path_root))
    from yoto_api import *

    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s %(name)s %(levelname)s:%(message)s')
    logger = logging.getLogger(__name__)

    ym = YotoManager(username="username", password="password")
    ym.check_and_refresh_token()
    ym.update_player_status()
    print (ym.players)
    ym.connect_to_events()
    # Pauses the first player
    ym.pause_player(next(iter(ym.players)))
    # Sleep will let the terminal show events coming back. For dev today.
    time.sleep(60)
