#!/usr/bin/env python
import urllib
import time
from datetime import datetime
import sys
import argparse
import lxml.html
from lxml import etree
import paho.mqtt.client as mqtt
from pytradfri import Gateway
from pytradfri.api.libcoap_api import APIFactory
from pytradfri.error import PytradfriError
from pytradfri.util import load_json, save_json

hubip = '192.168.1.2' 
securityid = 'secret'
userid = 'secretuser'
broker = '192.168.7.3'


display = 0
base_name = "/tradfri"
status_name = "/status"
brightness_name = "/brightness"
color_name = "/color"
ON = b'on'
OFF = b'off'
name = "tradfri"
subname = "/mqtt2tradfri"
DELAY = 30
last_time = - DELAY - 1
force = False
SLEEP=2
flag_connected = 0

def on_disconnect(client, userdata, rc):
    print("Disconnected")
    global flag_connected
    flag_connected = 0
    client.reconnect()

def on_reconnect(client, userdata, flags, rc):
    on_connect(client, userdata, flags, rc)

def on_connect(client, userdata, flags, rc):
    client.will_set("mqtt2tradfri/status", "0", 0, True)
    print("Connected with result code " + str(rc))
    client.subscribe(base_name + "/+")
    client.subscribe(base_name + "/+/+")
    print("Subscribed")
    client.publish("clients/presence", name + subname + " appeared")
    client.publish("mqtt2tradfri/status", "1", 0, True)
    global flag_connected
    flag_connected = 1

a = None
devices = None
groups = None

def on_message(client, userdata, msg):
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    print(dt_string + " " + msg.topic + " " + str(msg.payload))
    if msg.topic.count('/') == 2:
        id = msg.topic[9:]
        if len(id) == 5:
            set_light(id,'',msg.payload)
        if len(id) == 6:
            set_group(id,'',msg.payload)
    elif msg.topic.count('/') == 3:
        if msg.topic[14] == '/':
#bulb
            id = msg.topic[9:14]
            type = msg.topic[15:]
            set_light(id, type, msg.payload)
        elif msg.topic[15] == '/':
#group
            id = msg.topic[9:15]
            type = msg.topic[16:]
            set_group(id, type, msg.payload)


def set_light(bulbid,type,data):
    global devices, a
    d = [dev for dev in devices if str(dev.id)==bulbid]
    if d:
        dvc = d[0]
    if dvc and type != 'status':
        if dvc.has_light_control:
            if data == ON:
                set_command = dvc.light_control.set_state(True)
                a(set_command)
                client.publish(base_name + "/" + str(bulbid) + status_name, data)
            elif data == OFF:
                set_command = dvc.light_control.set_state(False)
                a(set_command)
                client.publish(base_name + "/" + str(bulbid) + status_name, data)
        elif dvc.has_blind_control:
            if data == ON:
                set_command = dvc.blind_control.set_state(99)
                a(set_command)
                client.publish(base_name + "/" + str(bulbid) + status_name, data)
            elif data == OFF:
                set_command = dvc.blind_control.set_state(1)
                a(set_command)
                client.publish(base_name + "/" + str(bulbid) + status_name, data)

    time.sleep(.5)


def set_group(groupid,type,data):
    global groups, a
    g = [group for group in groups if str(group.id)==groupid]
    if g:
        gr = g[0]
    if gr and type != 'status':
        if data == ON:
            set_command = gr.set_state(True)
            a(set_command)
            client.publish(base_name + "/" + str(groupid) + status_name, data)
        elif data == OFF:
            set_command = gr.set_state(False)
            a(set_command)
            client.publish(base_name + "/" + str(groupid) + status_name, data)
        global force
        force = True
    time.sleep(.5)

client = mqtt.Client()
client.on_disconnect = on_disconnect
client.on_connect = on_connect
client.on_message = on_message


try:
    print("Config read")

    api_factory = APIFactory(host=hubip, psk_id=userid, psk=securityid)
    print("Config set")

    a = api_factory.request
    api = a
    gateway = Gateway()


    client.will_set("mqtt2tradfri/status", "0", 0, True)
    client.connect(broker, 1883, 60)
    print("Connected")

    while True:
        client.loop()
        if force or last_time + DELAY < time.time():
            force = False

            try:
                devices_command = gateway.get_devices()
                devices_commands = api(devices_command)
                devices = api(devices_commands)
                #print(devices)
            except:
                client.disconnect()
                client.reconnect()
                print("error2")
                client.publish("esp/text", "tradfri: error while getting devices")
                #pass
                # sometimes the request are to fast, the will decline the request (flood security)
                # in this case you could increse the sleep timer
            time.sleep(SLEEP)
            try:
                groups_command = gateway.get_groups()
                groups_commands = api(groups_command)
                groups = api(groups_commands)
                #print(groups)
            except:
                client.disconnect()
                client.reconnect()
                client.publish("esp/text", "tradfri: error while getting groups")
                print("error3")
                #pass
            time.sleep(SLEEP)
            last_time = time.time()
                
            #publish
            if devices:
                lights = [dev for dev in devices if dev.has_light_control]
                print("Id\tState\tDimmer\tName")
                for l in range(len(lights)):
                    light = lights[l]
                    print("{}\t{}\t{}\t{}".format(light.id, light.light_control.lights[0].state, light.light_control.lights[0].dimmer, light.name))
  
                    b = str(int(float(light.light_control.lights[0].dimmer)/2.55))
                    client.publish(base_name + "/" + str(light.id) + status_name + brightness_name, b)
                    if(light.light_control.lights[0].state):
                        client.publish(base_name + "/" + str(light.id) + status_name, ON)
                    else:
                        client.publish(base_name + "/" + str(light.id) + status_name, OFF)
                print("****************************************")
                blinds = [dev for dev in devices if dev.has_blind_control]
                print("Id\tState\tName")
                for b in range(len(blinds)):
                    blind = blinds[b]
                    print("{}\t{}\t{}".format(blind.id, blind.blind_control.blinds[0].current_cover_position, blind.name))
                    if blind.blind_control.blinds[0].current_cover_position > 98.0:
                        cp = ON
                    elif blind.blind_control.blinds[0].current_cover_position < 2.0:
                        cp = OFF
                    if cp:
                        client.publish(base_name + "/" + str(blind.id) + status_name, cp)
                print("****************************************")
            else:
                print("No devices")
                client.publish("esp/text", "tradfri: no devices")

            if groups:
                print("Id\tState\tName")
                print("    Members")
                for g in range(len(groups)):
                    group = groups[g]

                    # check lamp state instead of group state
                    m1 = [m for m in devices if m.id in group.member_ids and m.has_light_control]
                    b1 = [m for m in devices if m.id in group.member_ids and m.has_blind_control]
                    mi = [m.id for m in m1]
                    bi = [b.id for b in b1]
                    if len(m1) > 0:
                        m3 = [m.id for m in m1 if m.light_control.lights[0].state == True]
                        m4 = [m.id for m in m1 if m.light_control.lights[0].state == False]
                        if set(m3) == set(mi):
                            allOn = "+"
                            client.publish(base_name + "/" + str(group.id) + status_name, ON)
                        elif set(m4) == set(mi):
                            allOn = "-"
                            client.publish(base_name + "/" + str(group.id) + status_name, OFF)
                        else:
                            allOn = "?"
                    elif len(b1) > 0:
                        b3 = [m.id for m in b1 if m.blind_control.blinds[0].current_cover_position > 98.0]
                        b4 = [m.id for m in b1 if m.blind_control.blinds[0].current_cover_position < 2.0]
                        if set(b3) == set(bi):
                            allOn = "+"
                            client.publish(base_name + "/" + str(group.id) + status_name, ON)
                        elif set(b4) == set(bi):
                            allOn = "-"
                            client.publish(base_name + "/" + str(group.id) + status_name, OFF)
                        else:
                            allOn = "?"


                    print("{}\t{}\t{}".format(group.id, allOn, group.name))
                    for mbm in group.member_ids:
                        print("    {}".format(mbm))
                print("==========================")
            else:
                print("No groups")
                client.publish("esp/text", "tradfri: no groups")

except KeyboardInterrupt:
    pass
