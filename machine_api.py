from fastapi import FastAPI, Request
from dotenv import load_dotenv
load_dotenv()
from fastapi.responses import JSONResponse, PlainTextResponse
from datetime import datetime, timedelta
from collections import defaultdict, deque
import os, time, requests, statistics, math

# ================= CONFIG =================
FREE_LIMIT = 100
PRICE_PER_CALL = 0.01
PAYPAL_API = "https://api-m.paypal.com"

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET")

# ================= STATE (RAM ONLY) =================
usage = defaultdict(lambda: {"count": 0, "reset": datetime.utcnow() + timedelta(days=1)})
paid_clients = set()

TOTAL_CALLS = 0
TOTAL_REVENUE = 0.0

# ================= RAM DATA =================
WINDOW = 100
EVENTS = deque(maxlen=WINDOW)
LAST_SNAPSHOT = []

def generate_event():
    v = int(time.time() * 1000) % 10000
    EVENTS.append(v)
    return v

def snapshot():
    global LAST_SNAPSHOT
    LAST_SNAPSHOT = list(EVENTS)
    return LAST_SNAPSHOT

# ================= PAYPAL =================
def paypal_token():
    r = requests.post(
        f"{PAYPAL_API}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
        data={"grant_type": "client_credentials"},
    )
    return r.json()["access_token"]

def create_order(amount, client_id):
    token = paypal_token()
    r = requests.post(
        f"{PAYPAL_API}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": "USD", "value": f"{amount:.2f}"},
                "custom_id": client_id
            }]
        }
    )
    for link in r.json().get("links", []):
        if link["rel"] == "approve":
            return link["href"]
    return None

# ================= FASTAPI =================
app = FastAPI(title="Machine Penny API")

def meter(request: Request):
    global TOTAL_CALLS, TOTAL_REVENUE
    ip = request.client.host
    u = usage[ip]

    if datetime.utcnow() > u["reset"]:
        usage[ip] = {"count": 0, "reset": datetime.utcnow() + timedelta(days=1)}

    if u["count"] >= FREE_LIMIT and ip not in paid_clients:
        amount = (u["count"] - FREE_LIMIT + 1) * PRICE_PER_CALL
        return JSONResponse(
            status_code=402,
            content={
                "price_per_call": PRICE_PER_CALL,
                "amount_due": round(amount, 2),
                "paypal": create_order(amount, ip)
            }
        )

    u["count"] += 1
    TOTAL_CALLS += 1
    if u["count"] > FREE_LIMIT:
        TOTAL_REVENUE += PRICE_PER_CALL

    print(f"{ip} | calls={u['count']} | revenue=${TOTAL_REVENUE:.2f}")
    return None

# ================= VALUE ENDPOINTS =================

@app.get("/query")
def query(req: Request):
    r = meter(req)
    if r: return r

    v = generate_event()
    snapshot()

    return {
        "value": v,
        "mean": round(statistics.mean(EVENTS), 2),
        "volatility": round(statistics.pstdev(EVENTS), 2),
        "trend": "up" if len(EVENTS) > 1 and EVENTS[-1] > EVENTS[-2] else "down",
        "window": len(EVENTS)
    }

@app.get("/metrics")
def metrics(req: Request):
    r = meter(req)
    if r: return r

    if len(EVENTS) < 2:
        return PlainTextResponse("insufficient_data 1")

    diffs = [abs(EVENTS[i] - EVENTS[i-1]) for i in range(1, len(EVENTS))]
    entropy = -sum(
        (d / sum(diffs)) * math.log(d / sum(diffs))
        for d in diffs if d > 0
    )

    return PlainTextResponse(
        f"calls {TOTAL_CALLS}\n"
        f"revenue {TOTAL_REVENUE}\n"
        f"mean {statistics.mean(EVENTS):.2f}\n"
        f"volatility {statistics.pstdev(EVENTS):.2f}\n"
        f"entropy {entropy:.4f}\n"
        f"velocity {statistics.mean(diffs):.2f}"
    )

@app.get("/delta")
def delta(req: Request):
    r = meter(req)
    if r: return r

    if not LAST_SNAPSHOT:
        return {"delta": [], "changed": False}

    current = list(EVENTS)
    delta_vals = [c - p for c, p in zip(current[-len(LAST_SNAPSHOT):], LAST_SNAPSHOT)]

    return {
        "changed": any(delta_vals),
        "delta": delta_vals[-10:],  # last 10 changes
        "magnitude": sum(abs(d) for d in delta_vals)
    }

# ================= PAYMENT =================
@app.post("/paypal/webhook")
async def paypal_webhook(req: Request):
    body = await req.json()
    try:
        cid = body["resource"]["purchase_units"][0]["custom_id"]
        paid_clients.add(cid)
        print(f"💰 PAYMENT CONFIRMED: {cid}")
    except:
        pass
    return {"ok": True}

# ================= DISCOVERY =================
@app.get("/robots.txt")
def robots():
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /query\n"
        "Allow: /stats\n"
        "Allow: /metrics\n"
    )

@app.get("/")
def root():
    return {
        "endpoints": ["/query", "/metrics", "/delta"],
        "price_per_call": PRICE_PER_CALL
    }


print("PayPal ID loaded:", bool(PAYPAL_CLIENT_ID))
