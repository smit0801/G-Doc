# Architecture Deep Dive

## System Components

### 1. Frontend (React + Monaco Editor)

**Purpose**: Provide rich code editing experience with real-time collaboration

**Key Technologies**:
- React 18 for UI framework
- Monaco Editor (VS Code's editor) for code editing
- Yjs for CRDT state management
- WebSocket API for real-time communication

**Responsibilities**:
- Render code editor with syntax highlighting
- Manage WebSocket connection to backend
- Display active users and their cursors
- Handle local edits and broadcast to server
- Apply remote updates from other users

### 2. Backend (Python + FastAPI)

**Purpose**: Handle WebSocket connections, broadcast updates, and manage state

**Key Technologies**:
- FastAPI for async HTTP and WebSocket support
- SQLAlchemy for database ORM
- Redis for pub/sub messaging
- JWT for authentication

**Responsibilities**:
- Accept and manage WebSocket connections
- Broadcast document updates to connected clients
- Publish updates to Redis for other server instances
- Persist documents to PostgreSQL
- Handle user authentication

### 3. Redis (Pub/Sub)

**Purpose**: Enable horizontal scaling by broadcasting messages across server instances

**How it works**:
1. Each backend instance subscribes to channels for active documents
2. When a user makes an edit, the backend publishes to Redis
3. All subscribed backend instances receive the message
4. Each instance broadcasts to its connected WebSocket clients

**Benefits**:
- Stateless backends (can scale horizontally)
- Sub-millisecond message propagation
- Automatic cleanup when backends disconnect

### 4. PostgreSQL

**Purpose**: Persistent storage for documents, users, and sessions

**Schema**:
```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Documents table
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    yjs_state TEXT,
    owner_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_public BOOLEAN DEFAULT TRUE
);

-- Sessions table (for tracking active editing)
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    user_id INTEGER REFERENCES users(id),
    connected_at TIMESTAMP DEFAULT NOW(),
    disconnected_at TIMESTAMP
);
```

## Message Flow

### Scenario: User A types in the editor

```
1. User A types "hello"
   ↓
2. React component captures change
   ↓
3. WebSocket.send({type: "update", data: {content: "hello"}})
   ↓
4. Backend receives WebSocket message
   ↓
5. Backend broadcasts to all local connections (User B)
   ↓
6. Backend publishes to Redis: PUBLISH document:123 {...}
   ↓
7. Other backend instances receive from Redis
   ↓
8. Other backends broadcast to their connections (User C)
   ↓
9. All users see "hello" in < 100ms
```

## Conflict Resolution Strategy

### Problem: Two users edit at the same position simultaneously

**Traditional Approach (Operational Transforms)**:
- Complex transformation functions
- Difficult to implement correctly
- Order-dependent operations

**Our Approach (CRDT-inspired)**:
- Last-write-wins for simplicity (demo version)
- Each edit has a timestamp
- Clients merge updates based on timestamps
- Can be extended to full CRDT with Yjs

**Future Enhancement**:
- Implement full Yjs CRDT integration
- Character-level conflict resolution
- Preserve all edits with automatic merging

## Scalability

### Current Capacity
- **Single Backend**: ~500 concurrent connections
- **Multiple Backends**: Linear scaling with Redis
- **Database**: Millions of documents

### Scaling Strategies

#### 1. Horizontal Scaling (Recommended)

```
Add more backend instances:
- Deploy 3-5 backend instances
- Use Nginx/HAProxy load balancer
- Redis handles message distribution
- Each instance maintains ~500 connections
- Total capacity: 1500-2500 users
```

#### 2. Document Sharding

```
Distribute documents across instances:
- Hash document_id to assign to specific backend
- Reduces Redis message overhead
- Requires consistent hashing for failover
```

#### 3. Read Replicas

```
Separate read and write paths:
- Primary backend for WebSocket writes
- Read replicas for REST API queries
- PostgreSQL replication
```

## Performance Optimization

### Current Optimizations

1. **WebSocket Connection Pooling**
   - Reuse connections across documents
   - Reduce handshake overhead

2. **Redis Pipelining**
   - Batch multiple pub/sub operations
   - Reduce network round-trips

3. **Async/Await**
   - Non-blocking I/O throughout stack
   - Handle thousands of connections per process

4. **Connection Manager**
   - Efficient dictionary lookups O(1)
   - Cleanup disconnected clients automatically

### Future Optimizations

1. **Message Compression**
   - gzip WebSocket messages
   - Reduce bandwidth by 60-80%

2. **Differential Sync**
   - Send only character diffs
   - Reduce message size by 90%

3. **Caching**
   - Redis cache for frequently accessed documents
   - Reduce PostgreSQL load

4. **CDN**
   - Serve frontend assets from CDN
   - Reduce server load

## Monitoring & Observability

### Key Metrics to Track

1. **WebSocket Metrics**
   - Active connections count
   - Messages per second
   - Average message latency
   - Reconnection rate

2. **Redis Metrics**
   - Pub/sub channel count
   - Message throughput
   - Memory usage

3. **Database Metrics**
   - Query latency
   - Connection pool usage
   - Slow queries

4. **Application Metrics**
   - Active documents
   - Users per document
   - Edit frequency

### Recommended Tools

- **Prometheus + Grafana**: Metrics visualization
- **ELK Stack**: Log aggregation
- **Sentry**: Error tracking
- **Jaeger**: Distributed tracing

## Security Considerations

### Current Implementation

1. **JWT Authentication**
   - Secure token-based auth
   - 7-day token expiration

2. **Password Hashing**
   - bcrypt with salt
   - Resistant to rainbow tables

3. **CORS Protection**
   - Whitelist allowed origins
   - Prevent CSRF attacks

### Production Hardening

1. **Rate Limiting**
   - Prevent message flooding
   - Per-user and per-IP limits

2. **Input Validation**
   - Sanitize all user inputs
   - Prevent injection attacks

3. **TLS/SSL**
   - Encrypt all WebSocket traffic
   - Use wss:// instead of ws://

4. **Access Control**
   - Document-level permissions
   - Owner/editor/viewer roles

## Deployment Options

### 1. Docker Compose (Development)
```bash
docker-compose up
```

### 2. Kubernetes (Production)
```yaml
# k8s deployment with:
# - 3 backend replicas
# - Redis cluster (3 nodes)
# - PostgreSQL with replication
# - Nginx ingress controller
```

### 3. Cloud Services
- **AWS**: ECS + ElastiCache + RDS
- **GCP**: Cloud Run + Memorystore + Cloud SQL
- **Azure**: Container Instances + Cache + Database

## Cost Estimation

### Small Scale (100 users)
- 1 Backend: $10/month (1GB RAM)
- Redis: $10/month (shared instance)
- PostgreSQL: $15/month (small DB)
- **Total: ~$35/month**

### Medium Scale (1000 users)
- 3 Backends: $60/month (2GB RAM each)
- Redis: $50/month (dedicated)
- PostgreSQL: $100/month (replicated)
- Load Balancer: $20/month
- **Total: ~$230/month**

### Large Scale (10,000+ users)
- 10 Backends: $400/month
- Redis Cluster: $300/month
- PostgreSQL: $500/month
- CDN: $50/month
- Monitoring: $100/month
- **Total: ~$1,350/month**
