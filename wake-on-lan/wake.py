#!/usr/bin/env python

import urllib
import time
import sys
import argparse
import paho.mqtt.client as mqtt
from datetime import datetime

import socket
import struct

broker = "192.168.7.3"

def wake_on_lan(macaddress):
    """ Switches on remote computers using WOL. """

    # Check macaddress format and try to compensate.
    if len(macaddress) == 12:
        pass
    elif len(macaddress) == 12 + 5:
        sep = macaddress[2]
        macaddress = macaddress.replace(sep, '')
    else:
        raise ValueError('Incorrect MAC address format')
 
    # Pad the synchronization stream.
    data = ''.join(['FFFFFFFFFFFF', macaddress * 20])
    send_data = '' 

    # Split up the hex values and pack.
    for i in range(0, len(data), 2):
        send_data = ''.join([send_data,
                             struct.pack('B', int(data[i: i + 2], 16))])

    # Broadcast it to the LAN.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(send_data, ('<broadcast>', 7))

def on_connect(client, userdata, flags, rc):
#    print("Connected with result code " + str(rc))
    client.subscribe("wakeonlan")

def on_message(client, userdata, msg):
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    print(dt_string + " " + msg.topic + " " + str(msg.payload))
    wake_on_lan(msg.payload)
    

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message


client.will_set("wakeonlan/status", "0", 0, True)
client.connect(broker, 1883, 60)
client.publish("wakeonlan/status", "1", 0 , True)

try:
    while True:
        client.loop()
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
