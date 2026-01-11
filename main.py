from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import sqlite3
import json
import hashlib
import secrets
from contextlib import contextmanager

app = FastAPI(title="Buyer Request Workflow API")

# Database setup
DB_PATH = "workflow.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize database schema"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                actor_user_id TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                action TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
        """)
        
        # Evidence table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                factory_id TEXT NOT NULL,
                name TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Evidence versions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_versions (
                id TEXT PRIMARY KEY,
                evidence_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                expiry TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES evidence(id)
            )
        """)
        
        # Requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                buyer_id TEXT NOT NULL,
                factory_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Request items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_items (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                evidence_id TEXT,
                version_id TEXT,
                fulfilled_at TEXT,
                FOREIGN KEY (request_id) REFERENCES requests(id)
            )
        """)
        
        # Auth tokens (in-memory would work too, but using DB for persistence)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                factory_id TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)

# Enums
class Role(str, Enum):
    BUYER = "buyer"
    FACTORY = "factory"

class Action(str, Enum):
    CREATE_REQUEST = "CREATE_REQUEST"
    CREATE_EVIDENCE = "CREATE_EVIDENCE"
    ADD_VERSION = "ADD_VERSION"
    FULFILL_ITEM = "FULFILL_ITEM"
    LOGIN = "LOGIN"

class ObjectType(str, Enum):
    REQUEST = "Request"
    EVIDENCE = "Evidence"
    VERSION = "Version"
    REQUEST_ITEM = "RequestItem"

# Pydantic models
class LoginRequest(BaseModel):
    userId: str
    role: Role
    factoryId: Optional[str] = None

class LoginResponse(BaseModel):
    token: str
    userId: str
    role: str
    factoryId: Optional[str] = None

class EvidenceCreate(BaseModel):
    name: str
    docType: str
    expiry: Optional[str] = None
    notes: Optional[str] = None

class EvidenceResponse(BaseModel):
    evidenceId: str
    versionId: str

class VersionCreate(BaseModel):
    notes: Optional[str] = None
    expiry: Optional[str] = None

class RequestItem(BaseModel):
    docType: str

class RequestCreate(BaseModel):
    factoryId: str
    title: str
    items: List[RequestItem]

class FulfillRequest(BaseModel):
    evidenceId: str
    versionId: str

class AuditEntry(BaseModel):
    id: int
    timestamp: str
    actorUserId: str
    actorRole: str
    action: str
    objectType: str
    objectId: str
    metadata: Dict[str, Any]

# Helper functions
def generate_id(prefix: str) -> str:
    """Generate unique ID with prefix"""
    return f"{prefix}{secrets.token_hex(4).upper()}"

def log_audit(
    conn: sqlite3.Connection,
    actor_user_id: str,
    actor_role: str,
    action: Action,
    object_type: ObjectType,
    object_id: str,
    metadata: Dict[str, Any]
):
    """Write audit log entry"""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log (timestamp, actor_user_id, actor_role, action, object_type, object_id, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().isoformat(),
        actor_user_id,
        actor_role,
        action.value,
        object_type.value,
        object_id,
        json.dumps(metadata)
    ))

def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Validate token and return user info"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.split(" ")[1]
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, role, factory_id, expires_at 
            FROM auth_tokens 
            WHERE token = ?
        """, (token,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        if datetime.fromisoformat(row['expires_at']) < datetime.utcnow():
            raise HTTPException(status_code=401, detail="Token expired")
        
        return {
            "userId": row['user_id'],
            "role": row['role'],
            "factoryId": row['factory_id']
        }

def require_role(required_role: Role):
    """Dependency to require specific role"""
    def checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if user['role'] != required_role.value:
            raise HTTPException(status_code=403, detail=f"Requires {required_role.value} role")
        return user
    return checker

# API Endpoints

@app.on_event("startup")
async def startup():
    """Initialize database on startup"""
    init_db()

@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return token"""
    # Validate factory role has factoryId
    if request.role == Role.FACTORY and not request.factoryId:
        raise HTTPException(status_code=400, detail="Factory role requires factoryId")
    
    if request.role == Role.BUYER and request.factoryId:
        raise HTTPException(status_code=400, detail="Buyer role should not have factoryId")
    
    # Generate token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO auth_tokens (token, user_id, role, factory_id, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            token,
            request.userId,
            request.role.value,
            request.factoryId,
            datetime.utcnow().isoformat(),
            expires_at.isoformat()
        ))
        
        # Log authentication
        log_audit(
            conn,
            request.userId,
            request.role.value,
            Action.LOGIN,
            ObjectType.REQUEST,  # Using REQUEST as placeholder
            "N/A",
            {
                "userId": request.userId,
                "role": request.role.value,
                "factoryId": request.factoryId
            }
        )
    
    return LoginResponse(
        token=token,
        userId=request.userId,
        role=request.role.value,
        factoryId=request.factoryId
    )

@app.post("/evidence", response_model=EvidenceResponse)
async def create_evidence(
    evidence: EvidenceCreate,
    user: Dict[str, Any] = Depends(require_role(Role.FACTORY))
):
    """Create evidence document (Factory only)"""
    evidence_id = generate_id("E")
    version_id = generate_id("V")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create evidence
        cursor.execute("""
            INSERT INTO evidence (id, factory_id, name, doc_type, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            evidence_id,
            user['factoryId'],
            evidence.name,
            evidence.docType,
            datetime.utcnow().isoformat()
        ))
        
        # Create initial version
        cursor.execute("""
            INSERT INTO evidence_versions (id, evidence_id, version_number, expiry, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            version_id,
            evidence_id,
            1,
            evidence.expiry,
            evidence.notes,
            datetime.utcnow().isoformat()
        ))
        
        # Audit log
        log_audit(
            conn,
            user['userId'],
            user['role'],
            Action.CREATE_EVIDENCE,
            ObjectType.EVIDENCE,
            evidence_id,
            {
                "factoryId": user['factoryId'],
                "name": evidence.name,
                "docType": evidence.docType,
                "versionId": version_id
            }
        )
    
    return EvidenceResponse(evidenceId=evidence_id, versionId=version_id)

@app.post("/evidence/{evidence_id}/versions", response_model=EvidenceResponse)
async def add_evidence_version(
    evidence_id: str,
    version: VersionCreate,
    user: Dict[str, Any] = Depends(require_role(Role.FACTORY))
):
    """Add new version to evidence (Factory only)"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify evidence belongs to factory
        cursor.execute("""
            SELECT factory_id FROM evidence WHERE id = ?
        """, (evidence_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Evidence not found")
        
        if row['factory_id'] != user['factoryId']:
            raise HTTPException(status_code=403, detail="Cannot add version to other factory's evidence")
        
        # Get next version number
        cursor.execute("""
            SELECT MAX(version_number) as max_version 
            FROM evidence_versions 
            WHERE evidence_id = ?
        """, (evidence_id,))
        
        max_version = cursor.fetchone()['max_version'] or 0
        new_version_number = max_version + 1
        
        version_id = generate_id("V")
        
        # Create new version
        cursor.execute("""
            INSERT INTO evidence_versions (id, evidence_id, version_number, expiry, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            version_id,
            evidence_id,
            new_version_number,
            version.expiry,
            version.notes,
            datetime.utcnow().isoformat()
        ))
        
        # Audit log
        log_audit(
            conn,
            user['userId'],
            user['role'],
            Action.ADD_VERSION,
            ObjectType.VERSION,
            version_id,
            {
                "factoryId": user['factoryId'],
                "evidenceId": evidence_id,
                "versionNumber": new_version_number
            }
        )
    
    return EvidenceResponse(evidenceId=evidence_id, versionId=version_id)

@app.post("/requests")
async def create_request(
    request: RequestCreate,
    user: Dict[str, Any] = Depends(require_role(Role.BUYER))
):
    """Create evidence request (Buyer only)"""
    request_id = generate_id("R")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create request
        cursor.execute("""
            INSERT INTO requests (id, buyer_id, factory_id, title, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            request_id,
            user['userId'],
            request.factoryId,
            request.title,
            'pending',
            datetime.utcnow().isoformat()
        ))
        
        # Create request items
        item_ids = []
        for item in request.items:
            item_id = generate_id("I")
            item_ids.append(item_id)
            cursor.execute("""
                INSERT INTO request_items (id, request_id, doc_type, status)
                VALUES (?, ?, ?, ?)
            """, (
                item_id,
                request_id,
                item.docType,
                'pending'
            ))
        
        # Audit log
        log_audit(
            conn,
            user['userId'],
            user['role'],
            Action.CREATE_REQUEST,
            ObjectType.REQUEST,
            request_id,
            {
                "buyerId": user['userId'],
                "factoryId": request.factoryId,
                "title": request.title,
                "itemCount": len(request.items),
                "items": [{"docType": item.docType} for item in request.items]
            }
        )
    
    return {
        "requestId": request_id,
        "status": "pending",
        "itemIds": item_ids
    }

@app.get("/factory/requests")
async def get_factory_requests(
    user: Dict[str, Any] = Depends(require_role(Role.FACTORY))
):
    """Get requests for factory (Factory only, filtered by factoryId)"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get requests for this factory only
        cursor.execute("""
            SELECT id, buyer_id, factory_id, title, status, created_at
            FROM requests
            WHERE factory_id = ?
            ORDER BY created_at DESC
        """, (user['factoryId'],))
        
        requests = []
        for row in cursor.fetchall():
            request_id = row['id']
            
            # Get items for this request
            cursor.execute("""
                SELECT id, doc_type, status, evidence_id, version_id, fulfilled_at
                FROM request_items
                WHERE request_id = ?
            """, (request_id,))
            
            items = [dict(item) for item in cursor.fetchall()]
            
            requests.append({
                "requestId": row['id'],
                "buyerId": row['buyer_id'],
                "factoryId": row['factory_id'],
                "title": row['title'],
                "status": row['status'],
                "createdAt": row['created_at'],
                "items": items
            })
    
    return {"requests": requests}

@app.post("/requests/{request_id}/items/{item_id}/fulfill")
async def fulfill_request_item(
    request_id: str,
    item_id: str,
    fulfill: FulfillRequest,
    user: Dict[str, Any] = Depends(require_role(Role.FACTORY))
):
    """Fulfill request item with evidence (Factory only, own factoryId only)"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify request belongs to this factory
        cursor.execute("""
            SELECT factory_id, buyer_id FROM requests WHERE id = ?
        """, (request_id,))
        
        request_row = cursor.fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Request not found")
        
        if request_row['factory_id'] != user['factoryId']:
            raise HTTPException(status_code=403, detail="Cannot fulfill other factory's requests")
        
        # Verify item exists and belongs to request
        cursor.execute("""
            SELECT status, doc_type FROM request_items 
            WHERE id = ? AND request_id = ?
        """, (item_id, request_id))
        
        item_row = cursor.fetchone()
        if not item_row:
            raise HTTPException(status_code=404, detail="Request item not found")
        
        previous_status = item_row['status']
        doc_type = item_row['doc_type']
        
        # Verify evidence belongs to factory
        cursor.execute("""
            SELECT factory_id FROM evidence WHERE id = ?
        """, (fulfill.evidenceId,))
        
        evidence_row = cursor.fetchone()
        if not evidence_row:
            raise HTTPException(status_code=404, detail="Evidence not found")
        
        if evidence_row['factory_id'] != user['factoryId']:
            raise HTTPException(status_code=403, detail="Cannot use other factory's evidence")
        
        # Verify version exists
        cursor.execute("""
            SELECT id FROM evidence_versions 
            WHERE id = ? AND evidence_id = ?
        """, (fulfill.versionId, fulfill.evidenceId))
        
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Evidence version not found")
        
        # Update item
        cursor.execute("""
            UPDATE request_items
            SET status = 'fulfilled',
                evidence_id = ?,
                version_id = ?,
                fulfilled_at = ?
            WHERE id = ?
        """, (
            fulfill.evidenceId,
            fulfill.versionId,
            datetime.utcnow().isoformat(),
            item_id
        ))
        
        # Check if all items fulfilled, update request status
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status = 'fulfilled' THEN 1 ELSE 0 END) as fulfilled
            FROM request_items
            WHERE request_id = ?
        """, (request_id,))
        
        counts = cursor.fetchone()
        if counts['total'] == counts['fulfilled']:
            cursor.execute("""
                UPDATE requests SET status = 'completed' WHERE id = ?
            """, (request_id,))
        
        # Audit log
        log_audit(
            conn,
            user['userId'],
            user['role'],
            Action.FULFILL_ITEM,
            ObjectType.REQUEST_ITEM,
            item_id,
            {
                "factoryId": user['factoryId'],
                "buyerId": request_row['buyer_id'],
                "requestId": request_id,
                "docType": doc_type,
                "evidenceId": fulfill.evidenceId,
                "versionId": fulfill.versionId,
                "previousStatus": previous_status,
                "newStatus": "fulfilled"
            }
        )
    
    return {
        "success": True,
        "itemId": item_id,
        "status": "fulfilled"
    }

@app.get("/audit", response_model=List[AuditEntry])
async def get_audit_log(
    limit: int = 100,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Get audit log entries"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, actor_user_id, actor_role, action, object_type, object_id, metadata
            FROM audit_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        entries = []
        for row in cursor.fetchall():
            entries.append(AuditEntry(
                id=row['id'],
                timestamp=row['timestamp'],
                actorUserId=row['actor_user_id'],
                actorRole=row['actor_role'],
                action=row['action'],
                objectType=row['object_type'],
                objectId=row['object_id'],
                metadata=json.loads(row['metadata'])
            ))
    
    return entries

@app.get("/")
async def root():
    """API root"""
    return {
        "name": "Buyer Request Workflow API",
        "version": "1.0",
        "endpoints": {
            "auth": "POST /auth/login",
            "evidence": "POST /evidence, POST /evidence/{id}/versions",
            "requests": "POST /requests, GET /factory/requests, POST /requests/{rid}/items/{iid}/fulfill",
            "audit": "GET /audit"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
