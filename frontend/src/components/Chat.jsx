import React, { useState, useEffect, useRef } from 'react';
import './Chat.css';

const Chat = ({ websocket, username, isConnected, onChatMessage }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const messagesEndRef = useRef(null);
  const chatBoxRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Handle incoming chat messages from parent component
  useEffect(() => {
    if (!onChatMessage) return;

    const handleIncomingMessage = (data) => {
      if (data.username === username) return;           // made change ; cause we already add own message to state when sending, so ignore if it's from self
      const newMessage = {
        id: Date.now() + Math.random(),
        username: data.username,
        message: data.message,
        timestamp: data.timestamp,
        isOwn: false
      };

      setMessages(prev => [...prev, newMessage]);

      // Increment unread count if chat is closed
      if (!isOpen) {
        setUnreadCount(prev => prev + 1);
      }
    };

    // Register callback with parent
    onChatMessage.current = handleIncomingMessage;

    return () => {
      if (onChatMessage.current === handleIncomingMessage) {
        onChatMessage.current = null;
      }
    };
  }, [onChatMessage, username, isOpen]);

  const sendMessage = (e) => {
    e.preventDefault();
    
    if (!inputMessage.trim() || !websocket || !isConnected) return;

    const messageText = inputMessage.trim();

    // Add message to local state immediately (optimistic update)
    const newMessage = {
      id: Date.now() + Math.random(),
      username: username,
      message: messageText,
      timestamp: Date.now() / 1000, // Convert to seconds
      isOwn: true
    };
    setMessages(prev => [...prev, newMessage]);

    // Send chat message via WebSocket
    websocket.send(JSON.stringify({
      type: 'chat',
      message: messageText
    }));

    setInputMessage('');
  };

  const toggleChat = () => {
    setIsOpen(!isOpen);
    if (!isOpen) {
      setUnreadCount(0); // Clear unread count when opening
    }
  };

  const formatTime = (timestamp) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <div className={`chat-container ${isOpen ? 'open' : 'closed'}`}>
      {/* Chat Toggle Button */}
      <button className="chat-toggle" onClick={toggleChat}>
        💬
        {unreadCount > 0 && (
          <span className="unread-badge">{unreadCount}</span>
        )}
      </button>

      {/* Chat Box */}
      {isOpen && (
        <div className="chat-box" ref={chatBoxRef}>
          <div className="chat-header">
            <h3>💬 Chat</h3>
            <button className="close-btn" onClick={toggleChat}>×</button>
          </div>

          <div className="chat-messages">
            {messages.length === 0 ? (
              <div className="empty-state">
                <p>No messages yet</p>
                <small>Start a conversation!</small>
              </div>
            ) : (
              messages.map((msg) => (
                <div 
                  key={msg.id} 
                  className={`message ${msg.isOwn ? 'own-message' : 'other-message'}`}
                >
                  <div className="message-header">
                    <span className="message-username">{msg.username}</span>
                    <span className="message-time">{formatTime(msg.timestamp)}</span>
                  </div>
                  <div className="message-content">{msg.message}</div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="chat-input-form" onSubmit={sendMessage}>
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder={isConnected ? "Type a message..." : "Connecting..."}
              disabled={!isConnected}
              className="chat-input"
            />
            <button 
              type="submit" 
              disabled={!inputMessage.trim() || !isConnected}
              className="send-btn"
            >
              Send
            </button>
          </form>
        </div>
      )}
    </div>
  );
};

export default Chat;
