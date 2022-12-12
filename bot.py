#!/usr/bin/python3

import datetime
import openai
import re
import sys
import threading
import time
import traceback

from irc import *
from conf import config

irc = IRC()
irc.connect()

botnick = config.get('irc', 'nick')
openai.api_key = config.get('openai_api_key')

count_since_response = 100
last_response_time = int(time.time())

message_history = {}

def generate_reply(prompt):
    timestamp_str = timestamp()
    prompt += f"[{botnick}] ({timestamp_str})"

    print(f"Getting response to prompt: {prompt}")
    try:
        response = openai.Completion.create(
          model=config.get('model') or "text-davinci-003",
          prompt=prompt,
          temperature=0.7,
          max_tokens=config.get('max_tokens') or 64,
          top_p=1,
          frequency_penalty=0,
          presence_penalty=0,
          stop=[],
        )
        print(response)
        text = response['choices'][0]['text']
        return text.strip()
    except openai.error.APIError as error:
        traceback.print_exc()
        return str(error)
    except Exception as exc:
        traceback.print_exc()
        return str(exc)

def timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S")

def message_handler(username, channel, message, full_user):
    if message.startswith(config.get('command_key')) and full_user == config.get('admin'):
        return

    if channel == botnick:
        channel = username

    global message_history
    if channel not in message_history:
        message_history[channel] = ""

    timestamp_str = timestamp()
    message_history[channel] += f"[{username}] ({timestamp_str}) {message}\n"
    history_to_keep = config.get('history_to_keep') or 500
    message_history[channel] = message_history[channel][-1 * history_to_keep:]

    global count_since_response
    if not should_respond(message, channel, username):
        count_since_response += 1
        return

    reply = generate_reply(message_history[channel])
    if reply is None:
        return

    lines = reply.split('\n')
    for line in lines:
        if line:
            irc.send_to_channel(channel, line)
            message_history[channel] += f"[{botnick}] ({timestamp_str}) {line}\n"

    count_since_response = 0
    last_response_time = int(time.time())


def should_respond(message, channel, username):
    if botnick.upper() in message.upper():
        return True

    if channel == username:
        # DM
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
    if channel == botnick:
        channel = username

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
            if message is not None:
                lines = message.split("\n")
                timestamp_str = timestamp()
                for line in lines:
                    irc.send_to_channel(channel, line)
                    message_history[channel] += f"[{botnick}] ({timestamp_str}) {line}\n"

                history_to_keep = config.get('history_to_keep') or 500
                message_history[channel] = message_history[channel][-1 * history_to_keep:]

        count_since_response = 0
        last_response_time = int(time.time())

irc.add_message_handler(message_handler)
irc.add_message_handler(admin_commands)

random_message_thread = threading.Thread(target=try_random_message)
random_message_thread.start()
