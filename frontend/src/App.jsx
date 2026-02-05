import React, { useState } from 'react';
import CollaborativeEditor from './components/CollaborativeEditor';
import './App.css';

function App() {
  const [documentId, setDocumentId] = useState('demo-doc');
  const [userId, setUserId] = useState(() => {
    // Generate a random user ID
    return `user_${Math.random().toString(36).substring(2, 10)}`;
  });
  const [inputDocId, setInputDocId] = useState('demo-doc');
  const [isJoined, setIsJoined] = useState(false);

  const handleJoinDocument = () => {
    if (inputDocId.trim()) {
      setDocumentId(inputDocId.trim());
      setIsJoined(true);
    }
  };

  if (!isJoined) {
    return (
      <div className="landing-page">
        <div className="landing-container">
          <h1>🚀 Collaborative Code Editor</h1>
          <p className="subtitle">Real-time collaborative editing powered by WebSockets</p>
          
          <div className="join-form">
            <div className="form-group">
              <label>Your User ID</label>
              <input
                type="text"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="Enter your user ID"
                className="form-input"
              />
            </div>
            
            <div className="form-group">
              <label>Document ID</label>
              <input
                type="text"
                value={inputDocId}
                onChange={(e) => setInputDocId(e.target.value)}
                placeholder="Enter document ID"
                className="form-input"
                onKeyPress={(e) => e.key === 'Enter' && handleJoinDocument()}
              />
              <small>Enter the same document ID to collaborate with others</small>
            </div>
            
            <button onClick={handleJoinDocument} className="join-button">
              Join Document
            </button>
          </div>

          <div className="features">
            <div className="feature">
              <span className="feature-icon">⚡</span>
              <h3>Real-time Sync</h3>
              <p>Changes sync instantly across all users</p>
            </div>
            <div className="feature">
              <span className="feature-icon">👥</span>
              <h3>Multi-user</h3>
              <p>See who's online and editing</p>
            </div>
            <div className="feature">
              <span className="feature-icon">🔄</span>
              <h3>Conflict Resolution</h3>
              <p>Built-in CRDT-based conflict handling</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="App">
      <CollaborativeEditor documentId={documentId} userId={userId} />
    </div>
  );
}

export default App;
