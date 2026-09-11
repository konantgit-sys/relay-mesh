#!/bin/bash
cd /home/agent/data/sites/relay-mesh
exec python3 relay_mesh_api.py 9907 >> logs/relay_mesh_api.log 2>&1
