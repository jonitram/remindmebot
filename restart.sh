#!/bin/bash
if [ -d .git ]; then
    git pull
fi
python3.7 remindmebot.py
