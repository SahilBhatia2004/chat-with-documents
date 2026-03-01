import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import Sidebar from '../components/Sidebar';
import ChatMessage from '../components/ChatMessage';
import MessageInput from '../components/MessageInput';
import DocumentUpload from '../components/DocumentUpload';
import { ArrowLeft, Database, Upload } from 'lucide-react';

export default function SpreadsheetChatPage() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [chats, setChats] = useState([]);
    const [activeChat, setActiveChat] = useState(null);
    const [messages, setMessages] = useState([]);
    const [streaming, setStreaming] = useState(false);
    const [showUpload, setShowUpload] = useState(false);
    const [uploads, setUploads] = useState([]);
    const [activeTimestamp, setActiveTimestamp] = useState(null);
    const messagesEndRef = useRef(null);

    useEffect(() => { loadChats(); }, []);
    useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    const loadChats = async (search = '') => {
        try {
            const params = search ? { search } : {};
            const res = await api.get('/chat/spreadsheet', { params });
            setChats(res.data);
        } catch (err) { console.error('Failed to load chats:', err); }
    };

    const loadChat = async (chatId) => {
        try {
            const res = await api.get(`/chat/spreadsheet/${chatId}`);
            setActiveChat(res.data);
            setMessages(res.data.messages || []);
            setUploads(res.data.uploads || []);
            if (res.data.uploads && res.data.uploads.length > 0) {
                setActiveTimestamp(res.data.uploads[res.data.uploads.length - 1].upload_timestamp);
            } else {
                setActiveTimestamp(null);
            }
            setShowUpload(false);
        } catch (err) { console.error('Failed to load chat:', err); }
    };

    const createChat = async () => {
        try {
            const res = await api.post('/chat/spreadsheet', { title: 'New Spreadsheet Chat' });
            await loadChats();
            await loadChat(res.data.id);
            setShowUpload(true);
        } catch (err) { console.error('Failed to create chat:', err); }
    };

    const deleteChat = async (chatId) => {
        if (!confirm('Delete this spreadsheet chat and all associated data?')) return;
        try {
            await api.delete(`/chat/spreadsheet/${chatId}`);
            if (activeChat?.id === chatId) {
                setActiveChat(null);
                setMessages([]);
                setUploads([]);
                setActiveTimestamp(null);
            }
            await loadChats();
        } catch (err) { console.error('Failed to delete chat:', err); }
    };

    const handleUpload = async (files) => {
        if (!activeChat) return;
        const formData = new FormData();
        files.forEach(f => formData.append('files', f));

        const res = await api.post(`/chat/spreadsheet/${activeChat.id}/upload`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });

        setActiveTimestamp(res.data.upload_timestamp);
        setShowUpload(false);
        await loadChat(activeChat.id);
        await loadChats();
    };

    const sendMessage = async (content, tableMode = false) => {
        if (!activeChat || streaming) return;
        const userMsg = { id: Date.now(), role: 'user', content, created_at: new Date().toISOString() };
        setMessages(prev => [...prev, userMsg]);
        setStreaming(true);

        const assistantMsg = { id: Date.now() + 1, role: 'assistant', content: '', created_at: new Date().toISOString() };
        setMessages(prev => [...prev, assistantMsg]);

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`/api/chat/spreadsheet/${activeChat.id}/message`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ content, upload_timestamp: activeTimestamp })
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
                            if (data.table_data) {
                                const tableMarker = `\n\n<!--TABLE_DATA:${JSON.stringify(data.table_data)}-->`;
                                setMessages(prev => {
                                    const updated = [...prev];
                                    const current = updated[updated.length - 1];
                                    updated[updated.length - 1] = { ...current, content: current.content + tableMarker };
                                    return updated;
                                });
                            }
                            if (data.done) {
                                if (data.title) {
                                    setActiveChat(prev => ({ ...prev, title: data.title }));
                                    loadChats();
                                }
                            }
                        } catch (e) { /* ignore parse errors */ }
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

    const handleLogout = () => { logout(); navigate('/login'); };

    return (
        <div className="chat-layout">
            <Sidebar
                chats={chats} activeId={activeChat?.id}
                onSelect={loadChat} onNew={createChat}
                onDelete={deleteChat} onSearch={loadChats}
                type="spreadsheet" user={user} onLogout={handleLogout}
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
                                {uploads.length > 0 && (
                                    <span style={{ fontSize: '12px', color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                        <Database size={14} /> {uploads.length} sheets(s)
                                    </span>
                                )}
                                <button className="btn btn-ghost" style={{ fontSize: '12px', padding: '6px 12px' }}
                                    onClick={() => setShowUpload(!showUpload)}>
                                    <Upload size={14} /> Upload
                                </button>
                            </div>
                        </div>

                        {showUpload && (
                            <div className="upload-container animated-fade-in">
                                <DocumentUpload onUpload={handleUpload} disabled={streaming} />
                            </div>
                        )}

                        <div className="chat-messages">
                            {messages.length === 0 && !showUpload ? (
                                <div className="empty-state">
                                    <Database size={48} className="icon" />
                                    <h3>Upload spreadsheets to analyze</h3>
                                    <p>Upload XLSX, XLS, or CSV files. All data will be preprocessed for automated SQL querying.</p>
                                    <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
                                        <Upload size={16} /> Upload Spreadsheets
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
                            placeholder="Ask a question about your spreadsheets..."
                        />
                    </>
                ) : (
                    <div className="empty-state">
                        <Database size={64} className="icon" />
                        <h3>Spreadsheet Chat</h3>
                        <p>Analyze tabular data using AI-generated SQL queries on your uploaded spreadsheets.</p>
                        <button className="btn btn-primary" onClick={createChat}>New Spreadsheet Chat</button>
                    </div>
                )}
            </div>
        </div>
    );
}
