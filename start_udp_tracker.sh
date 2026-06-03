#!/bin/bash
cd /home/agent/data/sites/relay-mesh
exec python3 udp_tracker.py --port 9020 >> /tmp/udp_tracker.log 2>&1
