#!/bin/bash
echo "=== Current working directory ==="
pwd
echo "=== Contents of current directory ==="
ls -la
echo "=== Contents of /app ==="
ls -la /app
echo "=== Contents of /app/src ==="
ls -la /app/src
echo "=== Starting Python app ==="
python src/main.py