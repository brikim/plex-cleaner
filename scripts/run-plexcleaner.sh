#!/bin/bash
echo 
echo "===================================================="
echo "$(date) - Running scripts";
python3 /app/deleteWatchedTv.py;
python3 /app/moveLiveTv.py;
python3 /app/deleteOldTv.py;
echo 