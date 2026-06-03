#!/bin/bash
cd /home/agent/data/sites/relay-mesh
exec python3 relay_signing.py --port 9125 >> /tmp/relay_signing.log 2>&1
