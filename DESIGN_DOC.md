# Task AA: Buyer Request Workflow + Audit Log - Design Document

## System Overview

A role-based workflow API that enables buyers to request evidence from factories and factories to fulfill those requests, with comprehensive audit logging of all actions.

---

## Stack Choice

**Backend**: FastAPI (Python 3.8+)
- High-performance async framework
- Auto-generated OpenAPI/Swagger documentation
- Built-in request validation via Pydantic
- Excellent for rapid development

**Database**: SQLite
- Zero-configuration for demo/assessment
- ACID compliance for data integrity
- Easy migration path to PostgreSQL for production
- Sufficient for thousands of transactions

**Authentication**: Token-based (JWT-like)
- Simple bearer token implementation
- 24-hour expiry with configurable timeout
- Easily upgradeable to full OAuth2/JWT

**Why This Stack?**
- Fast to implement and demonstrate
- Production-ready patterns (just swap SQLite → PostgreSQL)
- Clear, maintainable code
- Industry-standard technologies

---

## Data Model

### Core Entities

**auth_tokens**
- Manages authentication sessions
- Links: → users (via user_id)

**evidence** 
- Evidence documents owned by factories
- Links: → organizations (via factory_id)

**evidence_versions**
- Version history for evidence documents
- Links: → evidence (via evidence_id)

**requests**
- Evidence requests from buyers to factories
- Links: → organizations (via buyer_id, factory_id)

**request_items**
- Individual evidence items within a request
- Links: → requests, → evidence_versions (when fulfilled)

**audit_log**
- Immutable record of all system actions
- No foreign keys (historical record, entities may be deleted)

### Key Relationships
```
Buyer (Organization) 1:N Requests
Factory (Organization) 1:N Evidence
Request 1:N RequestItems
Evidence 1:N EvidenceVersions
RequestItem N:1 EvidenceVersion (when fulfilled)
```

---

## Security Architecture

### Role-Based Access Control (RBAC)

**Buyer Permissions:**
-  Create requests for any factory
-  View their own requests
-  View audit log
-  Cannot create evidence
-  Cannot fulfill requests

**Factory Permissions:**
-  Create evidence documents
-  Add versions to their own evidence
-  View requests assigned to their factory
-  Fulfill items using their own evidence
-  View audit log
-  Cannot see other factories' evidence
-  Cannot fulfill other factories' requests

### Enforcement Layers

1. **Authentication Middleware**: Validates token on every request
2. **Role Dependencies**: FastAPI dependencies enforce buyer/factory roles
3. **Data Isolation**: SQL queries filter by organization ID
4. **Business Logic**: Double-check ownership before mutations

### Access Control Flow
```
Request → Validate Token → Extract User Context → Check Role → Verify Ownership → Execute → Audit Log
```

---

## Audit Logging System

### Requirements Met

Every action writes an audit record containing:
- **timestamp**: ISO 8601 format
- **actorUserId**: Who performed the action
- **actorRole**: buyer or factory
- **action**: CREATE_REQUEST, CREATE_EVIDENCE, ADD_VERSION, FULFILL_ITEM, LOGIN
- **objectType**: Request, Evidence, Version, RequestItem
- **objectId**: UUID of affected resource
- **metadata**: JSON with context (factoryId, buyerId, status changes, etc.)

### Immutability

Audit log is append-only:
- No UPDATE or DELETE operations
- Historical record preserved even if entities deleted
- Suitable for compliance and forensics

### State Transitions Tracked

Example metadata for FULFILL_ITEM:
```json
{
  "factoryId": "F001",
  "buyerId": "B001",
  "requestId": "R123",
  "evidenceId": "E456",
  "versionId": "V789",
  "previousStatus": "pending",
  "newStatus": "fulfilled"
}
```

---

## API Design

### RESTful Principles

- Resource-oriented URLs (`/evidence`, `/requests`)
- HTTP verbs for actions (POST, GET)
- Proper status codes (200, 201, 400, 401, 403, 404)
- JSON request/response bodies
- Bearer token authentication

### Error Handling

- 400: Validation errors (missing fields, invalid format)
- 401: Authentication required or token expired
- 403: Forbidden (role or ownership violation)
- 404: Resource not found
- 500: Server errors (logged for debugging)

### Endpoint Summary

| Endpoint | Method | Auth | Role | Purpose |
|----------|--------|------|------|---------|
| /auth/login | POST | None | - | Authenticate user |
| /evidence | POST | Required | Factory | Create evidence |
| /evidence/:id/versions | POST | Required | Factory | Add version |
| /requests | POST | Required | Buyer | Create request |
| /factory/requests | GET | Required | Factory | View assigned requests |
| /requests/:id/items/:id/fulfill | POST | Required | Factory | Fulfill item |
| /audit | GET | Required | Any | View audit log |

---

## Workflow Example

1. **Factory Login**
   ```
   POST /auth/login → token
   ```

2. **Factory Creates Evidence**
   ```
   POST /evidence → evidenceId, versionId
   Audit: CREATE_EVIDENCE
   ```

3. **Buyer Login**
   ```
   POST /auth/login → token
   ```

4. **Buyer Creates Request**
   ```
   POST /requests → requestId, itemIds
   Audit: CREATE_REQUEST
   ```

5. **Factory Views Requests**
   ```
   GET /factory/requests → [requests for this factory only]
   ```

6. **Factory Fulfills Item**
   ```
   POST /requests/:id/items/:id/fulfill → success
   Audit: FULFILL_ITEM (tracks status: pending → fulfilled)
   ```

7. **Anyone Views Audit Trail**
   ```
   GET /audit → [all actions with full context]
   ```

---

## Testing Strategy

### Unit Tests
- Model validation (Pydantic)
- Business logic functions
- Access control checks

### Integration Tests
- Full request/response cycle
- Database transactions
- Token authentication

### Security Tests
- Cross-factory access prevention
- Buyer cannot create evidence
- Factory cannot see other factories' requests
- Token expiry enforcement



---

## Scalability Considerations

### Current Design (Assessment Scope)
- Single-process FastAPI server
- SQLite database
- Synchronous processing
- In-memory session storage

### Production Scaling Path
1. **Horizontal Scaling**: Stateless API → multiple instances behind load balancer
2. **Database**: SQLite → PostgreSQL with connection pooling
3. **Caching**: Redis for session/token cache
4. **Async Processing**: Celery for background jobs (if needed)
5. **Storage**: File uploads → S3/CloudFront
6. **Monitoring**: APM tools (Datadog, Sentry)

### Performance Targets
- API response time: <200ms (p95)
- Concurrent users: 100+ (with PostgreSQL)
- Audit log writes: <50ms (indexed on timestamp, actorUserId)

---

## Production Readiness Checklist

**Security**
- [ ] OAuth2/JWT with proper signing
- [ ] HTTPS/TLS encryption
- [ ] Rate limiting middleware
- [ ] Input sanitization (already has Pydantic validation)
- [ ] Audit logging

**Operations**
- [ ] Database migrations (Alembic)
- [ ] Health check endpoints
- [ ] Structured logging (JSON)
- [ ] Metrics export (Prometheus)
- [ ] Error tracking (Sentry)

**Infrastructure**
- [ ] Docker containerization
- [ ] Kubernetes deployment
- [ ] CI/CD pipeline
- [ ] Automated testing
- [ ] Database backups



---

## Document Summary

This design implements a secure, auditable workflow system with:
- **Clear separation of concerns** between buyers and factories
- **Defense in depth** security (authentication, authorization, data isolation)
- **Complete audit trail** for compliance and debugging
- **Production-ready patterns** that scale from demo to enterprise



---
