#!/bin/bash
cd /home/agent/data/sites/relay-mesh
exec python3 -u cheque_book.py >> logs/chequebook.log 2>&1
