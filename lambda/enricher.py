"""
enricher.py — IoT Rule Lambda trigger
Receives MQTT readings, applies TNB tiered tariff, writes enriched
item to DynamoDB with cost_rm, tnb_rate, monthly_kwh added.
"""
import json, os, time, boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone
from decimal import Decimal

TABLE_NAME = os.environ.get("TABLE_NAME", "plug-readings")
TTL_DAYS   = 90

dynamodb = boto3.resource("dynamodb", region_name="ap-southeast-1")
table    = dynamodb.Table(TABLE_NAME)


def tnb_marginal_rate(monthly_kwh: float) -> float:
    """Return RM/kWh rate for current monthly consumption level."""
    if monthly_kwh <= 200:   return 0.218
    elif monthly_kwh <= 300: return 0.334
    elif monthly_kwh <= 600: return 0.516
    else:                    return 0.546


def get_monthly_kwh(device_key: str) -> float:
    month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
    try:
        resp = table.query(
            KeyConditionExpression=(
                Key("device_key").eq(device_key) &
                Key("timestamp").gte(month_start)
            ),
            ProjectionExpression="wh_delta",
        )
        return sum(float(i.get("wh_delta", 0)) for i in resp.get("Items", [])) / 1000.0
    except Exception as e:
        print(f"[enricher] monthly query error: {e}")
        return 0.0


def handler(event, context):
    print(f"[enricher] received: {json.dumps(event)}")

    device_key  = event.get("device_key", "unknown")
    wh_delta    = float(event.get("wh_delta", 0.0))
    monthly_kwh = get_monthly_kwh(device_key)
    rate        = tnb_marginal_rate(monthly_kwh)
    cost_rm     = round((wh_delta / 1000.0) * rate, 8)

    item = {
        "device_key":  device_key,
        "timestamp":   event.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "device_name": event.get("device_name", ""),
        "switch":      bool(event.get("switch", False)),
        "watts":       Decimal(str(event.get("watts", 0))),
        "voltage":     Decimal(str(event.get("voltage", 0))),
        "current_ma":  int(float(event.get("current_ma", 0))),
        "add_ele_kwh": Decimal(str(event.get("add_ele_kwh", 0))),
        "wh_delta":    Decimal(str(wh_delta)),
        "monthly_kwh": Decimal(str(round(monthly_kwh, 6))),
        "tnb_rate":    Decimal(str(rate)),
        "cost_rm":     Decimal(str(cost_rm)),
        "ttl_epoch":   int(time.time()) + (TTL_DAYS * 86400),
    }

    table.put_item(Item=item)
    print(f"[enricher] ✓ {device_key} | {event.get('watts')}W | RM{cost_rm:.8f} | {monthly_kwh:.4f}kWh @ RM{rate}/kWh")
    return {"statusCode": 200, "body": "ok"}
