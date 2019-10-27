#!/usr/bin/env python3

# (c)2019 RothM - MIIO Client MQTT Dispatcher
# Licensed under GPL v3
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

import time
import socket
import os
import yaml
from multiprocessing import Queue
import logging
from classes.Miio import Miio
from classes.MiioMsg import MiioMsg
from classes.Mqtt import Mqtt

# Constants
miio_len_max = 1480

queue = Queue(maxsize=100)


def read_config():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    with open(script_dir + "/miioclient_mqtt.yaml") as file:
        config = yaml.safe_load(file)
    return config


def initial_states(config):
    return {
        'sound':
            config.get('initial_states', {}).get('sound', 2),
        'sound_volume':
            config.get('initial_states', {}).get('sound_volume', 50),
        'light_rgb':
            int(
                config.get('initial_states', {}).get('light_rgb', 'ffffff'),
                16
            ),
        'doorbell_volume':
            config.get('initial_states', {}).get('doorbell_volume', 25),
        'doorbell_sound':
            config.get('initial_states', {}).get('doorbell_sound', 11),
        'alarm_volume':
            config.get('initial_states', {}).get('alarm_volume', 90),
        'alarm_sound':
            config.get('initial_states', {}).get('alarm_sound', 2),
        'arming_time':
            config.get('initial_states', {}).get('arming_time', 30),
        'alarm_duration':
            config.get('initial_states', {}).get('alarm_duration', 1200),
        'brightness':
            config.get('initial_states', {}).get('brightness', 54),
    }


def queueAppend(queue, item):
    if (item):
        queue.put(item)
        return True
    else:
        return False


def mqtt_connect(client, userdata, flags, rc):
    try:
        logging.debug("MQTT Connected with result code "+str(rc))
        # Subscribe to default MQTT topics for the gateway
        userdata['mqtt'].subscribe("heartbeat")
        userdata['mqtt'].subscribe("alarm")
        userdata['mqtt'].subscribe("alarm/time_to_activate")
        userdata['mqtt'].subscribe("alarm/duration")
        userdata['mqtt'].subscribe("light")
        userdata['mqtt'].subscribe("brightness")
        userdata['mqtt'].subscribe("rgb")
        userdata['mqtt'].subscribe("sound")
        userdata['mqtt'].subscribe("sound/sound")
        userdata['mqtt'].subscribe("sound/volume")
        userdata['mqtt'].subscribe("sound/alarming/volume")
        userdata['mqtt'].subscribe("sound/alarming/sound")
        userdata['mqtt'].subscribe("sound/doorbell/volume")
        userdata['mqtt'].subscribe("sound/doorbell/sound")
        userdata['mqtt'].subscribe('effect/blink')
        userdata['mqtt'].subscribe('effect/slowblink')
    except Exception as inst:
        logging.debug("Exception: " + inst.args)


def mqtt_init(config):
    mqtt = Mqtt()
    mqtt.username_pw_set(
        config.get('mqtt', {}).get('username', ''),
        config.get('mqtt', {}).get('password', '')
    )
    mqtt.on_connect = mqtt_connect
    mqtt.on_message = mqtt_message
    mqtt.connect(config['mqtt']['broker'])
    mqtt.set_prefix(config['mqtt']['prefix'])
    mqtt.user_data_set({'prefix': config['mqtt']['prefix'], 'mqtt': mqtt})
    mqtt.loop_start()
    return mqtt


# MQTT callback
def mqtt_message(client, userdata, message):

    try:
        topic = message.topic[len(userdata['prefix']):]
        payload = message.payload.decode("utf-8")
        logging.debug(
            "MQTT Received topic: " + topic + " payload: " + str(payload)
        )
        command = str(message.payload.decode("utf-8"))
        if topic == "heartbeat":
            queueAppend(queue, MiioMsg.get_arming())
        if topic == "alarm":
            queueAppend(queue, MiioMsg.set_arming(command.lower()))
        if topic == "light":
            queueAppend(queue, MiioMsg.set_light(command.lower()))
        if topic == "brightness":
            if (queueAppend(
                queue,
                MiioMsg.set_rgb(command, states['light_rgb'])
            )):
                states['brightness'] = command
        if topic == "rgb":
            if (queueAppend(
                queue,
                MiioMsg.set_rgb(states['brightness'], int(command, 16))
            )):
                states['light_rgb'] = int(command, 16)
        if topic == "sound/volume":
            if (queueAppend(queue, MiioMsg.set_volume(command))):
                states['sound_volume'] = command
        if topic == "sound":
            if command.lower() == "on":
                queueAppend(
                    queue,
                    MiioMsg.play_sound(states['sound'], states['sound_volume'])
                )
            if command.upper() == "OFF":
                queueAppend(queue, MiioMsg.stop_sound())
        if topic == "sound/sound":
            states['sound'] = int(command)
        if topic == "sound/alarming/volume":
            if (queueAppend(queue, MiioMsg.set_alarm_volume(queue))):
                states['alarm_volume'] = command
        if topic == "sound/alarming/sound":
            if (queueAppend(queue, MiioMsg.set_alarm_sound(command))):
                states['alarm_sound'] = command
        if topic == "sound/doorbell/volume":
            if (queueAppend(queue, MiioMsg.set_doorbell_volume(command))):
                states['doorbell_volume'] = command
        if topic == "sound/doorbell/sound":
            if (queueAppend(queue, MiioMsg.set_doorbell_sound(command))):
                states['doorbell_sound'] = command
        if topic == "effect/blink":
            # color:color:duration
            command_parts = command.split(':', 3)
            # states['effect']['flag'] = 1
            states['effect'] = {}
            states['effect']['type'] = 'blink'
            if int(command_parts[0], 16) > 0xffffff:
                (
                    states['effect']['start_brightness'],
                    states['effect']['start_color']
                ) = divmod(int(command_parts[0], 16), 0x1000000)
            else:
                states['effect']['start_brightness'] = states['brightness']
                states['effect']['start_color'] = int(command_parts[0], 16)
            if int(command_parts[1], 16) > 0xffffff:
                (
                    states['effect']['target_brightness'],
                    states['effect']['target_color']
                ) = divmod(int(command_parts[1], 16), 0x1000000)
            else:
                states['effect']['target_brightness'] = states['brightness']
                states['effect']['target_color'] = int(command_parts[1], 16)
            states['effect']['current_color'] = states['effect']['start_color']
            states['effect']['end_time'] = time.time() + int(command_parts[2])
            states['effect']['active'] = True
            states['effect']['last_iteration'] = time.time()
            queueAppend(queue, MiioMsg.set_light('on'))
            queueAppend(
                queue,
                MiioMsg.set_rgb(
                    states['effect']['start_brightness'],
                    states['effect']['start_color']
                )
            )
        if topic == "effect/slowblink":
            # color:pulse:duration
            command_parts = command.split(':', 3)
            # states['effect']['flag'] = 1
            states['effect'] = {}
            states['effect']['type'] = 'slowblink'
            states['effect']['start_color'] = int('000000', 16)
            states['effect']['target_color'] = int(command_parts[0], 16)
            states['effect']['pulse_time'] = int(command_parts[1])
            states['effect']['pulse_start'] = time.time()
            states['effect']['pulse_end'] = time.time() + int(command_parts[1])
            states['effect']['end_time'] = time.time() + int(command_parts[2])
            states['effect']['last_iteration'] = time.time()
    except Exception as inst:
        logging.debug("Exception: " + inst.args)


def time_to_color(t0, t1, tx, c0, c1):
    if tx >= t1:
        return c1
    else:
        a = (c0 - c1) / (t0 - t1)
        b = c1 - t1 * ((c0 - c1) / (t0 - t1))
        return int(a * tx + b)


def handle_effect():
    if (states.get('effect', {}).get('end_time', 0) < time.time()):
        states['effect']['active'] = False
        queueAppend(queue, MiioMsg.set_light('off'))
        return

    if states['effect']['type'] == 'slowblink':
        slowblink()
    elif states['effect']['type'] == 'blink':
        blink()
    else:
        logging.debug("Unknown effect: " + states['effect']['type'])


def blink():
    if (states['effect']['last_iteration'] + 0.5 > time.time()):
        return
    else:
        states['effect']['last_iteration'] = time.time()
    if states['effect']['current_color'] == states['effect']['start_color']:
        states['light_rgb'] = states['effect']['target_color']
        states['brightness'] = states['effect']['target_brightness']
    else:
        states['light_rgb'] = states['effect']['start_color']
        states['brightness'] = states['effect']['start_brightness']
    states['effect']['current_color'] = states['light_rgb']
    queueAppend(
        queue,
        MiioMsg.set_rgb(states['brightness'], states['light_rgb'])
    )


def slowblink():
    if (states['effect']['last_iteration'] + 0.5 > time.time()):
        return
    else:
        states['effect']['last_iteration'] = time.time()
    tx = time.time()
    cx_red = time_to_color(
            states['effect']['pulse_start'],
            states['effect']['pulse_end'],
            tx,
            states['effect']['start_color'] // 0x10000 % 0x100,
            states['effect']['target_color'] // 0x10000 % 0x100
    )
    cx_green = time_to_color(
            states['effect']['pulse_start'],
            states['effect']['pulse_end'],
            tx,
            states['effect']['start_color'] // 0x100 % 0x100,
            states['effect']['target_color'] // 0x100 % 0x100
    )
    cx_blue = time_to_color(
            states['effect']['pulse_start'],
            states['effect']['pulse_end'],
            tx,
            states['effect']['start_color'] // 1 % 0x100,
            states['effect']['target_color'] // 1 % 0x100
    )
    brightness = time_to_color(
        states['effect']['pulse_start'],
        states['effect']['pulse_end'],
        tx,
        0,
        100
    )

    print(str(cx_red) + "/" + str(cx_green) + "/" + str(cx_blue))
    if tx >= states['effect']['pulse_end']:
        states['effect']['pulse_start'] = time.time()
        states['effect']['pulse_end'] = \
            time.time() + states['effect']['pulse_time']
    cx = cx_red * 0x10000 + cx_green * 0x100 + cx_blue
    print("Effect color: " + format(int(cx), 'x'))
    queueAppend(
        queue,
        MiioMsg.set_rgb(brightness, int(cx))
    )


config = read_config()
logging.basicConfig(
    level=config.get('log_level', 'NOTSET'),
    format='%(asctime)s - %(message)s'
)
states = initial_states(config)
mqtt = mqtt_init(config)
miio = Miio(mqtt)

# Create a UDP socket at client side
UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
UDPClientSocket.settimeout(1)
# Send a PING first
queueAppend(queue, MiioMsg.ping())
ts_last_ping = time.time()
# Is Gateway armed?
queueAppend(queue, MiioMsg.get_arming())
# Set time in seconds after which alarm is really armed
queueAppend(queue, MiioMsg.set_arming_time(states['arming_time']))
if (not config['silent_start']):
    # Set duration of alarm if triggered
    queueAppend(queue, MiioMsg.set_alarm_duration(states['alarm_duration']))
    queueAppend(queue, MiioMsg.set_alarm_volume(states['alarm_volume']))
    queueAppend(queue, MiioMsg.set_alarm_sound(states['alarm_sound']))
    queueAppend(queue, MiioMsg.set_doorbell_volume(states['doorbell_volume']))
    queueAppend(queue, MiioMsg.set_doorbell_sound(states['doorbell_sound']))
    # Turn OFF sound as previous commands will make the gateway play tones
    queueAppend(queue, MiioMsg.stop_sound())
# Set intensity + color
queueAppend(queue, MiioMsg.set_rgb(states['brightness'], states['light_rgb']))

while True:
    while not queue.empty():
        # print("Something in the queue")
        # req : topic , miio_msg
        req = queue.get()
        logging.debug("Sending: " + str(miio.msg_encode(req[1])))
        UDPClientSocket.sendto(
            miio.msg_encode(req[1]),
            (config['miio']['broker'], config['miio']['port'])
        )
        UDPClientSocket.settimeout(2)
        try:
            # Wait for response
            miio.handle_reply(
                req[0],
                miio.msg_decode(UDPClientSocket.recvfrom(miio_len_max)[0]),
                req[2],
                states
            )
        except socket.timeout:
            logging.warning("No reply!")
        UDPClientSocket.settimeout(0.1)
#    print("Waiting...")
    try:
        miio_msgs = miio.msg_decode(UDPClientSocket.recvfrom(miio_len_max)[0])
        while len(miio_msgs) > 0:
            miio_msg = miio_msgs.pop()
            miio.handle_msg(miio_msg, states)
    except socket.timeout:
        pass

    if (states.get('effect', {}).get('active', False)):
        handle_effect()

    if (time.time() - ts_last_ping) > 200:
        queue.put(MiioMsg.ping())
        ts_last_ping = time.time()
    if (not miio.recent_pong()):
        mqtt.publish('internal/state', 'OFFLINE')

# disconnect
mqtt.disconnect()
# stop loop
mqtt.loop_stop()
