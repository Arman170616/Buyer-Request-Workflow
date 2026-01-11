# Top 3 Risks & Mitigation Strategies
## Task AA: Buyer Request Workflow + Audit Log API

---

## Risk 1: Access Control Vulnerabilities Lead to Data Leaks 🔒

### Risk Level: **CRITICAL**
- **Likelihood**: Medium (40%)
- **Impact**: Critical (legal liability, compliance breach)
- **Business Impact**: GDPR fines up to €20M, customer loss

### Description
A bug in role-based access control could allow:
- Buyer A viewing Buyer B's requests
- Factory A accessing Factory B's evidence  
- Buyers creating evidence (role violation)
- Factories fulfilling other factories' requests

### Root Causes
1. Insufficient input validation
2. Complex permission logic with edge cases
3. Parameter tampering opportunities
4. Incomplete security testing
5. Stale sessions after role changes

### Mitigation Strategies

**1. Defense in Depth - Multiple Security Layers**
- Authentication middleware validates tokens
- Role dependencies enforce buyer/factory separation
- Resource ownership verification before operations
- Audit logging of all access attempts

**2. Comprehensive Security Test Suite**
```python
def test_buyer_cannot_create_evidence():
    response = client.post("/evidence",
        headers={"Authorization": buyer_token},
        json={"name": "Evidence", "docType": "Report"})
    assert response.status_code == 403

def test_factory_isolation():
    # Factory A cannot see Factory B's requests
    requests = get_factory_requests(factory_a_token)
    assert all(r["factoryId"] == "F001" for r in requests)
```

**3. Security Code Review Process**
- All access control code requires 2+ approvals
- Security checklist in PR template
- Static analysis (Bandit) in CI/CD

**4. Monitor Suspicious Activity**
- Alert on >10 access denials per user per hour
- Track parameter tampering attempts
- Real-time security dashboard

**5. Regular Penetration Testing**
- Quarterly security audits
- Automated vulnerability scanning
- Bug bounty program (production)

---

## Risk 2: Audit Log Data Loss or Corruption 📝

### Risk Level: **HIGH**
- **Likelihood**: Medium (30%)
- **Impact**: High (compliance failure, forensics impossible)
- **Business Impact**: Failed audits, regulatory penalties

### Description
The audit log is critical for compliance, forensics, and debugging. Loss could occur due to:
- Database crash during write
- Disk full (SQLite limitations)
- Accidental deletion
- Performance degradation from growth

### Root Causes
1. Single point of failure (SQLite file)
2. No automated backups
3. Unbounded growth without archival
4. Write performance bottlenecks
5. No redundancy

### Mitigation Strategies

**1. Multi-Destination Audit Logging**
```python
def log_action(entry):
    # Primary: Database (for queries)
    db.session.add(entry)
    db.session.commit()
    
    # Secondary: File (for backup)
    append_to_file('/var/log/audit.jsonl', entry)
    
    # Tertiary: Remote logging (Datadog/Splunk)
    datadog.log(entry)
    
    # Quaternary: S3 (long-term storage)
    s3.upload(f"audit/{entry.id}.json", entry)
```

**2. Automated Backup Strategy**
- Backup database every 6 hours
- Verify backup integrity with SQLite PRAGMA
- Upload to S3 for off-site storage
- Retain local 7 days, S3 90 days

**3. Archive Old Data**
```python
# Monthly: Archive logs >90 days old
old_logs = query(AuditLog).filter(timestamp < cutoff)
export_to_jsonl(old_logs, "archive.jsonl")
upload_to_s3_glacier("archive.jsonl")
delete_from_database(old_logs)
```

**4. Read-Only Access Controls**
- Prevent accidental deletion
- Application-level immutability enforcement
- Database-level read-only user for queries

**5. Health Monitoring**
- Alert if no logs in last hour (system down?)
- Monitor database size (approaching limits?)
- Track write latency (<1 second target)

---

## Risk 3: Scalability Bottlenecks Under Load ⚡

### Risk Level: **MEDIUM**
- **Likelihood**: High (60%)  
- **Impact**: Medium (degraded performance, poor UX)
- **Business Impact**: User churn, SLA violations

### Description
Under high load (100+ concurrent users):
- SQLite single-writer bottleneck
- API timeouts from slow queries
- Memory issues from large result sets
- Audit log writes slow down requests

**Scenario**: 200 buyers create requests simultaneously → 2,000 database writes → SQLite serializes → timeouts

### Root Causes
1. SQLite single-writer limitation
2. Synchronous request processing
3. No caching layer
4. Missing database indexes
5. No rate limiting

### Mitigation Strategies

**1. Migrate to PostgreSQL**
```python
# Connection pooling
engine = create_engine(DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600)
```
Benefits: Multiple writers, better concurrency, replication

**2. Implement Redis Caching**
```python
# Cache frequently accessed data
@app.get("/factory/requests")
async def get_requests(user):
    cache_key = f"requests:{user.org_id}"
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Query database, cache for 5 minutes
    data = query_database()
    redis.setex(cache_key, 300, json.dumps(data))
    return data
```
Benefit: 80%+ reduction in database load

**3. Add Database Indexes**
```sql
CREATE INDEX idx_evidence_factory_id ON evidence(factory_id);
CREATE INDEX idx_requests_factory_id ON requests(factory_id);
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);
```
Before: 500ms queries → After: <50ms queries

**4. Rate Limiting**
```python
@limiter.limit("10/minute")  # Per IP
@app.post("/requests")
async def create_request():
    pass
```
Prevents abuse and ensures fair usage

**5. Async Background Jobs**
```python
@celery.task
def send_notification(request_id):
    # Non-blocking email sending
    send_email(...)

@app.post("/requests")
async def create_request():
    # Create request
    request = Request(...)
    db.commit()
    
    # Send notification async
    send_notification.delay(request.id)
    return {"requestId": request.id}
```

---

## Summary

| Risk | Likelihood | Impact | Priority | Key Mitigation |
|------|------------|--------|----------|----------------|
| Access Control | 40% | Critical | **1** | Defense in depth + testing |
| Audit Log Loss | 30% | High | **2** | Multi-destination + backups |
| Scalability | 60% | Medium | **3** | PostgreSQL + caching + indexes |

## Implementation Roadmap

**Immediate** (Before Production):
- Security test suite (Risk 1)
- Database backups (Risk 2)  
- Basic indexes (Risk 3)

**Short-term** (First Month):
- PostgreSQL migration (Risk 3)
- Redis caching (Risk 3)
- Multi-destination logging (Risk 2)

**Ongoing**:
- Security audits (Risk 1)
- Performance monitoring (Risk 3)
- Capacity planning (Risk 2, 3)

---

**Document Version**: 1.0  
**Date**: January 11, 2025
