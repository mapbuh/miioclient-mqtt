import time
import logging
import json


class Miio:

    def __init__(self, mqtt):
        self.miio_id = 0
        self.last_pong = 0
        self.mqtt = mqtt

    def recent_pong(self):
        if (time.time() - self.last_pong) > 300:
            return False
        else:
            return True

    def msg_encode(self, data):
        if data.get("method") and data.get("method") == "internal.PING":
            msg = data
        else:
            if self.miio_id != 12345:
                self.miio_id = self.miio_id + 1
            else:
                self.miio_id = self.miio_id + 2
            if self.miio_id > 999999999:
                self.miio_id = 1
            msg = {"id": self.miio_id}
            msg.update(data)
        return (json.dumps(msg)).encode()

    def msg_decode(self, data):
        logging.debug("Received: " + data.decode())
        if data[-1] == 0:
            data = data[:-1]
        res = [{""}]
        try:
            fixed_str = data.decode().replace('}{', '},{')
            res = json.loads("[" + fixed_str + "]")
        except:
            logging.warning("Bad JSON received")
        return res

    def msg_params(self, topic, params, states):
        for key, value in params.items():
            if type(value) is not dict:
                if key == "rgb":
                    # response seem to be increased by 1,
                    # unless brightness set to 0
                    states['brightness'], states['light_rgb'] = \
                            divmod(value-1+1, 0x1000000)
                    states['light_rgb'] = \
                        states['light_rgb'] ^ states['brightness']
                    self.mqtt.publish(
                        topic + key + "/state",
                        format(states['light_rgb'], 'x').upper()
                    )
                    self.mqtt.publish(
                        topic + key + "/brightness/state",
                        str(states['brightness']).upper()
                    )
                else:
                    self.mqtt.publish(
                        topic + key + "/state",
                        str(value).upper()
                    )
            else:
                self.msg_params(topic + key + "/", value, states)

    def handle_msg(self, miio_msg, states):
        method = miio_msg.get("method", None)
        topic = miio_msg.get("sid", "internal") + "/"
        params = miio_msg.get("params", None)
        if method is not None:
            if method == "props" and "model" in miio_msg:
                if params is not None:
                    self.msg_params(topic, params, states)
            elif method == "props":
                topic = "internal/"
                if params is not None:
                    self.msg_params(topic, params, states)
            elif method == "_otc.log":
                if params is not None:
                    self.msg_params(topic, params, states)
            if method.find("event.") != -1:
                self.msg_event(topic, method, miio_msg.get("params"))

    def handle_reply(self, topic, miio_msgs, state_update, states):
        while len(miio_msgs) > 0:
            miio_msg = miio_msgs.pop()
            if state_update is True and miio_msg.get("result"):
                result = miio_msg.get("result")[0].upper()
                self.mqtt.publish(topic + "/state", result)    # publish
                if miio_msg.get("method") and \
                        miio_msg.get("method") == "internal.PONG":
                    self.last_pong = time.time()
                    logging.debug("PONG: TS updated")
            else:
                self.handle_msg(miio_msg, states)

    def msg_event(self, topic, event, params):
        value = event[6:]
        if value == "keepalive":
            return
        elif value == "motion":
            value = "on"
        elif value == "no_motion":
            value = "off"
        elif value == "alarm":
            topic = value + "/"
            value = params[0]
            if value == "all_off":
                value = "off"
        elif value == "close":
            value = "closed"
        value = value.upper()
        if len(params) > 0:
            self.mqtt.publish(topic + "params", str(params))
        self.mqtt.publish(topic + "state", str(value))
