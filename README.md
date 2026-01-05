# Machine Penny API

FastAPI-based API charging **$0.01 per call** after 100 free requests. Designed for automated bots and scripts — no human interaction required.  

🌐 **Live API:** [https://peak-made-extensive-phases.trycloudflare.com](https://peak-made-extensive-phases.trycloudflare.com)  

Clone the repo: `git clone https://github.com/<your-username>/<repo-name>.git && cd <repo-name>` and install dependencies with `pip install -r requirements.txt`. Create a `.env` file with your PayPal credentials: `PAYPAL_CLIENT_ID=your-client-id` and `PAYPAL_SECRET=your-client-secret`. Run FastAPI using `uvicorn machine_api:app --host 0.0.0.0 --port 8000`. Optionally expose a public URL with `cloudflared tunnel --url http://localhost:8000`.  

**Core API Endpoints:** `/query` returns value, mean, volatility, trend, window; `/metrics` returns calls, revenue, mean, volatility, entropy, velocity; `/delta` returns last 10 changes and magnitude; `/latest` returns latest value; `/lookup?key=<key>` returns key hash value; `/resolve?id=<id>` returns resolved test; `/signals` dummy signal (BUY/SELL); `/features` dummy features array; `/stats` total calls and revenue; `/pricing` free call limit and price per call.  

**OpenAI-style Endpoints:** `/predict` POST JSON `{ "input": number }`; `/embed` POST JSON `{ "input": string }`; `/completion` POST JSON `{ "prompt": string }`.  

**Payment:** `/paypal/webhook` receives PayPal confirmations. Example: `curl -X POST https://peak-made-extensive-phases.trycloudflare.com/paypal/webhook -H "Content-Type: application/json" -d '{"resource":{"purchase_units":[{"custom_id":"127.0.0.1"}]}}'` outputs in terminal: `💰 PAYMENT CONFIRMED: 127.0.0.1`.  

**Discovery for Bots:** `/robots.txt` contains:  
