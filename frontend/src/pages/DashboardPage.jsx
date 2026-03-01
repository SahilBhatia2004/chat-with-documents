import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { MessageSquare, FileText, Database, ShieldCheck, Shield, LogOut } from 'lucide-react';

export default function DashboardPage() {
    const navigate = useNavigate();
    const { user, logout } = useAuth();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <div className="dashboard-container">
            <div style={{ position: 'absolute', top: '24px', right: '32px' }}>
                <button className="btn btn-ghost" onClick={handleLogout}>
                    <LogOut size={16} /> Logout
                </button>
            </div>

            <div className="dashboard-header">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', marginBottom: '16px' }}>
                    <div style={{
                        width: '56px', height: '56px', borderRadius: '14px',
                        background: 'linear-gradient(135deg, #3b82f6, #10b981)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                        <Shield size={32} color="white" />
                    </div>
                </div>
                <h1>Defense Chat System</h1>
                <p>Welcome, <strong style={{ color: 'var(--accent)' }}>{user?.username}</strong>. Select an operation mode.</p>
            </div>

            <div className="dashboard-cards">
                <div className="dashboard-card" onClick={() => navigate('/chat/general')}>
                    <div className="icon-wrapper" style={{ background: 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(59,130,246,0.05))' }}>
                        <MessageSquare size={32} style={{ color: '#3b82f6' }} />
                    </div>
                    <h2>General Chat</h2>
                    <p>AI-powered chat assistant for day-to-day queries, briefings, and operational support.</p>
                </div>

                <div className="dashboard-card" onClick={() => navigate('/chat/document')}>
                    <div className="icon-wrapper" style={{ background: 'linear-gradient(135deg, rgba(16,185,129,0.2), rgba(16,185,129,0.05))' }}>
                        <FileText size={32} style={{ color: '#10b981' }} />
                    </div>
                    <h2>Chat with Documents</h2>
                    <p>Upload documents for AI analysis, data extraction, SQL queries, and chart visualization.</p>
                </div>

                <div className="dashboard-card" onClick={() => navigate('/chat/spreadsheet')}>
                    <div className="icon-wrapper" style={{ background: 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(59,130,246,0.05))' }}>
                        <Database size={32} style={{ color: '#3b82f6' }} />
                    </div>
                    <h2>Spreadsheet Chat</h2>
                    <p>Upload Excel/CSV sheets for automated analysis, SQL data querying, and interactive reporting.</p>
                </div>

                <div className="dashboard-card" onClick={() => navigate('/chat/policy')}>
                    <div className="icon-wrapper" style={{ background: 'linear-gradient(135deg, rgba(16,185,129,0.2), rgba(16,185,129,0.05))' }}>
                        <ShieldCheck size={32} style={{ color: '#10b981' }} />
                    </div>
                    <h2>Internal Policies</h2>
                    <p>Access and query sensitive company policy documents using high-precision semantic search.</p>
                </div>
            </div>

            <div style={{ marginTop: '48px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                <p>🔒 Airgapped Environment • No Internet Connection • Classified Operations</p>
            </div>
        </div>
    );
}
