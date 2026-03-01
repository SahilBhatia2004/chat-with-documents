import { Bot, User } from 'lucide-react';

export default function ChatMessage({ message }) {
    const isUser = message.role === 'user';

    // Parse content to extract table data and chart data
    let textContent = message.content || '';
    let tableData = null;

    // Extract embedded table data
    const tableMatch = textContent.match(/<!--TABLE_DATA:(.*?)-->/s);
    if (tableMatch) {
        try {
            tableData = JSON.parse(tableMatch[1]);
        } catch (e) { /* ignore parse errors */ }
        textContent = textContent.replace(/<!--TABLE_DATA:.*?-->/s, '').trim();
    }


    return (
        <div className="message">
            <div className={`message-avatar ${isUser ? 'user' : 'assistant'}`}>
                {isUser ? <User size={18} /> : <Bot size={18} />}
            </div>
            <div className="message-content">
                <div className="role">{isUser ? 'You' : 'Assistant'}</div>
                <div className="text">{textContent}</div>

                {tableData && tableData.data && tableData.data.length > 0 && (
                    <div className="result-table-wrapper" style={{ marginTop: '12px' }}>
                        <table className="result-table">
                            <thead>
                                <tr>
                                    {tableData.columns.map((col, i) => (
                                        <th key={i}>{col}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {tableData.data.slice(0, 50).map((row, i) => (
                                    <tr key={i}>
                                        {tableData.columns.map((col, j) => (
                                            <td key={j}>{row[col] != null ? String(row[col]) : ''}</td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {tableData.row_count > 50 && (
                            <div style={{ padding: '8px 14px', color: 'var(--text-muted)', fontSize: '12px' }}>
                                Showing 50 of {tableData.row_count} rows
                            </div>
                        )}
                    </div>
                )}

            </div>
        </div>
    );
}
