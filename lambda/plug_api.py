"""
plug_api.py — Lambda handler for the smart plug REST API
Endpoints:
  GET /readings?device=plug&hours=24   → last N hours of readings from DynamoDB
  GET /summary?device=plug             → today's kWh, avg/peak watts
"""
import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone, timedelta
from decimal import Decimal

TABLE_NAME = os.environ.get("TABLE_NAME", "plug-readings")
dynamodb   = boto3.resource("dynamodb", region_name="ap-southeast-1")
table      = dynamodb.Table(TABLE_NAME)


def _json_serial(obj):
    """JSON serialiser for Decimal (DynamoDB returns Decimal for numbers)."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serialisable")


def _ok(body):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_json_serial),
    }


def _err(code, msg):
    return {"statusCode": code, "body": json.dumps({"error": msg})}


def handler(event, context):
    path   = event.get("rawPath", "/")
    params = event.get("queryStringParameters") or {}
    device = params.get("device", "plug")   # 'plug' or 'server'

    # ── GET /readings ──────────────────────────────────────────────────────────
    if path == "/readings":
        hours = int(params.get("hours", "24"))
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        resp = table.query(
            KeyConditionExpression=(
                Key("device_key").eq(device) & Key("timestamp").gte(since)
            ),
            ScanIndexForward=False,
            Limit=500,
        )
        return _ok({"device": device, "hours": hours, "items": resp["Items"]})

    # ── GET /summary ───────────────────────────────────────────────────────────
    elif path == "/summary":
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        resp = table.query(
            KeyConditionExpression=(
                Key("device_key").eq(device) & Key("timestamp").begins_with(today)
            ),
        )
        items = resp["Items"]
        if not items:
            return _ok({"device": device, "readings": 0,
                        "total_wh": 0, "total_kwh": 0,
                        "avg_watts": 0, "peak_watts": 0})

        watts_list = [float(i.get("watts", 0)) for i in items]
        total_wh   = sum(float(i.get("wh_delta", 0)) for i in items)

        total_cost_rm = sum(float(i.get("cost_rm", 0)) for i in items)
        return _ok({
            "device":        device,
            "date":          today,
            "readings":      len(items),
            "total_wh":      round(total_wh, 4),
            "total_kwh":     round(total_wh / 1000, 6),
            "avg_watts":     round(sum(watts_list) / len(watts_list), 2),
            "peak_watts":    round(max(watts_list), 2),
            "total_cost_rm": round(total_cost_rm, 6),
            "tnb_rate":      0.218,
        })

    return _err(404, "Use GET /readings or GET /summary")
