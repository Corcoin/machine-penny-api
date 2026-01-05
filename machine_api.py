from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from dotenv import load_dotenv
load_dotenv()
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

WINDOW = 100
EVENTS = deque(maxlen=WINDOW)
LAST_SNAPSHOT = []

# ================= RAM DATA =================
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
app = FastAPI(title="Machine Penny API - PayPal Only")

def meter(request: Request):
    global TOTAL_CALLS, TOTAL_REVENUE
    ip = request.client.host
    u = usage[ip]

    if datetime.utcnow() > u["reset"]:
        usage[ip] = {"count": 0, "reset": datetime.utcnow() + timedelta(days=1)}

    if u["count"] >= FREE_LIMIT and ip not in paid_clients:
        amount_usd = (u["count"] - FREE_LIMIT + 1) * PRICE_PER_CALL
        return JSONResponse(
            status_code=402,
            content={
                "price_per_call": PRICE_PER_CALL,
                "amount_due_usd": round(amount_usd,2),
                "paypal": create_order(amount_usd, ip)
            }
        )

    u["count"] += 1
    TOTAL_CALLS += 1
    if u["count"] > FREE_LIMIT:
        TOTAL_REVENUE += PRICE_PER_CALL

    print(f"[{datetime.utcnow().isoformat()}] {ip} | calls={u['count']} | revenue=${TOTAL_REVENUE:.2f}")
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
    if len(EVENTS) < 2: return PlainTextResponse("insufficient_data")
    diffs = [abs(EVENTS[i] - EVENTS[i-1]) for i in range(1, len(EVENTS))]
    entropy = -sum((d/sum(diffs))*math.log(d/sum(diffs)) for d in diffs if d>0)
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
    if not LAST_SNAPSHOT: return {"delta": [], "changed": False}
    current = list(EVENTS)
    delta_vals = [c - p for c, p in zip(current[-len(LAST_SNAPSHOT):], LAST_SNAPSHOT)]
    return {"changed": any(delta_vals), "delta": delta_vals[-10:], "magnitude": sum(abs(d) for d in delta_vals)}

@app.get("/latest")
def latest(req: Request):
    r = meter(req)
    if r: return r
    return {"latest": EVENTS[-1] if EVENTS else None}

@app.get("/lookup")
def lookup(key: str, req: Request):
    r = meter(req)
    if r: return r
    return {"key": key, "value": hash(key) % 10000}

@app.get("/resolve")
def resolve(id: int, req: Request):
    r = meter(req)
    if r: return r
    return {"id": id, "resolved": True}

@app.get("/signals")
def signals(req: Request):
    r = meter(req)
    if r: return r
    return {"signal": "BUY", "strength": 0.91}

@app.get("/features")
def features(req: Request):
    r = meter(req)
    if r: return r
    return {"features": [0.12, 0.88, 0.44, 0.91]}

@app.get("/stats")
def stats(req: Request):
    r = meter(req)
    if r: return r
    return {"total_calls": TOTAL_CALLS, "revenue": TOTAL_REVENUE}

@app.get("/pricing")
def pricing():
    return {"free_calls": FREE_LIMIT, "price_per_call": PRICE_PER_CALL}

# ================= OPENAI-STYLE ENDPOINTS =================
@app.post("/predict")
def predict(data: dict, req: Request):
    r = meter(req)
    if r: return r
    x = data.get("input", 1)
    value = (sum(EVENTS) + x*42) % 10000
    return {"input": x, "prediction": value}

@app.post("/embed")
def embed(data: dict, req: Request):
    r = meter(req)
    if r: return r
    vec = [(hash(str(data.get("input", i))) % 1000)/1000 for i in range(8)]
    return {"embedding": vec}

@app.post("/completion")
def completion(data: dict, req: Request):
    r = meter(req)
    if r: return r
    prompt = data.get("prompt","")
    return {"completion": f"Output for '{prompt}' at {int(time.time())}"}

# ================= PAYMENT WEBHOOK =================
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

# ================= BOT DISCOVERY =================
@app.get("/robots.txt")
def robots():
    return PlainTextResponse(
        "User-agent: *\n"
        "Allow: /query\n"
        "Allow: /stats\n"
        "Allow: /metrics\n"
        "Allow: /delta\n"
        "Allow: /latest\n"
        "Allow: /lookup\n"
        "Allow: /resolve\n"
        "Allow: /signals\n"
        "Allow: /features\n"
        "Allow: /predict\n"
        "Allow: /embed\n"
        "Allow: /completion\n"
    )

@app.get("/")
def root():
    return {
        "endpoints": [
            "/query","/stats","/metrics","/delta","/latest",
            "/lookup","/resolve","/signals","/features",
            "/predict","/embed","/completion"
        ],
        "price_per_call": PRICE_PER_CALL
    }

print("PayPal ID loaded:", bool(PAYPAL_CLIENT_ID))
