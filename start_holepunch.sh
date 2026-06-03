#!/bin/bash
cd /home/agent/data/sites/relay-mesh
exec python3 holepunch.py --udp-port 9120 --tcp-port 9121 >> /tmp/holepunch.log 2>&1
