import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import Sidebar from '../components/Sidebar';
import ChatMessage from '../components/ChatMessage';
import MessageInput from '../components/MessageInput';
import DocumentUpload from '../components/DocumentUpload';
import { ArrowLeft, ShieldCheck, Upload, Trash2, Search as SearchIcon, X } from 'lucide-react';

export default function PolicyChatPage() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [chats, setChats] = useState([]);
    const [activeChat, setActiveChat] = useState(null);
    const [messages, setMessages] = useState([]);
    const [streaming, setStreaming] = useState(false);
    const [showUpload, setShowUpload] = useState(false);
    const [uploads, setUploads] = useState([]);
    const [docSearch, setDocSearch] = useState('');
    const [showDocManager, setShowDocManager] = useState(false);
    const messagesEndRef = useRef(null);

    useEffect(() => { loadChats(); }, []);
    useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    const loadChats = async (search = '') => {
        try {
            const params = search ? { search } : {};
            const res = await api.get('/chat/policy', { params });
            setChats(res.data);
        } catch (err) { console.error('Failed to load chats:', err); }
    };

    const loadChat = async (chatId) => {
        try {
            const res = await api.get(`/chat/policy/${chatId}`);
            setActiveChat(res.data);
            setMessages(res.data.messages || []);
            setUploads(res.data.uploads || []);
            setShowUpload(false);
        } catch (err) { console.error('Failed to load chat:', err); }
    };

    const createChat = async () => {
        try {
            const res = await api.post('/chat/policy', { title: 'New Policy Chat' });
            await loadChats();
            await loadChat(res.data.id);
            setShowUpload(true);
        } catch (err) { console.error('Failed to create chat:', err); }
    };

    const deleteChat = async (chatId) => {
        if (!confirm('Delete this policy chat and all indexed documents?')) return;
        try {
            await api.delete(`/chat/policy/${chatId}`);
            if (activeChat?.id === chatId) {
                setActiveChat(null);
                setMessages([]);
                setUploads([]);
            }
            await loadChats();
        } catch (err) { console.error('Failed to delete chat:', err); }
    };

    const handleUpload = async (files) => {
        if (!activeChat) return;
        const formData = new FormData();
        files.forEach(f => formData.append('files', f));

        const res = await api.post(`/chat/policy/${activeChat.id}/upload`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });

        setShowUpload(false);
        await loadChat(activeChat.id);
        await loadChats();
    };

    const deleteDocument = async (docId) => {
        if (!confirm('Delete this specific document from policy index?')) return;
        try {
            await api.delete(`/chat/policy/${activeChat.id}/document/${docId}`);
            await loadChat(activeChat.id);
        } catch (err) { console.error('Failed to delete document:', err); }
    };

    const sendMessage = async (content) => {
        if (!activeChat || streaming) return;
        const userMsg = { id: Date.now(), role: 'user', content, created_at: new Date().toISOString() };
        setMessages(prev => [...prev, userMsg]);
        setStreaming(true);

        const assistantMsg = { id: Date.now() + 1, role: 'assistant', content: '', created_at: new Date().toISOString() };
        setMessages(prev => [...prev, assistantMsg]);

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`/api/chat/policy/${activeChat.id}/message`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ content })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullContent = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const text = decoder.decode(value, { stream: true });
                const lines = text.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.content) {
                                fullContent += data.content;
                                setMessages(prev => {
                                    const updated = [...prev];
                                    updated[updated.length - 1] = { ...updated[updated.length - 1], content: fullContent };
                                    return updated;
                                });
                            }
                            if (data.done) {
                                if (data.title) {
                                    setActiveChat(prev => ({ ...prev, title: data.title }));
                                    loadChats();
                                }
                            }
                        } catch (e) { }
                    }
                }
            }
        } catch (err) {
            console.error('Streaming error:', err);
            setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1] = { ...updated[updated.length - 1], content: 'Error: Failed to get response.' };
                return updated;
            });
        } finally {
            setStreaming(false);
        }
    };

    const filteredUploads = uploads.filter(u =>
        u.filename.toLowerCase().includes(docSearch.toLowerCase())
    );

    const handleLogout = () => { logout(); navigate('/login'); };

    return (
        <div className="chat-layout">
            <Sidebar
                chats={chats} activeId={activeChat?.id}
                onSelect={loadChat} onNew={createChat}
                onDelete={deleteChat} onSearch={loadChats}
                type="policy" user={user} onLogout={handleLogout}
            />

            <div className="chat-main">
                {activeChat ? (
                    <>
                        <div className="chat-header">
                            <div className="nav-header">
                                <button className="btn-icon back-btn" onClick={() => navigate('/dashboard')}>
                                    <ArrowLeft size={18} />
                                </button>
                                <h2>{activeChat.title}</h2>
                            </div>
                            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                <button className="btn btn-ghost" style={{ fontSize: '12px', padding: '6px 12px' }}
                                    onClick={() => setShowDocManager(!showDocManager)}>
                                    <ShieldCheck size={14} /> Documents ({uploads.length})
                                </button>
                                <button className="btn btn-ghost" style={{ fontSize: '12px', padding: '6px 12px' }}
                                    onClick={() => setShowUpload(!showUpload)}>
                                    <Upload size={14} /> Upload
                                </button>
                            </div>
                        </div>

                        {showDocManager && (
                            <div className="doc-manager-overlay animated-fade-in">
                                <div className="doc-manager-panel">
                                    <div className="panel-header">
                                        <h3>Manage Policy Documents</h3>
                                        <button className="btn-icon" onClick={() => setShowDocManager(false)}><X size={18} /></button>
                                    </div>
                                    <div className="panel-search">
                                        <SearchIcon size={16} className="search-icon" />
                                        <input
                                            type="text"
                                            placeholder="Search documents by name..."
                                            value={docSearch}
                                            onChange={(e) => setDocSearch(e.target.value)}
                                        />
                                    </div>
                                    <div className="doc-list">
                                        {filteredUploads.length === 0 ? (
                                            <p className="no-docs">No documents found matching "{docSearch}"</p>
                                        ) : (
                                            filteredUploads.map(doc => (
                                                <div key={doc.id} className="doc-item">
                                                    <div className="doc-info">
                                                        <span className="doc-name">{doc.filename}</span>
                                                        <span className="doc-date">{new Date(doc.created_at).toLocaleDateString()}</span>
                                                    </div>
                                                    <button className="btn-icon delete-btn" onClick={() => deleteDocument(doc.id)} title="Delete document">
                                                        <Trash2 size={16} />
                                                    </button>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}

                        {showUpload && (
                            <div className="upload-container animated-fade-in">
                                <DocumentUpload onUpload={handleUpload} disabled={streaming} />
                            </div>
                        )}

                        <div className="chat-messages" style={{ opacity: showDocManager ? 0.3 : 1 }}>
                            {messages.length === 0 && !showUpload ? (
                                <div className="empty-state">
                                    <ShieldCheck size={48} className="icon" />
                                    <h3>Secure Policy Assistant</h3>
                                    <p>Upload internal policy papers to create a secure knowledge base for query resolution.</p>
                                    <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
                                        <Upload size={16} /> Upload Policy Papers
                                    </button>
                                </div>
                            ) : (
                                messages.map(msg => <ChatMessage key={msg.id} message={msg} />)
                            )}
                            {streaming && (
                                <div className="loading-dots" style={{ marginLeft: '48px' }}>
                                    <span></span><span></span><span></span>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        <MessageInput
                            onSend={sendMessage} disabled={streaming}
                            placeholder="Search in policy database..."
                        />
                    </>
                ) : (
                    <div className="empty-state">
                        <ShieldCheck size={64} className="icon" />
                        <h3>Internal Policies Chat</h3>
                        <p>High-precision semantic search across your organization's sensitive policy documentation.</p>
                        <button className="btn btn-primary" onClick={createChat}>New Policy Chat</button>
                    </div>
                )}
            </div>
        </div>
    );
}
