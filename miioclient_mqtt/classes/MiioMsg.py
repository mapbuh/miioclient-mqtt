import logging


class MiioMsg:

    def ping():
        return ["broker", {"method": "internal.PING"}, True]

    def set_volume(volume):
        return [
            "sound/volume",
            {
                "method": "set_gateway_volume",
                "params": [int(volume)]
            },
            True
        ]

    def play_sound(sound, volume):
        return [
            "sound",
            {
                "method": "play_music_new",
                "params": [str(sound), int(volume)]
            },
            False
        ]

    def stop_sound():
        return [
            "sound",
            {"method": "set_sound_playing", "params": ['off']},
            False
        ]

    def get_arming():
        return ["alarm", {"method": "get_arming"}, True]

    def set_arming(state):
        if (state in ['off', 'on']):
            return [
                "alarm",
                {"method": "set_arming", "params": [state]},
                False
            ]
        else:
            logging.warning("Invalid arming state: " + state)

    def set_arming_time(arming_time):
        return [
            "alarm/time_to_activate",
            {"method": "set_arming_time", "params": [int(arming_time)]},
            True
        ]

    def set_alarm_duration(duration):
        return [
            "alarm/duration",
            {
                "method": "set_device_prop",
                "params": {
                    "sid": "lumi.0",
                    "alarm_time_len": int(duration)
                }
            },
            True
        ]

    def set_alarm_volume(volume):
        return [
            "sound/alarming/volume",
            {"method": "set_alarming_volume", "params": [int(volume)]},
            True
        ]

    def set_alarm_sound(sound):
        return [
            "sound/alarming/sound",
            {
                "method": "set_alarming_sound",
                "params": [0, str(sound)]
            },
            True
        ]

    def set_doorbell_volume(volume):
        return [
            "sound/doorbell/volume",
            {"method": "set_doorbell_volume", "params": [int(volume)]},
            True
        ]

    def set_doorbell_sound(sound):
        return [
            "sound/doorbell/sound",
            {
                "method": "set_doorbell_sound",
                "params": [1, str(sound)]
            },
            True
        ]

    def set_light(state):
        if state in ['off', 'on']:
            return [
                "light",
                {"method": "toggle_light", "params": [str(state)]},
                False
            ]
        else:
            logging.warning("Invalid light state: " + state)

    def set_rgb(brightness, color):
        return [
            "rgb",
            {
                "method": "set_rgb",
                "params": [(int(brightness) << 24) + int(color)]
            },
            False
        ]
