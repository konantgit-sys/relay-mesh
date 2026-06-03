#!/bin/bash
cd /home/agent/data/sites/relay-mesh
exec python3 lan_discovery.py --port 9901 >> /tmp/lan_discovery.log 2>&1
