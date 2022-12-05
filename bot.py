#!/usr/bin/python3

import re
import sys
import threading
import time
import traceback

from irc import *
from conf import config

irc = IRC()
irc.connect()

HISTORY_TO_KEEP = 200

botnick = config.get('irc', 'nick')

count_since_response = 100
last_response_time = int(time.time())

message_history = {}

def generate_reply(input):
    return "test"

def message_handler(username, channel, message, full_user):
    global message_history
    if channel not in message_history:
        message_history[channel] = ""
    message_history[channel] += message + "\n"
    message_history[channel] = message_history[channel][-1 * HISTORY_TO_KEEP:]

    global count_since_response
    if not should_respond(message):
        count_since_response += 1
        return

    reply = generate_reply(message_history[channel])
    if botnick.upper() in message.upper():
        reply = username + ": " + reply
    irc.send_to_channel(channel, reply)
    message_history[channel] += reply + "\n"

    count_since_response = 0
    last_response_time = int(time.time())


def should_respond(message):
    if botnick.upper() in message.upper():
        return True

    if config.get('respond_without_prompt'):
        global count_since_response
        if count_since_response < config.get('respond_without_prompt', 'messages_between'):
            # too few messages
            return False

        time_since_last_response = int(time.time()) - last_response_time
        if time_since_last_response < config.get('respond_without_prompt', 'seconds_since_last_response'):
            # last response too recent
            return False
        return True

    return False

def admin_commands(username, channel, message, full_user):
    if full_user != config.get('admin'):
        return

    if not message.startswith(config.get('command_key')):
        return

    parts = message.split(" ")
    command = parts[0][len(config.get('command_key')):]
    args = "".join(parts[1:])

    if command == "join":
        irc.send("JOIN " + args + "\n")

    elif command in ["leave", "part"]:
        to_leave = args if args else channel
        irc.send("PART " + to_leave + "\n")

    elif command == "shutdown":
        irc.stop()

    elif command in ["reload_config", "config", "reloadconfig"]:
        config.load_from_file()
        irc.send_to_channel(channel, username + ": reloaded config.json")
        global random_message_thread
        if random_message_thread and not random_message_thread.is_alive():
            random_message_thread = threading.Thread(target=try_random_message)
            random_message_thread.start()


def try_random_message():
    global last_response_time, count_since_response
    if not config.get('message_randomly_time'):
        return

    while True:
        time.sleep(config.get('message_randomly_time'))
        time_since_last_response = int(time.time()) - last_response_time
        if time_since_last_response < config.get('message_randomly_time'):
            # last message was too recent
            continue

        for channel in config.get('irc', 'channels'):
            if channel not in message_history or len(message_history[channel]) < 10:
                continue
            message = generate_reply(message_history[channel])
            irc.send_to_channel(channel, message)
            message_history[channel] += message + "\n"
            message_history[channel] = message_history[channel][-1 * HISTORY_TO_KEEP:]

        count_since_response = 0
        last_response_time = int(time.time())

irc.add_message_handler(message_handler)
irc.add_message_handler(admin_commands)

random_message_thread = threading.Thread(target=try_random_message)
random_message_thread.start()