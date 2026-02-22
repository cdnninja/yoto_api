Introduction
============

This is a Python wrapper for the Yoto API.  It allows you to interact with the Yoto API to control your Yoto players, update your library, and get information about your players and cards.

You need a client ID to use this API.  You can get this from here: https://yoto.dev/get-started/start-here/.

Credit
======

A big thank you to @buzzeddesign for helping to sniff some of the API and make sense of it.  Thank you to @fuatakgun for creating the core architecture which is based on kia_uvo.

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

    ym = YotoManager(client_id="clientID")
    print(ym.device_code_flow_start())
    #complete the link, present to user
    time.sleep(15)
    ym.device_code_flow_complete()
    ym.update_player_status()
    print (ym.players)
    ym.connect_to_events()
    # Pauses the first player
    ym.pause_player(next(iter(ym.players)))
    # Sleep will let the terminal show events coming back. For dev today.
    time.sleep(60)

    # If you have already linked save the token.
    refresh_token = ym.token.refresh_token

    instead of device code flow user:
    ym.set_refresh_token(refresh_token)
    #Refresh token - maybe it is old. Auto run by set refresh token
    ym.check_and_refresh_token()

Usage
=====

For additional methods not mentioned below follow the file here for all functionality:
https://github.com/cdnninja/yoto_api/blob/master/yoto_api/YotoManager.py

To use this API you need to create a YotoManager object with your client ID.  You can get this from the Yoto app.  It is in the URL when you log in.  It is the long string after "client_id=".

    ym = YotoManager(client_id="your_client_id")

Start the device code flow.  This will return a dictionary with the device code and other information.  You will need to present this to the user to complete the login. ::

    ym.device_code_flow_start()

Complete the device code flow.  This will poll the API for the token.  You will need to wait a few seconds before calling this after presenting the device code to the user. ::
    ym.device_code_flow_complete()

If you have a token already you can set it directly.  This is useful if you have already logged in and want to use the API without going through the device code flow again. ::

    ym.set_token(token: Token)


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

Contains player object with data values you can access. ::

    ym.players

Contains the library of cards.  Each card being an object with the data values you can use. ::

    ym.library

Get Set Up For Development
==========================

Set up pyenv::

    pyenv install

Install the dependencies::

    pip install -r requirements.txt
    pip install -r requirements_dev.txt

Tests
=====

Create a .env file in the root of the project with the following content::

    YOTO_USERNAME=your_username
    YOTO_PASSWORD=your_password

Run the tests with::

        python -m pytest

Other Notes
===========

This is not associated or affiliated with yoto play in any way.
