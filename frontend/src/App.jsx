import React, { useState, useEffect } from 'react';
import CollaborativeEditor from './components/CollaborativeEditor';
import Login from './components/Login';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userData, setUserData] = useState(null);
  const [documentId, setDocumentId] = useState('demo-doc');
  const [inputDocId, setInputDocId] = useState('demo-doc');
  const [isJoined, setIsJoined] = useState(false);

  // Check if user is already logged in
  useEffect(() => {
    const token = localStorage.getItem('token');
    const userId = localStorage.getItem('userId');
    const username = localStorage.getItem('username');

    if (token && userId && username) {
      setUserData({ user_id: userId, username, access_token: token });
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = (data) => {
    setUserData(data);
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('userId');
    localStorage.removeItem('username');
    setUserData(null);
    setIsAuthenticated(false);
    setIsJoined(false);
  };

  const handleJoinDocument = () => {
    if (inputDocId.trim()) {
      setDocumentId(inputDocId.trim());
      setIsJoined(true);
    }
  };

  // Show login if not authenticated
  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  // Show document selector if not joined
  if (!isJoined) {
    return (
      <div className="landing-page">
        <div className="landing-container">
          <div className="user-info">
            <span>Logged in as: <strong>{userData.username}</strong></span>
            <button onClick={handleLogout} className="logout-button">
              Logout
            </button>
          </div>

          <h1>🚀 Collaborative Code Editor</h1>
          <p className="subtitle">Real-time collaborative editing powered by WebSockets</p>
          
          <div className="join-form">
            <div className="form-group">
              <label>Document ID</label>
              <input
                type="text"
                value={inputDocId}
                onChange={(e) => setInputDocId(e.target.value)}
                placeholder="Enter document ID to collaborate"
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
              <span className="feature-icon">🔐</span>
              <h3>Authenticated</h3>
              <p>Secure JWT token-based authentication</p>
            </div>
            <div className="feature">
              <span className="feature-icon">👥</span>
              <h3>Multi-user</h3>
              <p>See who's online and editing</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Show collaborative editor
  return (
    <div className="App">
      <CollaborativeEditor 
        documentId={documentId} 
        userId={userData.user_id}
      />
    </div>
  );
}

export default App;