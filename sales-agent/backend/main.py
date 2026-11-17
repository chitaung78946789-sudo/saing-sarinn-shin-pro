import os, sqlite3, secrets, json
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = os.getenv("DB_PATH", "sales_agent.db")
OWNER_TOKEN = os.getenv("OWNER_TOKEN", "")
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip()]

app = FastAPI(title="AI Super Salesman API", version="0.1.0",
              description="Owner-controlled sales operations API. AI/channel adapters are intentionally separate.")
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
        """)
init_db()

def now(): return datetime.now(timezone.utc).isoformat()
def audit(action, detail):
    with connect() as c:
        c.execute("INSERT INTO audit VALUES(?,?,?,?,?)".replace(",?,?,?,?",",?,?,?"), (secrets.token_hex(12),action,detail,now()))

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

@app.get("/health")
def health(): return {"ok":True,"service":"AI Super Salesman API","version":"0.1.0"}

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
    return {"id":order_id,"payment_status":"verified","delivery_status":"ready","note":"Owner must have checked the actual receiving account before calling this endpoint."}

@app.post("/api/agents/runs", dependencies=[Depends(owner_auth)])
def record_agent_run(run:AgentRunIn):
    allowed={"Product Builder","Market Research","Marketing","Sales","Customer Success","Finance & Analytics"}
    if run.agent not in allowed: raise HTTPException(400,"Unknown agent")
    i=secrets.token_hex(12)
    with connect() as c: c.execute("INSERT INTO agent_runs VALUES(?,?,?,?,?)",(i,run.agent,"recorded",run.summary,now()))
    audit("agent.run.recorded",run.agent); return {"id":i,"status":"recorded","note":"This records a run; it does not execute an AI agent."}

@app.get("/api/agents/runs", dependencies=[Depends(owner_auth)])
def agent_runs():
    with connect() as c: return [dict(x) for x in c.execute("SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT 100")]
@app.get("/api/audit", dependencies=[Depends(owner_auth)])
def audit_log():
    with connect() as c: return [dict(x) for x in c.execute("SELECT * FROM audit ORDER BY created_at DESC LIMIT 200")]
