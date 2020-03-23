# MIT License
#
# Copyright (c) 2019 Alex Temnok
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""HS300 Power Driver"""

__all__ = []

import array
import json
import socket
import time
from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import (
    PowerDriver,
)


class HS300(object):
    def __init__(self, ip):
        self.ip = ip
        self.device_id = None

    def get_sysinfo(self):
        return self._send_udp({
            "system": {
                "get_sysinfo": {},
            }
        })

    def set_relay_state(self, id, state):
        return self._send_udp({
            "context": {
                "child_ids": [self._get_device_outlet_id(id)]
            },
            "system": {
                "set_relay_state": {
                    "state": state
                },
                "get_sysinfo": {},
            }
        })

    def get_relay_state(self, id, min_power=None):
        response = self._get_realtime_emeter(id)
        state = self._get_outlet_state_from_response(response, id)
        if state == 1 and min_power is not None:
            if response["emeter"]["get_realtime"]["power_mw"] < min_power * 1000:
                response = self.set_relay_state(id, 0)
                return self._get_outlet_state_from_response(response, id)
        return state

    def _get_realtime_emeter(self, id):
        return self._send_udp({
            "context": {
                "child_ids": [self._get_device_outlet_id(id)]
            },
            "system": {
                "get_sysinfo": {}
            },
            "emeter": {
                "get_realtime": {},
            }
        })

    def _get_outlet_state_from_response(self, response, id):
        children, id = response["system"]["get_sysinfo"]["children"], str(id).zfill(2)
        return [c for c in children if c["id"] == id][0]["state"]

    def _get_device_outlet_id(self, id):
        if not self.device_id:
            self.device_id = self.get_sysinfo()["system"]["get_sysinfo"]["deviceId"]
        return self.device_id + str(id).zfill(2)

    def _send_udp(self, request):
        time.sleep(0.5)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        request = self._encode(json.dumps(request))
        s.sendto(request, (self.ip, 9999))
        response, addr = s.recvfrom(1024)
        time.sleep(0.5)
        return json.loads(self._decode(response))

    @staticmethod
    def _encode(string):
        result, a = [], 171
        for c in string:
            a ^= ord(c)
            result.append(a)
        return array.array("B", result).tobytes()

    @staticmethod
    def _decode(string):
        result, a = "", 171
        for c in string:
            result += chr(a ^ c)
            a = c
        return result


class HS300PowerDriver(PowerDriver):
    name = 'hs300'
    chassis = True
    description = "HS300"
    settings = [
        make_setting_field('power_address', "IP address", required=True),
        make_setting_field('outlet_id', "Outlet ID, 1-6", scope=SETTING_SCOPE.NODE, required=True),
        make_setting_field('min_power', "Min ON power, W (optional)", scope=SETTING_SCOPE.NODE, required=False),
    ]
    ip_extractor = make_ip_extractor('power_address')

    def detect_missing_packages(self):
        return []

    def power_on(self, system_id, context):
        self._set_outlet_state(1, **context)

    def power_off(self, system_id, context):
        self._set_outlet_state(0, **context)

    def power_query(self, system_id, context):
        return self._query_outlet_state(**context)

    def _set_outlet_state(self, state, power_address=None, outlet_id=None, **extra):
        client = HS300(power_address)
        client.set_relay_state(int(outlet_id) - 1, state)

    def _query_outlet_state(self, power_address=None, outlet_id=None, min_power=None, **extra):
        client = HS300(power_address)
        if min_power is not None:
            min_power = float(min_power)
        if client.get_relay_state(int(outlet_id) - 1, min_power) == 0:
            return "off"
        return "on"
