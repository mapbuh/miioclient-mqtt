import logging
import paho.mqtt.client as paho


class Mqtt(paho.Client):

    prefix = 'x/y'

    def subscribe(self, topic, qos=0):
        topic = self.prefix + topic.lstrip('/')
        logging.debug("MQTT Subscribe topic: " + topic)
        return super().subscribe(topic, qos)

    def publish(self, topic, payload):
        topic = self.prefix + topic.lstrip('/')
        logging.debug("MQTT Publish topic: " + topic + " payload: " + payload)
        return super().publish(topic, payload)

    def set_prefix(self, prefix):
        self.prefix = prefix.rstrip('/') + '/'
