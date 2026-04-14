#!/bin/bash
cd /opt/yol/RoadDamageDetection/api
source /opt/yol/rdd/bin/activate
export DATABASE_URL="postgresql://turna@127.0.0.1:5432/yol_hasar"
export JWT_SECRET="yol-hasar-gizli-anahtar-2026"
nohup uvicorn main:app --host 0.0.0.0 --port 8502 > /opt/yol/api.log 2>&1 &
echo "API PID: $!"