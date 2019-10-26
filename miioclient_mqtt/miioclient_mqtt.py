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
    except Exception as inst:
        print(inst.args)


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
    except Exception as inst:
        print(inst.args)


config = read_config()
logging.basicConfig(
    level=config.get('log_level', 'NOTSET'),
    format='%(asctime)s - %(message)s'
)
states = initial_states(config)
mqtt = mqtt_init(config)
miio = Miio(mqtt)
queue = Queue(maxsize=100)

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
        UDPClientSocket.settimeout(1)
#    print("Waiting...")
    try:
        miio_msgs = miio.msg_decode(UDPClientSocket.recvfrom(miio_len_max)[0])
        while len(miio_msgs) > 0:
            miio_msg = miio_msgs.pop()
            miio.handle_msg(miio_msg, states)
    except socket.timeout:
        pass

    if (time.time() - ts_last_ping) > 200:
        queue.put(MiioMsg.ping())
        ts_last_ping = time.time()
    if (not miio.recent_pong()):
        mqtt.publish('internal/state', 'OFFLINE')

# disconnect
mqtt.disconnect()
# stop loop
mqtt.loop_stop()
