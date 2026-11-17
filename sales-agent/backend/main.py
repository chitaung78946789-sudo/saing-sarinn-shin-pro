import os, sqlite3, secrets, json, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from agent_engine import generate_draft, generate_telegram_reply

DB_PATH = os.getenv("DB_PATH", "sales_agent.db")
OWNER_TOKEN = os.getenv("OWNER_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip() or (hashlib.sha256(("saing-sarinn-shin-pro:" + TELEGRAM_BOT_TOKEN).encode()).hexdigest() if TELEGRAM_BOT_TOKEN else "")
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip()]

app = FastAPI(title="AI Super Salesman API", version="0.2.0",
              description="Owner-controlled sales operations API with safe AI drafts and inbound Telegram replies.")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS or [], allow_credentials=False,
                   allow_methods=["GET","POST","PATCH"], allow_headers=["Authorization","Content-Type"])

def connect():
    c=sqlite3.connect(DB_PATH)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',price INTEGER NOT NULL CHECK(price>=0),demo_url TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'draft',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS leads(id TEXT PRIMARY KEY,name TEXT NOT NULL,contact TEXT NOT NULL DEFAULT '',interest TEXT NOT NULL DEFAULT '',source_url TEXT NOT NULL DEFAULT '',permission_note TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'new',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,buyer TEXT NOT NULL,product_id TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),payment_method TEXT NOT NULL DEFAULT '',payment_status TEXT NOT NULL DEFAULT 'pending',verified_at TEXT,delivery_status TEXT NOT NULL DEFAULT 'locked',created_at TEXT NOT NULL,FOREIGN KEY(product_id) REFERENCES products(id));
        CREATE TABLE IF NOT EXISTS agent_runs(id TEXT PRIMARY KEY,agent TEXT NOT NULL,status TEXT NOT NULL,summary TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,action TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orchestration_runs(id TEXT PRIMARY KEY,goal TEXT NOT NULL,status TEXT NOT NULL,outputs_json TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS telegram_history(id TEXT PRIMARY KEY,chat_id TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('user','assistant')),content TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_telegram_history_chat_time ON telegram_history(chat_id,created_at);
        """)
init_db()

@app.on_event("startup")
def configure_telegram_webhook():
    # Automatically register this service as the bot webhook when credentials exist.
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_WEBHOOK_SECRET:
        return
    base_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if not base_url:
        return
    payload = json.dumps({
        "url": base_url + "/api/integrations/telegram/webhook",
        "secret_token": TELEGRAM_WEBHOOK_SECRET,
        "allowed_updates": ["message", "edited_message"],
        "drop_pending_updates": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/setWebhook",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            print("Telegram webhook registration was rejected by Telegram.")
        else:
            print("Telegram webhook registered.")
    except Exception as exc:
        print("Telegram webhook registration failed:", type(exc).__name__)

def now(): return datetime.now(timezone.utc).isoformat()
def audit(action, detail):
    with connect() as c:
        c.execute("INSERT INTO audit VALUES(?,?,?,?)",(secrets.token_hex(12),action,detail,now()))

def owner_auth(authorization: Optional[str] = Header(default=None)):
    if not OWNER_TOKEN:
        raise HTTPException(503, "Owner authentication is not configured. Set OWNER_TOKEN on the server.")
    expected="Bearer "+OWNER_TOKEN
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(401, "Owner authentication required")
    return True

class ProductIn(BaseModel):
    name: str = Field(min_length=1,max_length=120)
    description: str = Field(default="",max_length=2000)
    price: int = Field(ge=0,le=1000000000)
    demo_url: str = Field(default="",max_length=1000)
class LeadIn(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    contact: str = Field(default="",max_length=200)
    interest: str = Field(default="",max_length=200)
    source_url: str = Field(default="",max_length=1000)
    permission_note: str = Field(default="",max_length=1000)
class OrderIn(BaseModel):
    buyer: str = Field(min_length=1,max_length=160)
    product_id: str
    amount: int = Field(gt=0,le=1000000000)
    payment_method: str = Field(default="",max_length=100)
class AgentRunIn(BaseModel):
    agent: str
    summary: str = Field(default="",max_length=2000)
class AgentTaskIn(BaseModel):
    agent: str = Field(min_length=1,max_length=80)
    task: str = Field(min_length=5,max_length=4000)

@app.get("/health")
def health():
    return {"ok":True,"service":"AI Super Salesman API","version":"0.2.0",
            "ai_configured":bool(os.getenv("GROQ_API_KEY")),
            "telegram_configured":bool(TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET)}

@app.get("/api/owner/overview", dependencies=[Depends(owner_auth)])
def overview():
    with connect() as c:
        return {"products":c.execute("SELECT COUNT(*) n FROM products").fetchone()["n"],
                "leads":c.execute("SELECT COUNT(*) n FROM leads").fetchone()["n"],
                "orders":c.execute("SELECT COUNT(*) n FROM orders").fetchone()["n"],
                "verified_revenue":c.execute("SELECT COALESCE(SUM(amount),0) n FROM orders WHERE payment_status='verified'").fetchone()["n"]}

@app.get("/api/products", dependencies=[Depends(owner_auth)])
def products():
    with connect() as c: return [dict(x) for x in c.execute("SELECT * FROM products ORDER BY created_at DESC")]
@app.post("/api/products", dependencies=[Depends(owner_auth)])
def add_product(p:ProductIn):
    i=secrets.token_hex(12)
    with connect() as c: c.execute("INSERT INTO products VALUES(?,?,?,?,?,?,?)",(i,p.name,p.description,p.price,p.demo_url,"draft",now()))
    audit("product.created",i); return {"id":i,"status":"draft"}


@app.post("/api/products/{product_id}/activate", dependencies=[Depends(owner_auth)])
def activate_product(product_id:str):
    with connect() as db:
        cur=db.execute("UPDATE products SET status='active' WHERE id=?",(product_id,))
        if cur.rowcount==0: raise HTTPException(404,"Product not found")
    audit("product.activated",product_id)
    return {"id":product_id,"status":"active","note":"The product can now be shown in inbound Telegram replies."}

@app.get("/api/leads", dependencies=[Depends(owner_auth)])
def leads():
    with connect() as c: return [dict(x) for x in c.execute("SELECT * FROM leads ORDER BY created_at DESC")]
@app.post("/api/leads", dependencies=[Depends(owner_auth)])
def add_lead(l:LeadIn):
    if not l.permission_note.strip():
        raise HTTPException(400,"Record the lawful/public source or contact permission before adding a prospect.")
    i=secrets.token_hex(12)
    with connect() as c: c.execute("INSERT INTO leads VALUES(?,?,?,?,?,?,?,?)",(i,l.name,l.contact,l.interest,l.source_url,l.permission_note,"new",now()))
    audit("lead.created",i); return {"id":i,"status":"new"}

@app.get("/api/orders", dependencies=[Depends(owner_auth)])
def orders():
    with connect() as c: return [dict(x) for x in c.execute("SELECT o.*,p.name product_name FROM orders o LEFT JOIN products p ON p.id=o.product_id ORDER BY o.created_at DESC")]
@app.post("/api/orders", dependencies=[Depends(owner_auth)])
def add_order(o:OrderIn):
    with connect() as c:
        p=c.execute("SELECT id FROM products WHERE id=?",(o.product_id,)).fetchone()
        if not p: raise HTTPException(404,"Product not found")
        i=secrets.token_hex(12)
        c.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?)",(i,o.buyer,o.product_id,o.amount,o.payment_method,"pending",None,"locked",now()))
    audit("order.created",i); return {"id":i,"payment_status":"pending","delivery_status":"locked"}

@app.post("/api/orders/{order_id}/verify-payment", dependencies=[Depends(owner_auth)])
def verify_payment(order_id:str):
    with connect() as c:
        o=c.execute("SELECT id,payment_status FROM orders WHERE id=?",(order_id,)).fetchone()
        if not o: raise HTTPException(404,"Order not found")
        if o["payment_status"]=="verified": return {"id":order_id,"payment_status":"verified","delivery_status":"ready"}
        c.execute("UPDATE orders SET payment_status='verified',verified_at=?,delivery_status='ready' WHERE id=?",(now(),order_id))
    audit("payment.owner_verified",order_id)
    return {"id":order_id,"payment_status":"verified","delivery_status":"ready","note":"Owner must check the actual receiving account first."}

@app.post("/api/agents/runs", dependencies=[Depends(owner_auth)])
def record_agent_run(run:AgentRunIn):
    allowed=set(AGENTS_FOR_API)
    if run.agent not in allowed: raise HTTPException(400,"Unknown agent")
    i=secrets.token_hex(12)
    with connect() as c: c.execute("INSERT INTO agent_runs VALUES(?,?,?,?,?)",(i,run.agent,"recorded",run.summary,now()))
    audit("agent.run.recorded",run.agent); return {"id":i,"status":"recorded"}

AGENTS_FOR_API={"Product Builder","Market Research","Marketing","Sales","Customer Success","Finance & Analytics"}

@app.post("/api/agents/execute", dependencies=[Depends(owner_auth)])
def execute_agent(request:AgentTaskIn):
    if request.agent not in AGENTS_FOR_API: raise HTTPException(400,"Unknown agent")
    try: result=generate_draft(request.agent,request.task)
    except ValueError as exc: raise HTTPException(400,str(exc))
    except RuntimeError as exc: raise HTTPException(503,str(exc))
    i=secrets.token_hex(12)
    with connect() as c: c.execute("INSERT INTO agent_runs VALUES(?,?,?,?,?)",(i,request.agent,"draft_generated",result[:2000],now()))
    audit("agent.draft.generated",request.agent)
    return {"id":i,"agent":request.agent,"status":"draft_generated","draft":result,"requires_owner_approval":True}

class OrchestratorIn(BaseModel):
    goal: str = Field(min_length=10,max_length=3000)

@app.post("/api/orchestrator/run", dependencies=[Depends(owner_auth)])
def run_orchestrator(payload:OrchestratorIn):
    if not os.getenv("GROQ_API_KEY", "").strip():
        raise HTTPException(503,"Set GROQ_API_KEY privately on Render before starting the six-agent system.")
    roles = ["Product Builder", "Market Research", "Marketing", "Sales", "Customer Success", "Finance & Analytics"]
    instructions = [
        "Define the product offer, deliverables, and acceptance checks.",
        "Research customer needs, competitors, market assumptions, and unknowns.",
        "Create truthful positioning, channel plan, and promotional drafts.",
        "Create ethical inquiry handling, qualification, and order scripts.",
        "Create payment-verification, delivery, and support checklists.",
        "Create cost, revenue, profit, and KPI tracking; never invent figures."
    ]
    run_id=secrets.token_hex(12)
    outputs=[]
    with connect() as c:
        c.execute("INSERT INTO orchestration_runs(id,goal,status,outputs_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",(run_id,payload.goal,"running","[]",now(),now()))
    try:
        for idx, role in enumerate(roles):
            context=json.dumps(outputs,ensure_ascii=False)[-7000:] if outputs else "No previous agent output."
            task="Business goal: "+payload.goal+"\nTask: "+instructions[idx]+"\nPrevious agent outputs: "+context+"\nReturn concise Burmese action drafts. Mark assumptions and owner decisions. Do not claim external actions were performed."
            draft=generate_draft(role,task)
            outputs.append({"agent":role,"status":"draft_generated","draft":draft})
            with connect() as c:
                c.execute("INSERT INTO agent_runs VALUES(?,?,?,?,?)",(secrets.token_hex(12),role,"orchestrated_draft",draft[:2000],now()))
                c.execute("UPDATE orchestration_runs SET outputs_json=?,updated_at=? WHERE id=?",(json.dumps(outputs,ensure_ascii=False),now(),run_id))
        status="completed_for_review"
    except RuntimeError as exc:
        status="failed"
        with connect() as c:
            c.execute("UPDATE orchestration_runs SET outputs_json=?,status=?,updated_at=? WHERE id=?",(json.dumps(outputs,ensure_ascii=False),status,now(),run_id))
        raise HTTPException(503,str(exc))
    with connect() as c:
        c.execute("UPDATE orchestration_runs SET status=?,updated_at=? WHERE id=?",(status,now(),run_id))
    audit("orchestrator."+status,run_id)
    return {"id":run_id,"status":status,"agents_completed":len(outputs),"outputs":outputs,"requires_owner_approval":True}

@app.get("/api/orchestrator/runs", dependencies=[Depends(owner_auth)])
def orchestrator_runs():
    with connect() as c:
        rows=c.execute("SELECT * FROM orchestration_runs ORDER BY created_at DESC LIMIT 50").fetchall()
    return [{**dict(x),"outputs":json.loads(x["outputs_json"])} for x in rows]

@app.get("/api/agents/runs", dependencies=[Depends(owner_auth)])
def agent_runs():
    with connect() as c: return [dict(x) for x in c.execute("SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT 100")]
@app.get("/api/audit", dependencies=[Depends(owner_auth)])
def audit_log():
    with connect() as c: return [dict(x) for x in c.execute("SELECT * FROM audit ORDER BY created_at DESC LIMIT 200")]

def telegram_send(chat_id:int, text:str):
    url="https://api.telegram.org/bot"+TELEGRAM_BOT_TOKEN+"/sendMessage"
    payload={"chat_id":chat_id,"text":text[:4000]}
    req=urllib.request.Request(url,data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            data=json.loads(response.read().decode("utf-8"))
        if not data.get("ok"): raise RuntimeError("Telegram sendMessage failed")
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        raise RuntimeError("Telegram API request failed") from exc

@app.post("/api/integrations/telegram/webhook")
async def telegram_webhook(request:Request, x_telegram_bot_api_secret_token:Optional[str]=Header(default=None)):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(503,"Telegram integration is not configured.")
    if not x_telegram_bot_api_secret_token or not secrets.compare_digest(x_telegram_bot_api_secret_token,TELEGRAM_WEBHOOK_SECRET):
        raise HTTPException(403,"Invalid webhook secret.")
    update=await request.json()
    message=update.get("message") or update.get("edited_message")
    if not message or message.get("from",{}).get("is_bot"): return {"ok":True,"ignored":True}
    chat=message.get("chat",{})
    if chat.get("type")!="private": return {"ok":True,"ignored":True}
    text_in=(message.get("text") or "").strip()
    if not text_in: return {"ok":True,"ignored":True}
    if text_in.startswith("/start"):
        reply="မင်္ဂလာပါ။ AI အကူအညီပေးသူပါ။ ဘယ်ထုတ်ကုန် သို့မဟုတ် ဝန်ဆောင်မှုအကြောင်း သိချင်ပါသလဲ။"
    else:
        chat_id=str(chat.get("id", ""))
        with connect() as c:
            rows=c.execute("SELECT name,description,price,demo_url FROM products WHERE status='active' ORDER BY created_at DESC LIMIT 30").fetchall()
            previous=c.execute("SELECT role,content FROM telegram_history WHERE chat_id=? ORDER BY created_at DESC LIMIT 10",(chat_id,)).fetchall()
        history=[{"role":x["role"],"content":x["content"]} for x in reversed(previous)]
        catalogue="\n".join([f"- {x['name']}: {x['description']} | ဈေးနှုန်း {x['price']} ကျပ် | {x['demo_url']}" for x in rows]) or "လက်ရှိ အတည်ပြုပြီး Active ထုတ်ကုန်မရှိသေးပါ။ ဈေးနှုန်း သို့မဟုတ် ပစ္စည်းကို မခန့်မှန်းပါနှင့်။"
        try: reply=generate_telegram_reply(text_in,catalogue,history)
        except RuntimeError: reply="လက်ရှိ AI ဝန်ဆောင်မှု မရနိုင်သေးပါ။ ခဏနေမှ ထပ်မေးပေးပါ။"
    try: telegram_send(int(chat["id"]),reply)
    except RuntimeError: raise HTTPException(502,"Telegram reply could not be sent.")
    with connect() as c:
        c.execute("INSERT INTO telegram_history VALUES(?,?,?,?,?)",(secrets.token_hex(12),chat_id,"user",text_in,now()))
        c.execute("INSERT INTO telegram_history VALUES(?,?,?,?,?)",(secrets.token_hex(12),chat_id,"assistant",reply,now()))
        c.execute("DELETE FROM telegram_history WHERE chat_id=? AND id NOT IN (SELECT id FROM telegram_history WHERE chat_id=? ORDER BY created_at DESC LIMIT 40)",(chat_id,chat_id))
    audit("telegram.inbound_reply",chat_id)
    return {"ok":True,"replied":True}
