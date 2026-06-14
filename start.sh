#!/bin/bash
# Auto-start SNIN Adapter (V2Bot Agent on Nostr)
cd /home/agent/data/sites/relay-mesh
nohup python3 snin_adapter.py run >> data/snin_adapter_run.log 2>&1 &
echo "SNIN Adapter started PID=$!"
