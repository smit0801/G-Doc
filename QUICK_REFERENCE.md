# 📋 Quick Reference Card

## Essential Commands

### Starting the Project
```bash
# Full stack with Docker
docker-compose up --build

# Backend only (local)
cd backend && python main.py

# Frontend only (local)
cd frontend && npm run dev
```

### Accessing Services
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Viewing Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f redis
docker-compose logs -f postgres
```

### Stopping/Restarting
```bash
# Stop all services
docker-compose down

# Restart specific service
docker-compose restart backend

# Rebuild and restart
docker-compose up --build backend
```

### Database Management
```bash
# Connect to PostgreSQL
docker exec -it collab-editor-db psql -U postgres -d collab_editor

# Common SQL queries
SELECT * FROM documents;
SELECT * FROM users;
SELECT * FROM sessions WHERE disconnected_at IS NULL;  -- Active sessions

# Reset database
docker-compose down -v  # Remove volumes
docker-compose up --build
```

### Redis Management
```bash
# Connect to Redis CLI
docker exec -it collab-editor-redis redis-cli

# Monitor pub/sub activity
PSUBSCRIBE document:*

# Check active channels
PUBSUB CHANNELS

# Check connected clients
CLIENT LIST
```

---

## 🐛 Troubleshooting

### Issue: Can't connect to WebSocket
```bash
# Check if backend is running
docker-compose ps

# Check backend logs for errors
docker-compose logs backend | grep ERROR

# Verify WebSocket endpoint
curl http://localhost:8000/
```

### Issue: Frontend not loading
```bash
# Check if frontend container is running
docker-compose ps frontend

# Rebuild frontend
cd frontend
rm -rf node_modules dist
npm install
npm run build
```

### Issue: Database connection errors
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker exec -it collab-editor-db psql -U postgres -c "SELECT 1;"

# Check DATABASE_URL in backend/.env
cat backend/.env | grep DATABASE_URL
```

### Issue: Redis connection failed
```bash
# Check Redis is running
docker-compose ps redis

# Test Redis connection
docker exec -it collab-editor-redis redis-cli PING
# Should return: PONG

# Check Redis host in backend/.env
cat backend/.env | grep REDIS_HOST
```

### Issue: Changes not syncing between users
```bash
# Test WebSocket connection
# 1. Open browser console
# 2. Connect to document
# 3. Look for WebSocket errors

# Check Redis pub/sub
docker exec -it collab-editor-redis redis-cli
SUBSCRIBE document:test-doc
# In another terminal, make an edit
# Should see message published
```

### Issue: High CPU/Memory usage
```bash
# Check resource usage
docker stats

# Check number of connections
docker exec -it collab-editor-backend python -c "
import redis
r = redis.Redis(host='redis', port=6379)
print('Redis memory:', r.info('memory')['used_memory_human'])
"

# Restart services
docker-compose restart backend
```

---

## 📝 Testing Checklist

### Manual Testing
```bash
# 1. Start services
docker-compose up

# 2. Open two browser windows
# Window 1: http://localhost:3000
# Window 2: http://localhost:3000 (incognito)

# 3. Join same document
# Both windows: document ID = "test-doc"

# 4. Test real-time sync
# Window 1: Type "hello"
# Window 2: Should see "hello" appear

# 5. Test presence
# Both windows: Should show 2 active users

# 6. Test disconnect
# Window 1: Close tab
# Window 2: Should show user left notification
```

### API Testing
```bash
# Create a document
curl -X POST http://localhost:8000/api/documents \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Doc", "content": "Hello world"}'

# List documents
curl http://localhost:8000/api/documents

# Get document
curl http://localhost:8000/api/documents/1

# Get active users
curl http://localhost:8000/api/documents/test-doc/users
```

### WebSocket Testing (with websocat)
```bash
# Install websocat
brew install websocat  # Mac
# or: cargo install websocat

# Connect to WebSocket
websocat ws://localhost:8000/ws/test-doc?user_id=test_user

# Send message (paste and press Enter)
{"type": "update", "data": {"content": "test"}}

# Should receive messages from other users
```

---

## 🔧 Configuration Quick Ref

### Backend Environment Variables
```bash
# backend/.env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/collab_editor
REDIS_HOST=redis
REDIS_PORT=6379
SECRET_KEY=change-me-in-production
DEBUG=True
```

### Frontend Configuration
```javascript
// frontend/vite.config.js
server: {
  port: 3000,
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws': {
      target: 'ws://localhost:8000',
      ws: true
    }
  }
}
```

### Docker Compose Services
```yaml
services:
  postgres:  # Port 5432
  redis:     # Port 6379
  backend:   # Port 8000
  frontend:  # Port 3000 (or 80 in production)
```

---

## 📊 Performance Metrics

### Normal Operation
- CPU (backend): 5-15%
- Memory (backend): 100-200 MB
- WebSocket connections: Check logs
- Redis memory: <50 MB
- Database connections: 5-10

### Red Flags
- CPU >80%: Too many connections or infinite loop
- Memory >1GB: Memory leak, check for unclosed connections
- WebSocket errors: Check firewall/proxy settings
- Redis out of memory: Increase Redis max memory

---

## 🚀 Deployment Quick Guide

### Deploy to Railway.app
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up

# Set environment variables
railway variables set DATABASE_URL=...
railway variables set REDIS_HOST=...
```

### Deploy to Render.com
1. Push to GitHub
2. Go to render.com
3. Create New → Web Service
4. Connect repo
5. Add Redis and PostgreSQL add-ons
6. Set environment variables
7. Deploy

### Deploy to AWS (ECS)
```bash
# Build and push Docker images
docker build -t myapp-backend ./backend
docker tag myapp-backend:latest <ECR_URI>:latest
docker push <ECR_URI>:latest

# Deploy to ECS
aws ecs update-service --cluster my-cluster --service backend --force-new-deployment
```

---

## 🎯 Development Workflow

### Making Changes

**Backend changes:**
```bash
# 1. Edit files in backend/
# 2. Container auto-reloads (if --reload flag set)
# 3. Check logs: docker-compose logs -f backend
```

**Frontend changes:**
```bash
# 1. Edit files in frontend/src/
# 2. Vite auto-reloads
# 3. Check browser console for errors
```

**Database changes:**
```bash
# 1. Edit backend/models.py
# 2. Restart backend to create tables
docker-compose restart backend
```

### Git Workflow
```bash
# Create feature branch
git checkout -b feature/add-chat

# Make changes and test
docker-compose up

# Commit
git add .
git commit -m "Add chat feature"

# Push and create PR
git push origin feature/add-chat
```

---

## 📚 Useful Resources

### Documentation
- FastAPI: https://fastapi.tiangolo.com/
- React: https://react.dev/
- Monaco Editor: https://microsoft.github.io/monaco-editor/
- Redis: https://redis.io/docs/
- PostgreSQL: https://www.postgresql.org/docs/

### Learning
- WebSockets: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket
- CRDTs: https://crdt.tech/
- Distributed Systems: https://www.distributed-systems.net/

### Tools
- Postman: API testing
- Redis Insight: Redis GUI
- pgAdmin: PostgreSQL GUI
- Chrome DevTools: WebSocket debugging

---

## 🆘 Getting Help

1. Check logs: `docker-compose logs -f`
2. Read error messages carefully
3. Check this file's troubleshooting section
4. Search error message on Stack Overflow
5. Read the code - comments explain everything!

---

**Print this page and keep it handy! 📋**
