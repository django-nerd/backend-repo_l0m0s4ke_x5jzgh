import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Schemas ==========
class ContactPayload(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    message: str = Field(..., min_length=4, max_length=4000)


class CheckoutPayload(BaseModel):
    courseId: str = Field(..., min_length=1)
    plan: Optional[str] = Field(default="standard")


class AnalyticsEvent(BaseModel):
    event: str = Field(..., min_length=2, max_length=64)
    properties: Optional[Dict[str, Any]] = None
    user: Optional[Dict[str, Any]] = None


# Attempt DB import (Mongo is preconfigured in this environment)
try:
    from database import db, create_document
except Exception:
    db, create_document = None, None


# ========== Core Routes ==========
@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# ========== Ascendia Integrations ==========
@app.post("/api/contact")
def submit_contact(payload: ContactPayload):
    """Persist contact form submissions. Lightweight validation + DB write."""
    doc = {
        **payload.model_dump(),
        "_type": "contact",
        "received_at": datetime.now(timezone.utc),
    }
    if create_document:
        try:
            _id = create_document("contact", doc)
            return {"ok": True, "id": _id}
        except Exception as e:
            # Still respond OK-ish but indicate server side note
            raise HTTPException(status_code=500, detail=f"Failed to save contact: {e}")
    return {"ok": True}


@app.post("/api/checkout")
def create_checkout(payload: CheckoutPayload):
    """
    Create a mock checkout session (Stripe-like) without heavy SDKs.
    Persists intent to DB and returns a session URL the frontend can open.
    """
    session_id = f"sess_{int(datetime.now().timestamp())}"
    session_url = f"/checkout/success?sid={session_id}&course={payload.courseId}"
    record = {
        "_type": "checkout",
        "courseId": payload.courseId,
        "plan": payload.plan,
        "session_id": session_id,
        "session_url": session_url,
        "created_at": datetime.now(timezone.utc),
    }
    if create_document:
        try:
            create_document("checkout", record)
        except Exception:
            pass
    return {"ok": True, "sessionId": session_id, "url": session_url}


@app.post("/api/analytics")
def track_event(event: AnalyticsEvent):
    """Capture analytics events in a lightweight collection."""
    record = {
        **event.model_dump(),
        "_type": "analytics",
        "received_at": datetime.now(timezone.utc),
    }
    if create_document:
        try:
            create_document("analytics", record)
        except Exception:
            pass
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
