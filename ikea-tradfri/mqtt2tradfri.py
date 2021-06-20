#!/usr/bin/env python3
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


display = 0
base_name = "/tradfri"
status_name = "/status"
battery_name = "/battery"
brightness_name = "/brightness"
color_name = "/color"
ON = b'on'
OFF = b'off'
name = "tradfri"
subname = "/mqtt2tradfri"
DELAY = 30
last_time = - DELAY - 1
grp = { b'131073' : [ b'65537', b'65538' ], b'131074' : [ b'65540' ]}
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
#    client.subscribe(base_name + "/+/+")
#    client.subscribe(base_name + "/+/brightness")
#    client.subscribe(base_name + "/+/status")
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
    dvc = None
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
        elif dvc.has_socket_control:
            if data == ON:
                set_command = dvc.socket_control.set_state(True)
                a(set_command)
                client.publish(base_name + "/" + str(bulbid) + status_name, data)
            elif data == OFF:
                set_command = dvc.socket_control.set_state(False)
                a(set_command)
                client.publish(base_name + "/" + str(bulbid) + status_name, data)
    time.sleep(.5)


def set_group(groupid,type,data):
    global groups, a, devices
    g = [group for group in groups if str(group.id)==groupid]
    gr = None
    if g:
        gr = g[0]
    if gr and type != 'status':
        mb = [dev for dev in devices if dev.has_blind_control and dev.id in gr.member_ids]
        ml = [dev for dev in devices if dev.has_light_control and dev.id in gr.member_ids]
        ms = [dev for dev in devices if dev.has_socket_control and dev.id in gr.member_ids]
        if len(mb) > 0 :
            if data == ON:
                for d in mb:
                    set_command = d.blind_control.set_state(100)
                    a(set_command)
            elif data == OFF:
                for d in mb:
                    set_command = d.blind_control.set_state(1)
                    a(set_command)
        elif len(ml) > 0 or len(ms) > 0:
            if data == ON:
                set_command = gr.set_state(True)
                a(set_command)
            elif data == OFF:
                set_command = gr.set_state(False)
                a(set_command)
        client.publish(base_name + "/" + str(groupid) + status_name, data)
        global force
        force = True
    time.sleep(.25)

client = mqtt.Client()
client.on_disconnect = on_disconnect
client.on_connect = on_connect
client.on_message = on_message

CONFIG_FILE = "tradfri_standalone_psk.conf"

try:
    conf = load_json(CONFIG_FILE)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "host", metavar="IP", type=str, help="IP Address of your Tradfri gateway"
    )
    parser.add_argument(
        "-K", "--key", dest="key", required=False, help="Key found on your Tradfri gateway"
    )
    args = parser.parse_args()
#    args.host = "192.168.7.180"

    if args.host not in load_json(CONFIG_FILE) and args.key is None:
        print(
            "Please provide the 'Security Code' on the back of your " "Tradfri gateway:",
            end=" ",
        )
        key = input().strip()
        if len(key) != 16:
            raise PytradfriError("Invalid 'Security Code' provided.")
        else:
            args.key = key



    try:
        identity = conf[args.host].get("identity")
        psk = conf[args.host].get("key")
        api_factory = APIFactory(host=args.host, psk_id=identity, psk=psk)
    except KeyError:
        identity = uuid.uuid4().hex
        api_factory = APIFactory.init(host=args.host, psk_id=identity)

        try:
            psk = api_factory.generate_psk(args.key)
            print("Generated PSK: ", psk)

            conf[args.host] = {"identity": identity, "key": psk}
            save_json(CONFIG_FILE, conf)
        except AttributeError:
            raise PytradfriError(
                "Please provide the 'Security Code' on the "
                "back of your Tradfri gateway using the "
                "-K flag."
            )


    print("Config set")





    a = api_factory.request
    api = a
    gateway = Gateway()


    client.will_set("mqtt2tradfri/status", "0", 0, True)
    client.connect("192.168.7.66", 1883, 60)
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
                last_time = time.time()
            except:
                client.disconnect()
                client.reconnect()
                print("error devices")
                client.publish("esp/text", "tradfri: error while getting devices")
                continue
                #pass
                # sometimes the request are to fast, the will decline the request (flood security)
                # in this case you could increse the sleep timer
            time.sleep(SLEEP)
               
            #publish
            if devices:
                lights = [dev for dev in devices if dev.has_light_control]
                for l in range(len(lights)):
                    light = lights[l]
                    if(light.light_control.lights[0].state):
                        client.publish(base_name + "/" + str(light.id) + status_name, ON)
                    else:
                        client.publish(base_name + "/" + str(light.id) + status_name, OFF)
                sockets = [dev for dev in devices if dev.has_socket_control]
                for s in range(len(sockets)):
                    socket = sockets[s]
                    if(socket.socket_control.sockets[0].state):
                        client.publish(base_name + "/" + str(socket.id) + status_name, ON)
                    else:
                        client.publish(base_name + "/" + str(socket.id) + status_name, OFF)
                blinds = [dev for dev in devices if dev.has_blind_control]
                for b in range(len(blinds)):
                    blind = blinds[b]
                    client.publish(base_name + "/" + str(blind.id) + battery_name, blind.device_info.battery_level)
                    if blind.blind_control.blinds[0].current_cover_position >= 50.0:
                        cp = ON
                    else:
                        cp = OFF
                    if cp:
                        client.publish(base_name + "/" + str(blind.id) + status_name, cp)
            else:
                print("No devices")
                client.publish("esp/text", "tradfri: no devices")


            try:
                groups_command = gateway.get_groups()
                groups_commands = api(groups_command)
                groups = api(groups_commands)
                #print(groups)
                last_time = time.time()
            except:
                client.disconnect()
                client.reconnect()
                client.publish("esp/text", "tradfri: error while getting groups")
                print("error groups")
                continue
                #pass
            time.sleep(SLEEP)
            if groups:
                print("Id\tState\tDimmer\tName")
                print(" Memb.\tState\tDimmer\tName")
                groups = sorted(groups, key=lambda x: int(x.id))
                for g in range(len(groups)):
                    group = groups[g]

                    # check lamp state instead of group state
                    m1 = [m for m in devices if m.id in group.member_ids and m.has_light_control]
                    m3 = [m.id for m in m1 if m.light_control.lights[0].state == True]
                    m4 = [m.id for m in m1 if m.light_control.lights[0].state == False]

                    s1 = [s for s in devices if s.id in group.member_ids and s.has_socket_control]
                    s3 = [s.id for s in s1 if s.socket_control.sockets[0].state == True]
                    s4 = [s.id for s in s1 if s.socket_control.sockets[0].state == False]

                    b1 = [m for m in devices if m.id in group.member_ids and m.has_blind_control]
                    b3 = [m.id for m in b1 if m.blind_control.blinds[0].current_cover_position > 98.0]
                    b4 = [m.id for m in b1 if m.blind_control.blinds[0].current_cover_position < 2.0]

                    e1 = [e for e in devices if e.id in group.member_ids and not e.has_light_control and not e.has_blind_control and not e.has_socket_control]



                    if (len(m1) == len(m3) and len(s1) == len(s3) and len(b1) == len(b3)):
                        allOn = "++"
                        client.publish(base_name + "/" + str(group.id) + status_name, ON)
                    elif (len(m1) == len(m4) and len(s1) == len(s4) and len(b1) == len(b4)):
                        allOn = "--"
                        client.publish(base_name + "/" + str(group.id) + status_name, OFF)
                    elif group.state == True:
                        allOn = "+"
                        client.publish(base_name + "/" + str(group.id) + status_name, ON)
                    else:
                        allOn = "-"
                        client.publish(base_name + "/" + str(group.id) + status_name, OFF)



                    print("{}\t{}\t{}\t{}".format(group.id, allOn, "x", group.name))
                    for mbm in sorted(group.member_ids, key=lambda x: int(x)):
                        ll = [llll for llll in m1 if llll.id == mbm]
                        if len(ll)>0:
                            lll = ll[0]
                            print(" {}\t{}\t{}\t{}".format(lll.id, lll.light_control.lights[0].state, str(int(float(light.light_control.lights[0].dimmer)/2.55))
, lll.name))
                        ss = [ssss for ssss in s1 if ssss.id == mbm]
                        if len(ss)>0:
                            sss = ss[0]
                            print(" {}\t{}\t{}\t{}".format(sss.id, sss.socket_control.sockets[0].state, "x", sss.name))
                        bb = [bbbb for bbbb in b1 if bbbb.id == mbm]
                        if len(bb)>0:
                            bbb = bb[0]
                            print(" {}\t{}\t{}\t{}".format(bbb.id, "x", bbb.blind_control.blinds[0].current_cover_position, bbb.name))
                        ee = [eeee for eeee in e1 if eeee.id == mbm]
                        if len(ee)>0:
                            eee = ee[0]
                            print(" {}\t{}\t{}\t{}".format(eee.id, 'x', 'x', eee.name))

                    print("==========================")



            else:
                print("No groups")
                client.publish("esp/text", "tradfri: no groups")

except KeyboardInterrupt:
    pass
