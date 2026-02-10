import { useState } from 'react';
import axios from 'axios';
import './Login.css';

function Login({ onLogin }) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setError('');
    setLoading(true);

    try {
      const response = await axios.post('/api/auth/login', {
        username,
        password
      });
      
      // Save token and user info
      localStorage.setItem('token', response.data.access_token);
      localStorage.setItem('userId', response.data.user_id);
      localStorage.setItem('username', response.data.username);
      
      console.log('✅ Login successful:', response.data);
      onLogin(response.data);
    } catch (error) {
      console.error('❌ Login failed:', error);
      setError(error.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    setError('');
    setLoading(true);

    if (!email || !username || !password) {
      setError('Please fill in all fields');
      setLoading(false);
      return;
    }

    try {
      const response = await axios.post('/api/auth/register', {
        username,
        email,
        password
      });
      
      // Save token and user info
      localStorage.setItem('token', response.data.access_token);
      localStorage.setItem('userId', response.data.user_id);
      localStorage.setItem('username', response.data.username);
      
      console.log('✅ Registration successful:', response.data);
      onLogin(response.data);
    } catch (error) {
      console.error('❌ Registration failed:', error);
      setError(error.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (isRegistering) {
      handleRegister();
    } else {
      handleLogin();
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>🚀 Collaborative Editor</h1>
        <p className="subtitle">Real-time collaboration, powered by WebSockets</p>
        
        <div className="auth-tabs">
          <button 
            className={!isRegistering ? 'active' : ''}
            onClick={() => setIsRegistering(false)}
          >
            Login
          </button>
          <button 
            className={isRegistering ? 'active' : ''}
            onClick={() => setIsRegistering(true)}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="error-message">{error}</div>}
          
          {isRegistering && (
            <div className="form-group">
              <label>Email</label>
              <input 
                type="email" 
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          )}
          
          <div className="form-group">
            <label>Username</label>
            <input 
              type="text" 
              placeholder="Enter username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          
          <div className="form-group">
            <label>Password</label>
            <input 
              type="password" 
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          
          <button 
            type="submit" 
            className="submit-button"
            disabled={loading}
          >
            {loading ? 'Please wait...' : (isRegistering ? 'Create Account' : 'Login')}
          </button>
        </form>

        <div className="demo-credentials">
          <p><strong>Demo Test:</strong></p>
          <p>1. Register a new account</p>
          <p>2. Open another browser window (incognito)</p>
          <p>3. Register with different username</p>
          <p>4. Join the same document ID to collaborate!</p>
        </div>
      </div>
    </div>
  );
}

export default Login;