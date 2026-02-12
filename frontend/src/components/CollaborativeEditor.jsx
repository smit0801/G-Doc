import React, { useEffect, useRef, useState } from 'react';
import Editor from '@monaco-editor/react';
import Chat from './Chat';
import './CollaborativeEditor.css';

console.log("🚀 V3 LOADED - If you don't see this, rebuild docker!");

const CollaborativeEditor = ({ documentId, userId }) => {
  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const pendingContentRef = useRef(null);
  const isRemoteUpdate = useRef(false);
  
  const [provider, setProvider] = useState(null);
  const [activeUsers, setActiveUsers] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [username, setUsername] = useState('');
  const chatMessageCallback = useRef(null);

  useEffect(() => {
    if (!documentId) return;

    const token = localStorage.getItem('token');
    const storedUsername = localStorage.getItem('username') || 'Anonymous';
    setUsername(storedUsername);
    
    if (!token) {
      console.error('❌ No token found. Please login first.');
      return;
    }

    const wsUrl = `ws://localhost:8000/ws/${documentId}?token=${token}`;
    console.log('🔌 Connecting to:', wsUrl);
    
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('✅ WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      // console.log('📨 Received:', message); 

      switch (message.type) {
        case 'init':
          setActiveUsers(message.active_users || []);
          
          const initContent = message.content || message.document_content;
          
          if (initContent !== undefined && initContent !== null) {
            if (editorRef.current) {
              console.log('📄 Init: Setting content immediately.');
              isRemoteUpdate.current = true;
              editorRef.current.setValue(initContent);
              isRemoteUpdate.current = false;
            } else {
              console.log('⏳ Init: Editor loading. Queuing content.');
              pendingContentRef.current = initContent;
            }
          }
          break;
        
        case 'user_joined':
          setActiveUsers(prev => [...prev, message.user_id]);
          break;
        
        case 'user_left':
          setActiveUsers(prev => prev.filter(id => id !== message.user_id));
          break;
        
        case 'update':
          if (editorRef.current && message.data) {
            const currentValue = editorRef.current.getValue();
            if (message.data.content !== undefined && message.data.content !== currentValue) {
              const position = editorRef.current.getPosition();
              
              isRemoteUpdate.current = true;
              editorRef.current.setValue(message.data.content);
              isRemoteUpdate.current = false;
              
              if (position) {
                editorRef.current.setPosition(position);
              }
            }
          }
          break;
        
        case 'chat':
          if (chatMessageCallback.current) {
            chatMessageCallback.current(message);
          }
          break;
      }
    };

    ws.onclose = (event) => {
      console.log('❌ WebSocket disconnected:', event.reason);
      setIsConnected(false);
      if (event.code === 1008) {
        alert(`Connection failed: ${event.reason}\nPlease login again.`);
        localStorage.removeItem('token');
        window.location.reload();
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    const providerRef = { ws };
    setProvider(providerRef);

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [documentId]);

  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Use setTimeout to ensure we run AFTER Monaco's internal init
    setTimeout(() => {
      if (pendingContentRef.current !== null) {
        console.log('🚀 Mount: Applying queued content:', pendingContentRef.current);
        isRemoteUpdate.current = true;
        editor.setValue(pendingContentRef.current);
        isRemoteUpdate.current = false;
        pendingContentRef.current = null;
      }
    }, 10);

    editor.updateOptions({
      readOnly: false,
      minimap: { enabled: true },
      fontSize: 14,
      lineNumbers: 'on',
      roundedSelection: false,
      scrollBeyondLastLine: false,
      automaticLayout: true,
    });
    
    editor.onDidChangeCursorPosition((e) => handleCursorChange(e));
    console.log('✅ Monaco editor mounted');
  };

  const handleEditorChange = (value, event) => {
    // 🛑 BLOCKER: Stop remote updates from echoing back
    if (isRemoteUpdate.current) {
      return;
    }

    if (provider && provider.ws && provider.ws.readyState === WebSocket.OPEN) {
      provider.ws.send(JSON.stringify({
        type: 'update',
        data: { content: value },
        timestamp: Date.now(),
      }));
    }
  };

  const handleCursorChange = (e) => {
    if (!provider || !provider.ws || provider.ws.readyState !== WebSocket.OPEN) return;
    const position = e.position;
    const selection = editorRef.current?.getSelection();
    provider.ws.send(JSON.stringify({
      type: 'cursor',
      position: { lineNumber: position.lineNumber, column: position.column },
      selection: selection ? {
        startLineNumber: selection.startLineNumber,
        startColumn: selection.startColumn,
        endLineNumber: selection.endLineNumber,
        endColumn: selection.endColumn,
      } : null,
    }));
  };

  return (
    <div className="collaborative-editor">
      <div className="editor-header">
        <div className="header-left">
          <h2>Document: {documentId}</h2>
          <span className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
          </span>
        </div>
        <div className="active-users">
          <span>👥 Active users ({activeUsers.length}):</span>
          <div className="user-list">
            {activeUsers.map((user, index) => (
              <span key={user} className="user-badge" style={{ backgroundColor: getUserColor(index) }}>
                {user}
              </span>
            ))}
          </div>
        </div>
      </div>
      
      <div className="editor-container">
        <Editor
          height="100%"
          defaultLanguage="javascript"
          defaultValue="" 
          theme="vs-dark"
          onMount={handleEditorDidMount}
          onChange={handleEditorChange}
          options={{
            minimap: { enabled: true },
            fontSize: 14,
            wordWrap: 'on',
            automaticLayout: true,
          }}
        />
      </div>
      
      <Chat 
        websocket={provider?.ws} 
        username={username}
        isConnected={isConnected}
        onChatMessage={chatMessageCallback}
      />
    </div>
  );
};

function getUserColor(index) {
  const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2'];
  return colors[index % colors.length];
}

export default CollaborativeEditor;




















































// import React, { useEffect, useRef, useState } from 'react';
// import Editor from '@monaco-editor/react';
// import Chat from './Chat';
// import './CollaborativeEditor.css';

// const CollaborativeEditor = ({ documentId, userId }) => {
//   const editorRef = useRef(null);
//   const monacoRef = useRef(null);
//   const [provider, setProvider] = useState(null);
//   const [activeUsers, setActiveUsers] = useState([]);
//   const [isConnected, setIsConnected] = useState(false);
//   const [username, setUsername] = useState('');
//   const chatMessageCallback = useRef(null);

//   useEffect(() => {
//     if (!documentId) return;

//     // Get token from localStorage
//     const token = localStorage.getItem('token');
//     const storedUsername = localStorage.getItem('username') || 'Anonymous';
//     setUsername(storedUsername);
    
//     if (!token) {
//       console.error('❌ No token found. Please login first.');
//       return;
//     }

//     // Create WebSocket connection WITH token
//     const wsUrl = `ws://localhost:8000/ws/${documentId}?token=${token}`;
//     console.log('🔌 Connecting to:', wsUrl);
    
//     const ws = new WebSocket(wsUrl);

//     ws.onopen = () => {
//       console.log('✅ WebSocket connected');
//       setIsConnected(true);
//     };

//     ws.onmessage = (event) => {
//       const message = JSON.parse(event.data);
//       console.log('📨 Received:', message);

//       switch (message.type) {
//         case 'init':
//           setActiveUsers(message.active_users || []);
//           if (message.document_content && editorRef.current) {
//             editorRef.current.setValue(message.document_content);
//             console.log('📄 Document content initialized from DB');
//           }
//           break;
        
//         case 'user_joined':
//           setActiveUsers(prev => [...prev, message.user_id]);
//           break;
        
//         case 'user_left':
//           setActiveUsers(prev => prev.filter(id => id !== message.user_id));
//           break;
        
//         case 'update':
//           // Handle document updates
//           if (editorRef.current && message.data) {
//             // Apply updates to editor
//             const currentValue = editorRef.current.getValue();
//             if (message.data.content && message.data.content !== currentValue) {
//               editorRef.current.setValue(message.data.content);
//             }
//           }
//           break;
        
//         case 'chat':
//           // Pass chat messages to Chat component via callback
//           if (chatMessageCallback.current) {
//             chatMessageCallback.current(message);
//           }
//           break;
//       }
//     };

//     ws.onclose = (event) => {
//       console.log('❌ WebSocket disconnected:', event.reason);
//       setIsConnected(false);
      
//       // Show reason if connection was rejected
//       if (event.code === 1008) {
//         alert(`Connection failed: ${event.reason}\nPlease login again.`);
//         localStorage.removeItem('token');
//         window.location.reload();
//       }
//     };

//     ws.onerror = (error) => {
//       console.error('WebSocket error:', error);
//     };

//     // Store WebSocket reference
//     const providerRef = { ws };
//     setProvider(providerRef);

//     return () => {
//       if (ws.readyState === WebSocket.OPEN) {
//         ws.close();
//       }
//     };
//   }, [documentId]);

//   const handleEditorDidMount = (editor, monaco) => {
//     editorRef.current = editor;
//     monacoRef.current = monaco;

//     // Set up editor options for collaboration
//     editor.updateOptions({
//       readOnly: false,
//       minimap: { enabled: true },
//       fontSize: 14,
//       lineNumbers: 'on',
//       roundedSelection: false,
//       scrollBeyondLastLine: false,
//       automaticLayout: true,
//     });

//     console.log('✅ Monaco editor mounted');
//   };

//   const handleEditorChange = (value, event) => {
//     // Send updates to server
//     if (provider && provider.ws && provider.ws.readyState === WebSocket.OPEN) {
//       provider.ws.send(JSON.stringify({
//         type: 'update',
//         data: {
//           content: value,
//         },
//         timestamp: Date.now(),
//       }));
//     }
//   };

//   const handleCursorChange = (e) => {
//     if (!provider || !provider.ws || provider.ws.readyState !== WebSocket.OPEN) return;

//     const position = e.position;
//     const selection = editorRef.current?.getSelection();

//     provider.ws.send(JSON.stringify({
//       type: 'cursor',
//       position: {
//         lineNumber: position.lineNumber,
//         column: position.column,
//       },
//       selection: selection ? {
//         startLineNumber: selection.startLineNumber,
//         startColumn: selection.startColumn,
//         endLineNumber: selection.endLineNumber,
//         endColumn: selection.endColumn,
//       } : null,
//     }));
//   };

//   return (
//     <div className="collaborative-editor">
//       <div className="editor-header">
//         <div className="header-left">
//           <h2>Document: {documentId}</h2>
//           <span className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
//             {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
//           </span>
//         </div>
//         <div className="active-users">
//           <span>👥 Active users ({activeUsers.length}):</span>
//           <div className="user-list">
//             {activeUsers.map((user, index) => (
//               <span key={user} className="user-badge" style={{ backgroundColor: getUserColor(index) }}>
//                 {user}
//               </span>
//             ))}
//           </div>
//         </div>
//       </div>
      
//       <div className="editor-container">
//         <Editor
//           height="100%"
//           defaultLanguage="javascript"
//           defaultValue="// Start typing to collaborate in real-time!\n// Your changes will be synced to all connected users.\n\nfunction hello() {\n  console.log('Hello, collaborative world!');\n}\n"
//           theme="vs-dark"
//           onMount={handleEditorDidMount}
//           onChange={handleEditorChange}
//           options={{
//             minimap: { enabled: true },
//             fontSize: 14,
//             wordWrap: 'on',
//             automaticLayout: true,
//           }}
//         />
//       </div>
      
//       {/* Chat Component */}
//       <Chat 
//         websocket={provider?.ws} 
//         username={username}
//         isConnected={isConnected}
//         onChatMessage={chatMessageCallback}
//       />
//     </div>
//   );
// };

// // Helper function to generate consistent colors for users
// function getUserColor(index) {
//   const colors = [
//     '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', 
//     '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2'
//   ];
//   return colors[index % colors.length];
// }

// export default CollaborativeEditor;