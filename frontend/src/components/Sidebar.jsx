import { Search, Plus, Trash2, MessageSquare, FileText, Database, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

export default function Sidebar({ chats, activeId, onSelect, onNew, onDelete, onSearch, type, user, onLogout }) {
    const [searchTerm, setSearchTerm] = useState('');

    const handleSearch = (e) => {
        setSearchTerm(e.target.value);
        onSearch?.(e.target.value);
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        const now = new Date();
        const diffMs = now - d;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays}d ago`;
        return d.toLocaleDateString();
    };

    const getSidebarInfo = () => {
        switch (type) {
            case 'document': return { label: '📄 Document Chats', icon: FileText };
            case 'spreadsheet': return { label: '📊 Spreadsheet Chats', icon: Database };
            case 'policy': return { label: '🛡️ Policy Chats', icon: ShieldCheck };
            default: return { label: '💬 General Chats', icon: MessageSquare };
        }
    };

    const { label, icon: Icon } = getSidebarInfo();

    return (
        <div className="sidebar">
            <div className="sidebar-header">
                <div className="top-row">
                    <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {label}
                    </span>
                    <button className="btn-icon" onClick={onNew} title="New Chat">
                        <Plus size={18} />
                    </button>
                </div>
                <div className="sidebar-search">
                    <Search size={14} className="search-icon" />
                    <input
                        type="text"
                        placeholder="Search chats..."
                        value={searchTerm}
                        onChange={handleSearch}
                    />
                </div>
            </div>

            <div className="sidebar-chats">
                {chats.length === 0 ? (
                    <div style={{ padding: '24px 12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                        No chats yet. Click + to start.
                    </div>
                ) : (
                    chats.map(chat => (
                        <div
                            key={chat.id}
                            className={`chat-item ${chat.id === activeId ? 'active' : ''}`}
                            onClick={() => onSelect(chat.id)}
                        >
                            <Icon size={16} style={{ color: 'var(--text-muted)', minWidth: 16 }} />
                            <div className="chat-info">
                                <div className="chat-title">{chat.title}</div>
                                <div className="chat-date">{formatDate(chat.updated_at || chat.created_at)}</div>
                            </div>
                            <button
                                className="btn-icon chat-delete"
                                onClick={(e) => { e.stopPropagation(); onDelete(chat.id); }}
                                title="Delete chat"
                            >
                                <Trash2 size={14} />
                            </button>
                        </div>
                    ))
                )}
            </div>

            <div className="sidebar-footer">
                <div className="user-info">
                    <div className="user-avatar">{user?.username?.[0]?.toUpperCase() || 'U'}</div>
                    <span>{user?.username}</span>
                </div>
                <button className="btn-icon" onClick={onLogout} title="Logout"
                    style={{ color: 'var(--danger)', fontSize: '12px' }}>
                    Logout
                </button>
            </div>
        </div>
    );
}
