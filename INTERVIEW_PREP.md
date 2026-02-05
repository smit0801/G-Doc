# 🎤 Interview Prep Guide - Collaborative Editor Project

## Deep-Dive Questions You Should Be Ready For

### 1. System Design Questions

#### Q: "Walk me through your architecture."

**Good Answer:**
> "The system has four main components. The frontend is React with Monaco Editor for the code editing interface. Users connect via WebSockets to a FastAPI backend. The backend uses a ConnectionManager class to handle WebSocket connections and broadcast updates. 
>
> For horizontal scaling, I integrated Redis pub/sub. When a user makes an edit, the backend broadcasts it locally and publishes to a Redis channel. Other backend instances subscribed to that channel receive the update and forward it to their connected clients. This makes the backends stateless.
>
> PostgreSQL stores document content and user data. I chose it for ACID compliance and because document data fits well in a relational model."

**Follow-up they might ask:** "Why not use MongoDB?"
> "MongoDB would work, but I chose PostgreSQL because document collaboration often needs transactional consistency - like ensuring a save operation completes fully or not at all. PostgreSQL's JSONB support also gives me flexibility for semi-structured data while maintaining referential integrity for users and documents."

---

#### Q: "How does your system handle conflicts when two users edit the same part simultaneously?"

**Good Answer:**
> "Currently, I use a last-write-wins strategy with timestamps. Each edit includes a timestamp, and updates are applied in order. This is simple but can lose edits in rare cases.
>
> For production, I'd implement full CRDTs - Conflict-free Replicated Data Types. The Yjs library I included provides this. CRDTs work by assigning unique identifiers to each character and position, so concurrent edits can be merged deterministically without coordination.
>
> The trade-off is complexity - CRDTs require more memory and bandwidth because each character has metadata. For this MVP, I prioritized getting the distributed architecture right, but the system is designed to swap in proper CRDTs."

**Red flag answer (avoid):**
> "I haven't really thought about conflicts, the WebSocket broadcasts should handle it."

---

#### Q: "How would you scale this to 10,000 concurrent users?"

**Good Answer:**
> "I'd approach it in stages:
>
> **Phase 1 (500-1000 users):** Add 2-3 backend instances behind Nginx load balancer. Redis pub/sub handles cross-instance messaging. This gets us to ~1500 users.
>
> **Phase 2 (1000-5000 users):** Implement document sharding - hash document IDs to specific backend instances. This reduces Redis traffic since not all backends need all messages. Add read replicas for the REST API.
>
> **Phase 3 (5000-10000 users):** Move to a geographically distributed setup. Deploy in multiple regions with regional Redis clusters. Use global load balancing to route users to nearest region. Implement message compression and differential sync to reduce bandwidth.
>
> I'd also add monitoring at each phase - track WebSocket connections, message latency, Redis throughput, and database query times to identify bottlenecks."

**Metrics to mention:**
- Current: ~500 connections per backend instance
- Redis: <1ms pub/sub latency
- WebSocket: <100ms end-to-end latency
- Database: <50ms query time for document loads

---

### 2. Implementation Questions

#### Q: "Show me the code for your WebSocket connection manager."

**What they're testing:** Can you explain your own code?

**Be ready to:**
1. Walk through `websocket_manager.py`
2. Explain the `active_connections` data structure
3. Describe how `broadcast_to_document()` works
4. Explain the Redis pub/sub integration

**Key points to hit:**
```python
# "I use a nested dictionary to organize connections by document"
self.active_connections: Dict[str, Dict[str, WebSocket]]
# document_id -> user_id -> WebSocket

# "When broadcasting, I send to local connections first"
for user_id, connection in self.active_connections[document_id].items():
    await connection.send_json(message)

# "Then publish to Redis for other servers"
await self.redis.publish(f"document:{document_id}", message)

# "The Redis listener runs in a separate async task"
asyncio.create_task(self._redis_listener(document_id))
```

---

#### Q: "How do you handle disconnections?"

**Good Answer:**
> "I handle disconnections at multiple levels:
>
> **1. WebSocket level:** FastAPI's WebSocketDisconnect exception catches clean disconnects. I remove the connection from the manager and notify other users.
>
> **2. Network failures:** I track connection state and have cleanup logic in the finally block. If a send fails, I mark that connection as disconnected and remove it.
>
> **3. Redis cleanup:** I use Redis' pub/sub unsubscribe to clean up channels when no users are in a document.
>
> **4. Database:** The sessions table tracks connect/disconnect times for analytics.
>
> On the frontend, I have reconnection logic with exponential backoff. If the WebSocket closes, it attempts to reconnect with increasing delays: 1s, 2s, 4s, up to 30s."

---

#### Q: "Why did you choose FastAPI over Flask or Django?"

**Good Answer:**
> "FastAPI was the best choice for three reasons:
>
> **1. Native async/await:** WebSockets require async support. FastAPI is built on Starlette and ASGI, making async WebSocket handling natural. Flask requires extensions and Django Channels adds complexity.
>
> **2. Type safety:** FastAPI uses Pydantic for automatic request validation and serialization. This catches bugs early and generates accurate API docs.
>
> **3. Performance:** ASGI servers like Uvicorn handle thousands of concurrent connections better than WSGI. Benchmarks show FastAPI matching Node.js performance.
>
> The automatic OpenAPI documentation at /docs was also valuable for testing during development."

---

### 3. Redis Questions

#### Q: "Could you use a message queue like RabbitMQ or Kafka instead of Redis?"

**Good Answer:**
> "Yes, but Redis pub/sub is better suited for this use case:
>
> **Redis pub/sub advantages:**
> - Fire-and-forget messaging (no persistence needed for live edits)
> - Sub-millisecond latency
> - Simple fan-out pattern
> - Built-in channel subscription
>
> **When to use Kafka:**
> - Need message persistence (replay history)
> - High throughput (millions of messages/sec)
> - Guaranteed delivery and ordering
>
> **When to use RabbitMQ:**
> - Complex routing rules
> - Need acknowledgments
> - Priority queues
>
> For live collaboration, Redis is optimal because edits are ephemeral - if a user isn't connected, they don't need missed edits (they get the full document state on connect). The simplicity and speed of Redis pub/sub fits perfectly."

---

#### Q: "What happens if Redis goes down?"

**Good Answer:**
> "Good question! Currently, Redis failure would break cross-server communication but not single-server functionality. Users on the same backend instance would still collaborate.
>
> **For production, I'd implement:**
>
> **1. Redis Sentinel or Cluster:**
> - Automatic failover
> - 3-node minimum for high availability
> - Promotion of replica to master on failure
>
> **2. Graceful degradation:**
> - Detect Redis connection failure
> - Fall back to single-server mode
> - Log errors and alert ops team
> - Return HTTP 503 for new connections if critical
>
> **3. Health checks:**
> - Kubernetes liveness/readiness probes
> - Monitor Redis connection state
> - Automatic pod restart on failure
>
> The code already has error handling in the ConnectionManager - it logs failures and continues serving local connections."

---

### 4. Frontend Questions

#### Q: "Why Monaco Editor instead of a simpler textarea or CodeMirror?"

**Good Answer:**
> "Monaco Editor is VS Code's editor, so users get a familiar, professional experience. Specific advantages:
>
> **1. Features out-of-box:**
> - Syntax highlighting for 50+ languages
> - IntelliSense and autocomplete
> - Multiple cursor support
> - Find/replace, code folding
>
> **2. Performance:**
> - Handles large files (10,000+ lines)
> - Virtual scrolling for efficiency
> - Web worker support for syntax parsing
>
> **3. Collaboration-ready:**
> - Well-documented cursor position API
> - Easy to add decorations for remote cursors
> - Support for Yjs bindings
>
> CodeMirror is also excellent, but Monaco's VS Code familiarity was worth the slightly larger bundle size (~1.5MB vs ~500KB)."

---

#### Q: "How do you handle the WebSocket connection state in React?"

**Good Answer:**
> "I use useEffect for lifecycle management and useState for connection state:
>
> ```javascript
> useEffect(() => {
>   const ws = new WebSocket(wsUrl);
>   
>   ws.onopen = () => setIsConnected(true);
>   ws.onmessage = (event) => handleMessage(event);
>   ws.onclose = () => setIsConnected(false);
>   
>   return () => ws.close(); // Cleanup on unmount
> }, [documentId]);
> ```
>
> The key is the cleanup function - it closes the WebSocket when the component unmounts or documentId changes, preventing memory leaks.
>
> I also handle reconnection by watching the isConnected state. When it goes false, a separate effect triggers reconnection logic with exponential backoff.
>
> For a production app, I'd extract this into a custom hook like `useWebSocket()` for reusability and testing."

---

### 5. Database Questions

#### Q: "Show me your database schema."

**Be ready to explain models.py:**

```sql
-- Users: authentication and ownership
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    email VARCHAR(100) UNIQUE,
    hashed_password VARCHAR(255),
    created_at TIMESTAMP
);

-- Documents: the actual content
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    content TEXT,              -- Plain text content
    yjs_state TEXT,           -- CRDT state for sync
    owner_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    is_public BOOLEAN
);

-- Sessions: analytics and active tracking
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    user_id INTEGER REFERENCES users(id),
    connected_at TIMESTAMP,
    disconnected_at TIMESTAMP  -- NULL while active
);
```

**Key design decisions:**
- `yjs_state` stores the CRDT state as text (base64 encoded)
- `content` is denormalized for quick reads
- `sessions` enables queries like "who's editing now?" and session analytics

---

#### Q: "Why store both `content` and `yjs_state`?"

**Good Answer:**
> "They serve different purposes:
>
> **`content` (TEXT):**
> - Plain text representation
> - Fast for search and display
> - Used for REST API responses
> - Human-readable for debugging
>
> **`yjs_state` (TEXT/BYTEA):**
> - Binary CRDT state
> - Complete edit history
> - Required for conflict-free sync
> - Includes all metadata for merging
>
> It's denormalization for performance - I could derive `content` from `yjs_state`, but querying would be slower. The storage cost is minimal (few KB per document), and disk is cheap compared to computation."

---

### 6. Testing & Debugging Questions

#### Q: "How would you test this system?"

**Good Answer:**
> "I'd have multiple levels of testing:
>
> **1. Unit Tests:**
> - `test_websocket_manager.py` - Connection handling, broadcasting
> - `test_auth.py` - Token generation, password hashing
> - Frontend: Jest tests for React components
>
> **2. Integration Tests:**
> - Test WebSocket message flow end-to-end
> - Test Redis pub/sub with multiple backend instances
> - Test database CRUD operations
>
> **3. Load Tests:**
> ```python
> # Using locust or k6
> # Simulate 100+ concurrent WebSocket connections
> # Measure message latency under load
> # Test reconnection storms
> ```
>
> **4. Chaos Engineering:**
> - Kill Redis mid-operation - does it recover?
> - Disconnect clients suddenly - are others affected?
> - Saturate network - does backpressure work?
>
> For load testing, I'd use tools like Locust or k6 to simulate 1000+ concurrent users and measure latency percentiles (p50, p95, p99)."

---

#### Q: "Tell me about a bug you encountered and how you debugged it."

**Prepare a real story! Example:**

> "One tricky bug was that edits sometimes weren't syncing to all users. I suspected the Redis pub/sub, but it was actually a race condition.
>
> **The bug:** When a user joined a document, they'd sometimes miss the first few edits from other users.
>
> **Debugging process:**
> 1. Added extensive logging with timestamps
> 2. Noticed the WebSocket connection succeeded before Redis subscription completed
> 3. Early messages were published but not subscribed yet
>
> **Solution:** Changed the connection flow:
> ```python
> # Before: connect → subscribe to Redis
> async def connect(websocket, doc_id, user_id):
>     await websocket.accept()
>     await self._subscribe_to_document(doc_id)  # ASYNC!
>
> # After: subscribe first
> async def connect(websocket, doc_id, user_id):
>     await self._subscribe_to_document(doc_id)
>     await websocket.accept()  # Accept AFTER subscribed
> ```
>
> Lesson learned: In distributed systems, timing matters. Always ensure setup completes before going live."

---

### 7. "What Would You Do Differently?" Questions

#### Q: "If you had more time, what would you add?"

**Great answer shows you think beyond MVP:**

> "Three main improvements:
>
> **1. Full CRDT Implementation**
> - Switch from last-write-wins to Yjs CRDTs
> - Enable true conflict-free merging
> - Add operational transforms for rich text
>
> **2. Operational Excellence**
> - Add Prometheus metrics and Grafana dashboards
> - Implement distributed tracing with Jaeger
> - Set up alerting for latency spikes
> - Add structured logging (JSON format)
>
> **3. User Features**
> - Syntax-aware edits (auto-indent, bracket matching)
> - Collaborative debugging (shared breakpoints)
> - Version history with git-style diffs
> - Comments and annotations
> - Document sharing and permissions (view/edit roles)
>
> If I had a week more, I'd prioritize #2 (observability) because you can't optimize what you don't measure."

---

### 8. Behavioral Questions About This Project

#### Q: "What was the hardest part of building this?"

**Good answer:**
> "The hardest part was understanding distributed systems concepts deeply enough to implement them correctly. Specifically:
>
> **1. Message ordering:** Ensuring updates apply in the right order across multiple servers was tricky. I had to think through edge cases like:
> - What if Redis delivers messages out of order?
> - What if a backend instance crashes mid-broadcast?
> - How do we handle network partitions?
>
> **2. Debugging distributed issues:** When something breaks, it's not always clear which component failed. I had to implement comprehensive logging with correlation IDs to trace messages through the system.
>
> **What I learned:** Reading academic papers (CRDTs, vector clocks) and open-source code (Yjs, Operational Transform libraries) was essential. I couldn't just code my way through - I needed to understand the theory."

---

#### Q: "Why did you choose to build this project?"

**Align with your goals:**
> "I wanted to build something that combined multiple skills I'm interested in:
>
> **1. Distributed systems:** I'm fascinated by how systems like Google Docs work at scale. This project let me implement pub/sub, handle consistency, and think about scaling.
>
> **2. Real-time systems:** WebSockets and event-driven architectures are increasingly important. Building this gave me hands-on experience with these patterns.
>
> **3. Full-stack development:** I wanted to see the complete picture - from user interactions in React to backend architecture to database design.
>
> It's also highly demonstrable - in interviews, I can pull it up and show real-time collaboration working, which is much more impressive than talking about a CRUD app."

---

## 🔑 Key Technical Terms to Know

Make sure you can define these in one sentence:

- **WebSocket:** Full-duplex communication channel over TCP, enabling real-time bidirectional data flow
- **CRDT:** Conflict-free Replicated Data Type - data structure that can be updated independently and merged without conflicts
- **Pub/Sub:** Messaging pattern where publishers send messages to channels, and subscribers receive them asynchronously
- **Operational Transform:** Algorithm for maintaining consistency in collaborative editing by transforming operations
- **Horizontal Scaling:** Adding more machines to handle load (vs vertical scaling = bigger machine)
- **Idempotency:** Property where an operation can be applied multiple times without changing the result
- **CAP Theorem:** In distributed systems, you can only guarantee 2 of 3: Consistency, Availability, Partition tolerance
- **Event-driven Architecture:** System where components communicate through events rather than direct calls

---

## 🎯 Practice Answers Out Loud

Before interviews:
1. Explain the architecture to a friend (or yourself in mirror)
2. Draw the system diagram from memory
3. Walk through the WebSocket message flow
4. Practice answering "why did you choose X over Y?" questions

---

## ⚠️ Red Flags to Avoid

**Don't say:**
- "I don't know how Redis works, I just used it"
- "The tutorial said to do it this way"
- "I didn't really understand CRDTs, but I included Yjs"
- "I haven't actually deployed it anywhere"
- "It probably doesn't scale well, but it works for now"

**Do say:**
- "I chose Redis because [specific reason]. The trade-off is [specific limitation]."
- "I studied CRDTs from [source]. While I used a simpler approach, I understand the theory."
- "I deployed to [platform]. Here's the URL you can try."
- "The current design handles X users. To scale further, I'd implement [specific strategy]."

---

## 📊 Know Your Numbers

Be ready to quote these:
- WebSocket latency: <100ms
- Redis pub/sub latency: <1ms  
- Concurrent users per backend: ~500
- Database query time: <50ms
- Message size: ~100-500 bytes
- Bandwidth per user: ~10-50 KB/s

---

## 🎤 Final Tips

1. **Be honest:** If you didn't implement something, say so but explain how you'd do it
2. **Show curiosity:** Ask questions back ("How does your team handle real-time sync?")
3. **Connect to business:** Mention user experience, not just tech ("This enables seamless collaboration, improving team productivity")
4. **Know the weak spots:** Every design has trade-offs - own them confidently
5. **Have the demo ready:** Nothing beats showing it work in real-time

Good luck! 🚀
