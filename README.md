# Task AA: Buyer Request Workflow + Audit Log API

## Overview

A FastAPI-based REST API implementing a buyer-factory request workflow with comprehensive audit logging and role-based access control. The system enforces strict security rules:

- **Buyers** can create requests but cannot create evidence or fulfill requests
- **Factories** can create evidence and fulfill requests, but only for their own factory
- All actions are logged to an immutable audit trail

## Stack

- **Backend**: Python 3.8+ with FastAPI
- **Database**: SQLite (in-memory or file-based)
- **Auth**: JWT-like token system with expiry
- **Server**: Uvicorn ASGI server

## Setup & Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Server

```bash
python main.py
```

The API will start on `http://localhost:8000`

### 3. View API Documentation

Open browser: `http://localhost:8000/docs` (Swagger UI)

## Database Schema

The system automatically initializes the following tables:

- `audit_log` - Immutable audit trail
- `evidence` - Evidence documents created by factories
- `evidence_versions` - Version history for evidence
- `requests` - Buyer requests for evidence
- `request_items` - Individual items in requests
- `auth_tokens` - Authentication tokens

## API Endpoints & Usage

### 1. Authentication

#### Login as Buyer

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "buyer1",
    "role": "buyer"
  }'
```

**Response:**
```json
{
  "token": "abc123...",
  "userId": "buyer1",
  "role": "buyer",
  "factoryId": null
}
```

#### Login as Factory

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "factory_user1",
    "role": "factory",
    "factoryId": "F001"
  }'
```

**Response:**
```json
{
  "token": "xyz789...",
  "userId": "factory_user1",
  "role": "factory",
  "factoryId": "F001"
}
```

**Note:** Save the token for subsequent requests. Replace `YOUR_TOKEN` in examples below.

---

### 2. Evidence Management (Factory Only)

#### Create Evidence

```bash
curl -X POST http://localhost:8000/evidence \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_FACTORY_TOKEN" \
  -d '{
    "name": "Q1 Safety Test Report",
    "docType": "Test Report",
    "expiry": "2025-12-31",
    "notes": "Annual safety compliance test"
  }'
```

**Response:**
```json
{
  "evidenceId": "E1A2B3C4",
  "versionId": "V5D6E7F8"
}
```

#### Add New Version to Evidence

```bash
curl -X POST http://localhost:8000/evidence/E1A2B3C4/versions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_FACTORY_TOKEN" \
  -d '{
    "notes": "Updated test results with new equipment",
    "expiry": "2026-06-30"
  }'
```

**Response:**
```json
{
  "evidenceId": "E1A2B3C4",
  "versionId": "V9A0B1C2"
}
```

**Security:** Factory can only add versions to their own evidence.

---

### 3. Request Workflow

#### Create Request (Buyer Only)

```bash
curl -X POST http://localhost:8000/requests \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_BUYER_TOKEN" \
  -d '{
    "factoryId": "F001",
    "title": "Q1 2025 Compliance Evidence",
    "items": [
      {"docType": "Test Report"},
      {"docType": "Certificate"},
      {"docType": "Inspection Report"}
    ]
  }'
```

**Response:**
```json
{
  "requestId": "R3D4E5F6",
  "status": "pending",
  "itemIds": ["I7G8H9I0", "I1J2K3L4", "I5M6N7O8"]
}
```

#### Get Factory Requests (Factory Only)

```bash
curl -X GET http://localhost:8000/factory/requests \
  -H "Authorization: Bearer YOUR_FACTORY_TOKEN"
```

**Response:**
```json
{
  "requests": [
    {
      "requestId": "R3D4E5F6",
      "buyerId": "buyer1",
      "factoryId": "F001",
      "title": "Q1 2025 Compliance Evidence",
      "status": "pending",
      "createdAt": "2025-01-11T10:30:00",
      "items": [
        {
          "id": "I7G8H9I0",
          "doc_type": "Test Report",
          "status": "pending",
          "evidence_id": null,
          "version_id": null,
          "fulfilled_at": null
        },
        {
          "id": "I1J2K3L4",
          "doc_type": "Certificate",
          "status": "pending",
          "evidence_id": null,
          "version_id": null,
          "fulfilled_at": null
        }
      ]
    }
  ]
}
```

**Security:** Factory only sees requests for their own factoryId.

#### Fulfill Request Item (Factory Only)

```bash
curl -X POST http://localhost:8000/requests/R3D4E5F6/items/I7G8H9I0/fulfill \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_FACTORY_TOKEN" \
  -d '{
    "evidenceId": "E1A2B3C4",
    "versionId": "V5D6E7F8"
  }'
```

**Response:**
```json
{
  "success": true,
  "itemId": "I7G8H9I0",
  "status": "fulfilled"
}
```

**Security:** 
- Factory can only fulfill requests for their own factoryId
- Factory can only use their own evidence
- Request status automatically updates to "completed" when all items fulfilled

---

### 4. Audit Log

#### Get Audit Entries

```bash
curl -X GET "http://localhost:8000/audit?limit=50" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
[
  {
    "id": 15,
    "timestamp": "2025-01-11T10:35:22.123456",
    "actorUserId": "factory_user1",
    "actorRole": "factory",
    "action": "FULFILL_ITEM",
    "objectType": "RequestItem",
    "objectId": "I7G8H9I0",
    "metadata": {
      "factoryId": "F001",
      "buyerId": "buyer1",
      "requestId": "R3D4E5F6",
      "docType": "Test Report",
      "evidenceId": "E1A2B3C4",
      "versionId": "V5D6E7F8",
      "previousStatus": "pending",
      "newStatus": "fulfilled"
    }
  },
  {
    "id": 14,
    "timestamp": "2025-01-11T10:30:15.654321",
    "actorUserId": "buyer1",
    "actorRole": "buyer",
    "action": "CREATE_REQUEST",
    "objectType": "Request",
    "objectId": "R3D4E5F6",
    "metadata": {
      "buyerId": "buyer1",
      "factoryId": "F001",
      "title": "Q1 2025 Compliance Evidence",
      "itemCount": 3,
      "items": [
        {"docType": "Test Report"},
        {"docType": "Certificate"},
        {"docType": "Inspection Report"}
      ]
    }
  }
]
```

**Audit Actions Logged:**
- `LOGIN` - User authentication
- `CREATE_REQUEST` - Buyer creates request
- `CREATE_EVIDENCE` - Factory creates evidence
- `ADD_VERSION` - Factory adds version to evidence
- `FULFILL_ITEM` - Factory fulfills request item

---

## Complete Workflow Example

### Step 1: Setup Actors

```bash
# Login as Buyer
BUYER_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"userId":"buyer1","role":"buyer"}' | jq -r '.token')

# Login as Factory F001
FACTORY_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"userId":"factory_user1","role":"factory","factoryId":"F001"}' | jq -r '.token')

echo "Buyer Token: $BUYER_TOKEN"
echo "Factory Token: $FACTORY_TOKEN"
```

### Step 2: Factory Creates Evidence

```bash
# Create test report evidence
EVIDENCE=$(curl -s -X POST http://localhost:8000/evidence \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FACTORY_TOKEN" \
  -d '{
    "name": "Annual Safety Test",
    "docType": "Test Report",
    "expiry": "2025-12-31",
    "notes": "Comprehensive safety testing"
  }')

EVIDENCE_ID=$(echo $EVIDENCE | jq -r '.evidenceId')
VERSION_ID=$(echo $EVIDENCE | jq -r '.versionId')

echo "Created Evidence: $EVIDENCE_ID (Version: $VERSION_ID)"
```

### Step 3: Buyer Creates Request

```bash
# Create request for factory F001
REQUEST=$(curl -s -X POST http://localhost:8000/requests \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BUYER_TOKEN" \
  -d '{
    "factoryId": "F001",
    "title": "Q1 Compliance Check",
    "items": [
      {"docType": "Test Report"},
      {"docType": "Certificate"}
    ]
  }')

REQUEST_ID=$(echo $REQUEST | jq -r '.requestId')
ITEM_ID=$(echo $REQUEST | jq -r '.itemIds[0]')

echo "Created Request: $REQUEST_ID"
echo "First Item: $ITEM_ID"
```

### Step 4: Factory Views and Fulfills Request

```bash
# View requests
curl -s -X GET http://localhost:8000/factory/requests \
  -H "Authorization: Bearer $FACTORY_TOKEN" | jq

# Fulfill first item
curl -s -X POST http://localhost:8000/requests/$REQUEST_ID/items/$ITEM_ID/fulfill \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FACTORY_TOKEN" \
  -d "{
    \"evidenceId\": \"$EVIDENCE_ID\",
    \"versionId\": \"$VERSION_ID\"
  }" | jq
```

### Step 5: View Audit Trail

```bash
# Get audit log
curl -s -X GET "http://localhost:8000/audit?limit=20" \
  -H "Authorization: Bearer $BUYER_TOKEN" | jq
```

---

## Security Features

### Role-Based Access Control

| Endpoint | Buyer | Factory |
|----------|-------|---------|
| POST /evidence | ❌ | ✅ |
| POST /evidence/:id/versions | ❌ | ✅ |
| POST /requests | ✅ | ❌ |
| GET /factory/requests | ❌ | ✅ (own factory only) |
| POST /requests/:rid/items/:iid/fulfill | ❌ | ✅ (own factory only) |
| GET /audit | ✅ | ✅ |

### Security Rules Enforced

1. **Buyer Restrictions:**
   - Cannot create or modify evidence
   - Cannot fulfill request items
   - Cannot access factory-specific endpoints

2. **Factory Restrictions:**
   - Can only see requests for their own factoryId
   - Can only fulfill items in requests for their own factoryId
   - Can only use their own evidence to fulfill requests
   - Can only add versions to their own evidence

3. **Audit Integrity:**
   - All actions logged with actor, timestamp, and metadata
   - Includes state transitions (previousStatus → newStatus)
   - Immutable append-only log

---

## Testing Negative Cases

### Buyer Cannot Create Evidence

```bash
curl -X POST http://localhost:8000/evidence \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BUYER_TOKEN" \
  -d '{"name":"Test","docType":"Report","notes":"Test"}'

# Expected: 403 Forbidden
```

### Factory Cannot See Other Factory's Requests

```bash
# Login as Factory F002
FACTORY2_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"userId":"factory_user2","role":"factory","factoryId":"F002"}' | jq -r '.token')

# Try to access F001's requests - will return empty array
curl -X GET http://localhost:8000/factory/requests \
  -H "Authorization: Bearer $FACTORY2_TOKEN"

# Expected: {"requests": []} (no requests for F002)
```

### Factory Cannot Fulfill Other Factory's Requests

```bash
# Try to fulfill F001's request with F002's token
curl -X POST http://localhost:8000/requests/$REQUEST_ID/items/$ITEM_ID/fulfill \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FACTORY2_TOKEN" \
  -d '{"evidenceId":"E123","versionId":"V456"}'

# Expected: 403 Forbidden - Cannot fulfill other factory's requests
```

---

## Architecture Highlights

### Audit Logging
Every endpoint that modifies data automatically writes to the audit log with:
- Actor information (userId, role)
- Action type (CREATE_REQUEST, FULFILL_ITEM, etc.)
- Object details (type, ID)
- Rich metadata including state transitions

### Database Design
- Normalized schema with foreign keys
- Evidence versioning support
- Request/item relationship for granular tracking
- Token-based authentication with expiry

### Error Handling
- 400: Bad Request (validation errors)
- 401: Unauthorized (missing/invalid token)
- 403: Forbidden (role violations, cross-factory access)
- 404: Not Found (resource doesn't exist)

---

## Development

### Run Tests

```bash
# Install test dependencies
pip install pytest httpx

# Run tests
pytest test_main.py
```

### Reset Database

```bash
rm workflow.db
python main.py
```

---

## Production Considerations

For production deployment, consider:

1. **Authentication**: Replace simple tokens with OAuth2/JWT with proper signing
2. **Database**: Migrate to PostgreSQL for production workloads
3. **Encryption**: Add TLS/HTTPS for API endpoints
4. **Rate Limiting**: Implement rate limiting per user/IP
5. **Audit Retention**: Archive old audit logs to cold storage
6. **Monitoring**: Add APM tools (Datadog, New Relic)
7. **Validation**: Add more comprehensive input validation
8. **CORS**: Configure CORS for frontend integration

---

# Buyer-Request-Workflow
