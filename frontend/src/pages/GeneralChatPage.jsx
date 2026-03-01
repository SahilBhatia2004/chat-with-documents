import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import Sidebar from '../components/Sidebar';
import ChatMessage from '../components/ChatMessage';
import MessageInput from '../components/MessageInput';
import { ArrowLeft, MessageSquare } from 'lucide-react';

export default function GeneralChatPage() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [chats, setChats] = useState([]);
    const [activeChat, setActiveChat] = useState(null);
    const [messages, setMessages] = useState([]);
    const [streaming, setStreaming] = useState(false);
    const messagesEndRef = useRef(null);

    useEffect(() => { loadChats(); }, []);
    useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

    const loadChats = async (search = '') => {
        try {
            const params = search ? { search } : {};
            const res = await api.get('/chat/general', { params });
            setChats(res.data);
        } catch (err) { console.error('Failed to load chats:', err); }
    };

    const loadChat = async (chatId) => {
        try {
            const res = await api.get(`/chat/general/${chatId}`);
            setActiveChat(res.data);
            setMessages(res.data.messages || []);
        } catch (err) { console.error('Failed to load chat:', err); }
    };

    const createChat = async () => {
        try {
            const res = await api.post('/chat/general', { title: 'New Chat' });
            await loadChats();
            await loadChat(res.data.id);
        } catch (err) { console.error('Failed to create chat:', err); }
    };

    const deleteChat = async (chatId) => {
        if (!confirm('Delete this chat?')) return;
        try {
            await api.delete(`/chat/general/${chatId}`);
            if (activeChat?.id === chatId) {
                setActiveChat(null);
                setMessages([]);
            }
            await loadChats();
        } catch (err) { console.error('Failed to delete chat:', err); }
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
            const response = await fetch(`/api/chat/general/${activeChat.id}/message`, {
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
                                // Update chat title in sidebar
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
                updated[updated.length - 1] = { ...updated[updated.length - 1], content: 'Error: Failed to get response. Please try again.' };
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
                chats={chats}
                activeId={activeChat?.id}
                onSelect={loadChat}
                onNew={createChat}
                onDelete={deleteChat}
                onSearch={loadChats}
                type="general"
                user={user}
                onLogout={handleLogout}
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
                        </div>

                        <div className="chat-messages">
                            {messages.length === 0 ? (
                                <div className="empty-state">
                                    <MessageSquare size={48} className="icon" />
                                    <h3>Start a conversation</h3>
                                    <p>Ask me anything. I'm your AI assistant operating in a secure airgapped environment.</p>
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

                        <MessageInput onSend={sendMessage} disabled={streaming} placeholder="Type your message..." />
                    </>
                ) : (
                    <div className="empty-state">
                        <MessageSquare size={64} className="icon" />
                        <h3>General Chat</h3>
                        <p>Select an existing chat or create a new one to start chatting with the AI assistant.</p>
                        <button className="btn btn-primary" onClick={createChat}>New Chat</button>
                    </div>
                )}
            </div>
        </div>
    );
}
