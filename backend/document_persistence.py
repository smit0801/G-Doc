import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import SessionLocal
from models import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentPersistenceManager:
    """
    Manages automatic document persistence.
    Periodically saves document content to database.
    """
    
    def __init__(self, save_interval: int = 30):
        """
        Initialize the persistence manager.
        
        Args:
            save_interval: How often to save documents (in seconds)
        """
        self.save_interval = save_interval
        
        # Track latest content per document: {document_id: content}
        self.document_cache: Dict[str, str] = {}
        
        # Track if document has unsaved changes: {document_id: bool}
        self.dirty_documents: Dict[str, bool] = {}
        
        # Background save task
        self.save_task: Optional[asyncio.Task] = None
        
        logger.info(f"💾 Document persistence initialized (save every {save_interval}s)")
    
    def update_document(self, document_id: str, content: str):
        """
        Update document content in cache (called on every edit).
        
        Args:
            document_id: Document identifier
            content: New document content
        """
        self.document_cache[document_id] = content
        self.dirty_documents[document_id] = True
        logger.debug(f"📝 Document {document_id} marked dirty")
    
    async def save_all_dirty_documents(self):
        """Save all documents that have unsaved changes."""
        if not self.dirty_documents:
            return
        
        dirty_count = sum(1 for dirty in self.dirty_documents.values() if dirty)
        if dirty_count == 0:
            return
        
        logger.info(f"💾 Saving {dirty_count} dirty document(s)...")
        
        db = SessionLocal()
        try:
            for doc_id, is_dirty in list(self.dirty_documents.items()):
                if not is_dirty:
                    continue
                
                content = self.document_cache.get(doc_id)
                if content is None:
                    continue
                
                try:
                    # Convert document_id to integer if needed
                    # In our case, document_id from WebSocket might be string
                    # but database ID is integer
                    if doc_id.isdigit():
                        db_doc_id = int(doc_id)
                    else:
                        # If it's a string like "demo-doc", we need to find or create it
                        # For now, we'll skip non-numeric IDs
                        logger.warning(f"⚠️  Skipping non-numeric document ID: {doc_id}")
                        continue
                    
                    # Find document in database
                    document = db.query(Document).filter(Document.id == db_doc_id).first()
                    
                    if document:
                        # Update existing document
                        document.content = content
                        document.updated_at = datetime.utcnow()
                        
                        logger.info(f"✅ Saved document {doc_id} ({len(content)} chars)")
                    else:
                        logger.warning(f"⚠️ Document {doc_id} not found - Creating it now...")
                        # Note: We default owner_id=1 since the background task doesn't know the creator
                        new_doc = Document(id=db_doc_id, title="Untitled", content=content, owner_id=1)
                        db.add(new_doc)
                        logger.info(f"✅ Created new document {doc_id}")
                    db.commit()
                    
                    # Mark as clean
                    self.dirty_documents[doc_id] = False
                
                except Exception as e:
                    logger.error(f"❌ Error saving document {doc_id}: {e}")
                    db.rollback()
        
        finally:
            db.close()
    
    async def auto_save_loop(self):
        """Background task that periodically saves dirty documents."""
        logger.info(f"🔄 Auto-save loop started (every {self.save_interval}s)")
        
        while True:
            try:
                await asyncio.sleep(self.save_interval)
                await self.save_all_dirty_documents()
            
            except asyncio.CancelledError:
                logger.info("🛑 Auto-save loop stopped")
                # Save one last time before stopping
                await self.save_all_dirty_documents()
                break
            
            except Exception as e:
                logger.error(f"❌ Error in auto-save loop: {e}")
    
    def start_auto_save(self):
        """Start the background auto-save task."""
        if self.save_task is None or self.save_task.done():
            self.save_task = asyncio.create_task(self.auto_save_loop())
            logger.info("▶️  Auto-save task started")
    
    async def stop_auto_save(self):
        """Stop the background auto-save task."""
        if self.save_task and not self.save_task.done():
            self.save_task.cancel()
            try:
                await self.save_task
            except asyncio.CancelledError:
                pass
            logger.info("⏹️  Auto-save task stopped")
    
    def load_document(self, document_id: str, db: Session) -> Optional[str]:
        """
        Load document content from database.
        
        Args:
            document_id: Document identifier
            db: Database session
            
        Returns:
            Document content or None if not found
        """
        try:
            if document_id.isdigit():
                db_doc_id = int(document_id)
                document = db.query(Document).filter(Document.id == db_doc_id).first()
                
                if document:
                    logger.info(f"📄 Loaded document {document_id} from database ({len(document.content or '')} chars)")
                    # Update cache
                    self.document_cache[document_id] = document.content or ""
                    self.dirty_documents[document_id] = False
                    return document.content or ""
            
            return None
        
        except Exception as e:
            logger.error(f"❌ Error loading document {document_id}: {e}")
            return None
    
    def get_cached_content(self, document_id: str) -> Optional[str]:
        """Get document content from cache (if available)."""
        return self.document_cache.get(document_id)

# Global persistence manager instance
persistence_manager = DocumentPersistenceManager(save_interval=30)
