#!/bin/bash
mkdir -p /Volumes/SD/Work/Daily_Standup
python3 /Users/alan/.cc-mirror/crad/config/skills/daily-standup/scripts/generate_standup.py 24 > /Volumes/SD/Work/Daily_Standup/standup-$(date +%Y-%m-%d).txt 2>&1
