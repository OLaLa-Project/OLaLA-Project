#!/bin/bash
mkdir -p logs
docker logs olala-backend > logs/olala-backend.log 2>&1
docker logs olala-frontend > logs/olala-frontend.log 2>&1
# Add other containers if needed
echo "Logs saved to logs/"
