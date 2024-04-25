Introduction
============

Early days of this API. Plan is to use this for home assistant. So far basic device data comes back including online.   The library of cards is also populated.  Pause command functions.  Not other commands work yet.

Credit
======

A big thank you to @buzzeddesign for helping to sniff some of the API and make sense of it.  Thank you to @fuatakgun for creating to core architecture is based on over in kia_uvo

Example Test Code
=================
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

Usage
=====
Check and refresh token will pull the first set of data.   It also should be run regularly if you keep your code running for days.  It will check if the token is valid.  If it isn't it will refresh the token.  If this is first run of the command and no data has been pulled it will also run update_player_status() and update_cards() for you. ::

    ym.check_and_refresh_token()

Check and refresh token will pull the first set of data.   It also should be run regularly if you keep your code running for days.  It will check if the token is valid.  If it isn't it will refresh the token.  If this is first run of the command and no data has been pulled it will also run update_player_status() and update_cards() for you. ::

    ym.update_player_status()

Connects to the MQTT broker.  This must be run before any command and also get get useful data. ::

    ym.connect_to_events()

Pauses the player for the player ID sent. ID can be found in ym.players.keys() ::

    ym.pause_player(player_id: str)

Updates the library of cards.   This is done as part of check_refresh_token so only needed if data is stale. ::

    ym.update_cards()

Contains player object will data values you can access. ::

    ym.players

Contains the library of cards.  Each card being an object with the data values you can use. ::

    ym.library

Other Notes
===========

This is not associated or affiliated with yoto play in any way.
