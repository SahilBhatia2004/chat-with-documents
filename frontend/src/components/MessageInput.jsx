import { useState, useRef } from 'react';
import { Send, Database } from 'lucide-react';

export default function MessageInput({ onSend, disabled, placeholder }) {
    const [value, setValue] = useState('');
    const [tableMode, setTableMode] = useState(false);
    const textareaRef = useRef(null);

    const handleSend = () => {
        if (value.trim() && !disabled) {
            onSend(value.trim(), tableMode);
            setValue('');
            if (textareaRef.current) {
                textareaRef.current.style.height = '48px';
            }
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleInput = (e) => {
        setValue(e.target.value);
        // Auto-resize
        const el = e.target;
        el.style.height = '48px';
        el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    };

    return (
        <div className="chat-input-container">
            <div className="chat-input-wrapper">
                <button
                    className={`btn-icon table-toggle-btn ${tableMode ? 'active' : ''}`}
                    onClick={() => setTableMode(!tableMode)}
                    disabled={disabled}
                    title={tableMode ? "Table Mode Active (SQL)" : "Switch to Table Mode (SQL)"}
                >
                    <Database size={20} />
                </button>
                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={handleInput}
                    onKeyDown={handleKeyDown}
                    placeholder={tableMode ? "Ask a question about tabular data..." : (placeholder || "Type your message...")}
                    disabled={disabled}
                    rows={1}
                />
                <button
                    className="send-btn"
                    onClick={handleSend}
                    disabled={disabled || !value.trim()}
                    title="Send message"
                >
                    <Send size={20} />
                </button>
            </div>
        </div>
    );
}
