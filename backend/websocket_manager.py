import json
import asyncio
import redis.asyncio as aioredis
from fastapi import WebSocket
from typing import Dict, Set, Optional
from collections import defaultdict
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts messages.
    Uses Redis pub/sub to enable horizontal scaling across multiple server instances.
    """
    
    def __init__(self):
        # Store active connections per document
        # Structure: {document_id: {user_id: WebSocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = defaultdict(dict)
        
        # Redis client for pub/sub
        self.redis: Optional[aioredis.Redis] = None
        self.pubsub = None
        
        # Track which documents this server instance is subscribed to
        self.subscribed_documents: Set[str] = set()
        
    async def connect_redis(self):
        """Initialize Redis connection for pub/sub"""
        try:
            self.redis = await aioredis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                encoding="utf-8",
                decode_responses=True
            )
            self.pubsub = self.redis.pubsub()
            logger.info("✅ Connected to Redis for pub/sub")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            logger.warning("⚠️  Running in single-server mode without Redis")
    
    async def disconnect_redis(self):
        """Clean up Redis connections"""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()
    
    async def connect(self, websocket: WebSocket, document_id: str, user_id: str):
        """Accept WebSocket connection and add to active connections"""
        await websocket.accept()
        self.active_connections[document_id][user_id] = websocket
        
        # Subscribe to Redis channel for this document (for multi-server sync)
        if self.redis and document_id not in self.subscribed_documents:
            await self._subscribe_to_document(document_id)
        
        logger.info(f"👤 User {user_id} connected to document {document_id}")
        logger.info(f"📊 Active connections for doc {document_id}: {len(self.active_connections[document_id])}")
        
        # Notify others about new user
        await self.broadcast_to_document(
            document_id,
            {
                "type": "user_joined",
                "user_id": user_id,
                "timestamp": asyncio.get_event_loop().time()
            },
            exclude_user=user_id
        )
    
    def disconnect(self, document_id: str, user_id: str):
        """Remove WebSocket connection"""
        if document_id in self.active_connections:
            if user_id in self.active_connections[document_id]:
                del self.active_connections[document_id][user_id]
                logger.info(f"👋 User {user_id} disconnected from document {document_id}")
                
                # Clean up empty document rooms
                if not self.active_connections[document_id]:
                    del self.active_connections[document_id]
                    logger.info(f"🗑️  Removed empty document room {document_id}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast_to_document(
        self, 
        document_id: str, 
        message: dict, 
        exclude_user: Optional[str] = None
    ):
        """
        Broadcast message to all users in a document.
        Also publishes to Redis for other server instances.
        """
        # Send to local connections
        if document_id in self.active_connections:
            disconnected_users = []
            
            for user_id, connection in self.active_connections[document_id].items():
                if exclude_user and user_id == exclude_user:
                    continue
                
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to user {user_id}: {e}")
                    disconnected_users.append(user_id)
            
            # Clean up disconnected users
            for user_id in disconnected_users:
                self.disconnect(document_id, user_id)
        
        # Publish to Redis for other server instances
        if self.redis:
            await self._publish_to_redis(document_id, message, exclude_user)
    
    async def _publish_to_redis(self, document_id: str, message: dict, exclude_user: Optional[str] = None):
        """Publish message to Redis channel"""
        try:
            redis_message = {
                "message": message,
                "exclude_user": exclude_user
            }
            await self.redis.publish(
                f"document:{document_id}",
                json.dumps(redis_message)
            )
        except Exception as e:
            logger.error(f"Error publishing to Redis: {e}")
    
    async def _subscribe_to_document(self, document_id: str):
        """Subscribe to Redis channel for document updates from other servers"""
        try:
            channel = f"document:{document_id}"
            await self.pubsub.subscribe(channel)
            self.subscribed_documents.add(document_id)
            
            # Start listener task for this channel
            asyncio.create_task(self._redis_listener(document_id))
            
            logger.info(f"📡 Subscribed to Redis channel: {channel}")
        except Exception as e:
            logger.error(f"Error subscribing to Redis channel: {e}")
    
    async def _redis_listener(self, document_id: str):
        """Listen for messages from Redis and forward to local connections"""
        channel = f"document:{document_id}"
        
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        msg = data["message"]
                        exclude_user = data.get("exclude_user")
                        
                        # Forward to local connections (without publishing back to Redis)
                        if document_id in self.active_connections:
                            for user_id, connection in self.active_connections[document_id].items():
                                if exclude_user and user_id == exclude_user:
                                    continue
                                
                                try:
                                    await connection.send_json(msg)
                                except Exception as e:
                                    logger.error(f"Error forwarding Redis message to user {user_id}: {e}")
                    
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding Redis message: {e}")
        
        except Exception as e:
            logger.error(f"Redis listener error for {document_id}: {e}")
    
    def get_active_users(self, document_id: str) -> list:
        """Get list of active user IDs for a document"""
        if document_id in self.active_connections:
            return list(self.active_connections[document_id].keys())
        return []

# Global connection manager instance
manager = ConnectionManager()
