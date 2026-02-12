from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging

from config import settings
from database import create_tables, get_db, get_async_db
from models import User, Document
from websocket_manager import manager
from document_persistence import persistence_manager
from auth import create_access_token, verify_token, get_password_hash, verify_password
from pydantic import BaseModel, EmailStr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class DocumentCreate(BaseModel):
    title: str
    content: str = ""

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    yjs_state: Optional[str] = None

# Initialize FastAPI app
app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize database and Redis on startup"""
    logger.info("🚀 Starting up...")
    create_tables()
    await manager.connect_redis()
    persistence_manager.start_auto_save()
    logger.info("✅ Startup complete!")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up Redis connections on shutdown"""
    logger.info("👋 Shutting down...")
    await persistence_manager.stop_auto_save()
    await manager.disconnect_redis()

# ==================== AUTH DEPENDENCY ====================

async def get_current_user(authorization: str = Header(None)):
    """Dependency to get current authenticated user"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return payload

# ==================== REST API Endpoints ====================

@app.get("/")
async def root():
    return {
        "message": "Collaborative Editor API",
        "version": "1.0.0",
        "endpoints": {
            "websocket": "/ws/{document_id}",
            "docs": "/docs"
        }
    }

@app.post("/api/auth/register")
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if user exists
    existing_user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create access token
    access_token = create_access_token(data={"sub": str(new_user.id), "username": new_user.username})
    
    return {
        "user_id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "access_token": access_token,
        "token_type": "bearer"
    }

@app.post("/api/auth/login")
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user"""
    user = db.query(User).filter(User.username == credentials.username).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
    
    return {
        "user_id": user.id,
        "username": user.username,
        "access_token": access_token,
        "token_type": "bearer"
    }

@app.post("/api/documents")
async def create_document(
    doc_data: DocumentCreate, 
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new document (authenticated users only)"""
    user_id = int(current_user.get("sub"))
    
    new_doc = Document(
        title=doc_data.title,
        content=doc_data.content,
        owner_id=user_id
    )
    
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    return {
        "id": new_doc.id,
        "title": new_doc.title,
        "content": new_doc.content,
        "owner_id": new_doc.owner_id,
        "created_at": new_doc.created_at
    }

@app.get("/api/documents")
async def list_documents(db: Session = Depends(get_db)):
    """List all public documents"""
    documents = db.query(Document).filter(Document.is_public == True).all()
    
    return [
        {
            "id": doc.id,
            "title": doc.title,
            "owner_id": doc.owner_id,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at
        }
        for doc in documents
    ]

@app.get("/api/documents/{document_id}")
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get document by ID"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "yjs_state": doc.yjs_state,
        "owner_id": doc.owner_id,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at
    }

@app.put("/api/documents/{document_id}")
async def update_document(
    document_id: int, 
    doc_data: DocumentUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update document (authenticated users only)"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc_data.title is not None:
        doc.title = doc_data.title
    if doc_data.content is not None:
        doc.content = doc_data.content
    if doc_data.yjs_state is not None:
        doc.yjs_state = doc_data.yjs_state
    
    db.commit()
    db.refresh(doc)
    
    return {"message": "Document updated successfully", "id": doc.id}

# ==================== WebSocket Endpoint ====================

@app.websocket("/ws/{document_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    document_id: str,
    token: Optional[str] = None
):
    """
    WebSocket endpoint for real-time collaboration.
    Requires authentication token.
    """
    
    # Verify token
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        logger.warning(f"WebSocket connection rejected: Missing token")
        return
    
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Invalid token")
        logger.warning(f"WebSocket connection rejected: Invalid token")
        return
    
    user_id = payload.get("sub")
    username = payload.get("username", user_id)
    
    logger.info(f"✅ User {username} (ID: {user_id}) authenticated for document {document_id}")
    
    # Get current active users BEFORE connecting (so new user isn't included)
    active_users = manager.get_active_users(document_id)
    
    # Connect to WebSocket (adds user to active list)
    await manager.connect(websocket, document_id, user_id)
    
    # Load document content from database
    from database import SessionLocal
    db = SessionLocal()
    try:
        document_content = persistence_manager.load_document(document_id, db)
    finally:
        db.close()
    
    # Send list of OTHER active users to the new user + document content
    await manager.send_personal_message(
        {
            "type": "init",
            "user_id": user_id,
            "username": username,
            "active_users": active_users,  # Doesn't include current user yet
            "content": document_content  # Send saved document content
        },
        websocket
    )
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            logger.info(f"📨 Received from {username}: {message.get('type', 'unknown')}")
            
            # Handle different message types
            msg_type = message.get("type")
            
            if msg_type == "update":
                # Update persistence cache
                content = message.get("data", {}).get("content")
                if content is not None:
                    persistence_manager.update_document(document_id, content)
                
                # Broadcast document update to all other users
                await manager.broadcast_to_document(
                    document_id,
                    {
                        "type": "update",
                        "user_id": user_id,
                        "username": username,
                        "data": message.get("data", {}),
                        "timestamp": message.get("timestamp")
                    },
                    exclude_user=user_id
                )
            
            elif msg_type == "cursor":
                # Broadcast cursor position
                await manager.broadcast_to_document(
                    document_id,
                    {
                        "type": "cursor",
                        "user_id": user_id,
                        "username": username,
                        "position": message.get("position"),
                        "selection": message.get("selection")
                    },
                    exclude_user=user_id
                )
            
            elif msg_type == "awareness":
                # Broadcast user awareness (presence, selection, etc.)
                await manager.broadcast_to_document(
                    document_id,
                    {
                        "type": "awareness",
                        "user_id": user_id,
                        "username": username,
                        "data": message.get("data")
                    },
                    exclude_user=user_id
                )
            
            elif msg_type == "chat":
                # Broadcast chat message to OTHER users (not sender)
                import time
                await manager.broadcast_to_document(
                    document_id,
                    {
                        "type": "chat",
                        "user_id": user_id,
                        "username": username,
                        "message": message.get("message"),
                        "timestamp": time.time()
                    },
                    exclude_user=user_id  # Don't send back to sender
                )
    
    except WebSocketDisconnect:
        manager.disconnect(document_id, user_id)
        
        # Notify others about user leaving
        await manager.broadcast_to_document(
            document_id,
            {
                "type": "user_left",
                "user_id": user_id,
                "username": username
            }
        )
        
        logger.info(f"👋 User {username} disconnected from document {document_id}")
    
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
        manager.disconnect(document_id, user_id)

@app.get("/api/documents/{document_id}/users")
async def get_active_users(document_id: str):
    """Get list of currently active users in a document"""
    active_users = manager.get_active_users(document_id)
    return {
        "document_id": document_id,
        "active_users": active_users,
        "count": len(active_users)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )














































































































# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Header
# from fastapi.middleware.cors import CORSMiddleware
# from sqlalchemy.orm import Session
# from typing import Optional
# import json
# import logging

# from config import settings
# from database import create_tables, get_db, get_async_db
# from models import User, Document
# from websocket_manager import manager
# from auth import create_access_token, verify_token, get_password_hash, verify_password
# from pydantic import BaseModel, EmailStr

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Pydantic models for API
# class UserCreate(BaseModel):
#     username: str
#     email: EmailStr
#     password: str

# class UserLogin(BaseModel):
#     username: str
#     password: str

# class DocumentCreate(BaseModel):
#     title: str
#     content: str = ""

# class DocumentUpdate(BaseModel):
#     title: Optional[str] = None
#     content: Optional[str] = None
#     yjs_state: Optional[str] = None

# # Initialize FastAPI app
# app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# # CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.CORS_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# @app.on_event("startup")
# async def startup_event():
#     """Initialize database and Redis on startup"""
#     logger.info("🚀 Starting up...")
#     create_tables()
#     await manager.connect_redis()
#     logger.info("✅ Startup complete!")

# @app.on_event("shutdown")
# async def shutdown_event():
#     """Clean up Redis connections on shutdown"""
#     logger.info("👋 Shutting down...")
#     await manager.disconnect_redis()

# # ==================== AUTH DEPENDENCY ====================

# async def get_current_user(authorization: str = Header(None)):
#     """Dependency to get current authenticated user"""
#     if not authorization or not authorization.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="Not authenticated")
    
#     token = authorization.replace("Bearer ", "")
#     payload = verify_token(token)
    
#     if not payload:
#         raise HTTPException(status_code=401, detail="Invalid token")
    
#     return payload

# # ==================== REST API Endpoints ====================

# @app.get("/")
# async def root():
#     return {
#         "message": "Collaborative Editor API",
#         "version": "1.0.0",
#         "endpoints": {
#             "websocket": "/ws/{document_id}",
#             "docs": "/docs"
#         }
#     }

# @app.post("/api/auth/register")
# async def register(user_data: UserCreate, db: Session = Depends(get_db)):
#     """Register a new user"""
#     # Check if user exists
#     existing_user = db.query(User).filter(
#         (User.username == user_data.username) | (User.email == user_data.email)
#     ).first()
    
#     if existing_user:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Username or email already registered"
#         )
    
#     # Create new user
#     hashed_password = get_password_hash(user_data.password)
#     new_user = User(
#         username=user_data.username,
#         email=user_data.email,
#         hashed_password=hashed_password
#     )
    
#     db.add(new_user)
#     db.commit()
#     db.refresh(new_user)
    
#     # Create access token
#     access_token = create_access_token(data={"sub": str(new_user.id), "username": new_user.username})
    
#     return {
#         "user_id": new_user.id,
#         "username": new_user.username,
#         "email": new_user.email,
#         "access_token": access_token,
#         "token_type": "bearer"
#     }

# @app.post("/api/auth/login")
# async def login(credentials: UserLogin, db: Session = Depends(get_db)):
#     """Login user"""
#     user = db.query(User).filter(User.username == credentials.username).first()
    
#     if not user or not verify_password(credentials.password, user.hashed_password):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Incorrect username or password"
#         )
    
#     access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
    
#     return {
#         "user_id": user.id,
#         "username": user.username,
#         "access_token": access_token,
#         "token_type": "bearer"
#     }

# @app.post("/api/documents")
# async def create_document(
#     doc_data: DocumentCreate, 
#     current_user: dict = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     """Create a new document (authenticated users only)"""
#     user_id = int(current_user.get("sub"))
    
#     new_doc = Document(
#         title=doc_data.title,
#         content=doc_data.content,
#         owner_id=user_id
#     )
    
#     db.add(new_doc)
#     db.commit()
#     db.refresh(new_doc)
    
#     return {
#         "id": new_doc.id,
#         "title": new_doc.title,
#         "content": new_doc.content,
#         "owner_id": new_doc.owner_id,
#         "created_at": new_doc.created_at
#     }

# @app.get("/api/documents")
# async def list_documents(db: Session = Depends(get_db)):
#     """List all public documents"""
#     documents = db.query(Document).filter(Document.is_public == True).all()
    
#     return [
#         {
#             "id": doc.id,
#             "title": doc.title,
#             "owner_id": doc.owner_id,
#             "created_at": doc.created_at,
#             "updated_at": doc.updated_at
#         }
#         for doc in documents
#     ]

# @app.get("/api/documents/{document_id}")
# async def get_document(document_id: int, db: Session = Depends(get_db)):
#     """Get document by ID"""
#     doc = db.query(Document).filter(Document.id == document_id).first()
    
#     if not doc:
#         raise HTTPException(status_code=404, detail="Document not found")
    
#     return {
#         "id": doc.id,
#         "title": doc.title,
#         "content": doc.content,
#         "yjs_state": doc.yjs_state,
#         "owner_id": doc.owner_id,
#         "created_at": doc.created_at,
#         "updated_at": doc.updated_at
#     }

# @app.put("/api/documents/{document_id}")
# async def update_document(
#     document_id: int, 
#     doc_data: DocumentUpdate,
#     current_user: dict = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     """Update document (authenticated users only)"""
#     doc = db.query(Document).filter(Document.id == document_id).first()
    
#     if not doc:
#         raise HTTPException(status_code=404, detail="Document not found")
    
#     if doc_data.title is not None:
#         doc.title = doc_data.title
#     if doc_data.content is not None:
#         doc.content = doc_data.content
#     if doc_data.yjs_state is not None:
#         doc.yjs_state = doc_data.yjs_state
    
#     db.commit()
#     db.refresh(doc)
    
#     return {"message": "Document updated successfully", "id": doc.id}

# # ==================== WebSocket Endpoint ====================

# @app.websocket("/ws/{document_id}")
# async def websocket_endpoint(
#     websocket: WebSocket,
#     document_id: str,
#     token: Optional[str] = None
# ):
#     """
#     WebSocket endpoint for real-time collaboration.
#     Requires authentication token.
#     """
    
#     # Verify token
#     if not token:
#         await websocket.close(code=1008, reason="Missing token")
#         logger.warning(f"WebSocket connection rejected: Missing token")
#         return
    
#     payload = verify_token(token)
#     if not payload:
#         await websocket.close(code=1008, reason="Invalid token")
#         logger.warning(f"WebSocket connection rejected: Invalid token")
#         return
    
#     user_id = payload.get("sub")
#     username = payload.get("username", user_id)
    
#     logger.info(f"✅ User {username} (ID: {user_id}) authenticated for document {document_id}")
    
#     # Get current active users BEFORE connecting (so new user isn't included)
#     active_users = manager.get_active_users(document_id)
    
#     # Connect to WebSocket (adds user to active list)
#     await manager.connect(websocket, document_id, user_id)
    
#     # Send list of OTHER active users to the new user
#     await manager.send_personal_message(
#         {
#             "type": "init",
#             "user_id": user_id,
#             "username": username,
#             "active_users": active_users  # Doesn't include current user yet
#         },
#         websocket
#     )
    
#     try:
#         while True:
#             # Receive message from client
#             data = await websocket.receive_text()
#             message = json.loads(data)
            
#             logger.info(f"📨 Received from {username}: {message.get('type', 'unknown')}")
            
#             # Handle different message types
#             msg_type = message.get("type")
            
#             if msg_type == "update":
#                 # Broadcast document update to all other users
#                 await manager.broadcast_to_document(
#                     document_id,
#                     {
#                         "type": "update",
#                         "user_id": user_id,
#                         "username": username,
#                         "data": message.get("data", {}),
#                         "timestamp": message.get("timestamp")
#                     },
#                     exclude_user=user_id
#                 )
            
#             elif msg_type == "cursor":
#                 # Broadcast cursor position
#                 await manager.broadcast_to_document(
#                     document_id,
#                     {
#                         "type": "cursor",
#                         "user_id": user_id,
#                         "username": username,
#                         "position": message.get("position"),
#                         "selection": message.get("selection")
#                     },
#                     exclude_user=user_id
#                 )
            
#             elif msg_type == "awareness":
#                 # Broadcast user awareness (presence, selection, etc.)
#                 await manager.broadcast_to_document(
#                     document_id,
#                     {
#                         "type": "awareness",
#                         "user_id": user_id,
#                         "username": username,
#                         "data": message.get("data")
#                     },
#                     exclude_user=user_id
#                 )
            
#             elif msg_type == "chat":
#                 # Broadcast chat message to OTHER users (not sender)
#                 import time
#                 await manager.broadcast_to_document(
#                     document_id,
#                     {
#                         "type": "chat",
#                         "user_id": user_id,
#                         "username": username,
#                         "message": message.get("message"),
#                         "timestamp": time.time()
#                     },
#                     exclude_user=user_id  # Don't send back to sender
#                 )
    
#     except WebSocketDisconnect:
#         manager.disconnect(document_id, user_id)
        
#         # Notify others about user leaving
#         await manager.broadcast_to_document(
#             document_id,
#             {
#                 "type": "user_left",
#                 "user_id": user_id,
#                 "username": username
#             }
#         )
        
#         logger.info(f"👋 User {username} disconnected from document {document_id}")
    
#     except Exception as e:
#         logger.error(f"❌ WebSocket error: {e}")
#         manager.disconnect(document_id, user_id)

# @app.get("/api/documents/{document_id}/users")
# async def get_active_users(document_id: str):
#     """Get list of currently active users in a document"""
#     active_users = manager.get_active_users(document_id)
#     return {
#         "document_id": document_id,
#         "active_users": active_users,
#         "count": len(active_users)
#     }

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(
#         "main:app",
#         host=settings.HOST,
#         port=settings.PORT,
#         reload=settings.DEBUG
#     )