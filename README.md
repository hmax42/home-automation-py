# home-automation-py
my home-automation-scripts


* IKEA Tradfri
  * based on the pytradfri lib https://github.com/ggravlingen/pytradfri/
  * publishes dynamically all at the tradfri-gateway registered lights blinds and groups
  * publishes to /tradfri/ID/status
  * receives on /tradfri/ID
  * supports lights, blinds and groups
  * currently the messages consist of "on" and "off"
    * for blinds this is internally translated to 99.0 and 1.0
* Wake on LAN
  * sends a wol-packet to the received MAC-adress

