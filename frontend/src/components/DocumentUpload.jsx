import { useState, useRef } from 'react';
import { Upload, FileText, X } from 'lucide-react';

export default function DocumentUpload({ onUpload, disabled }) {
    const [files, setFiles] = useState([]);
    const [dragging, setDragging] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const inputRef = useRef(null);

    const handleDragOver = (e) => { e.preventDefault(); setDragging(true); };
    const handleDragLeave = () => setDragging(false);

    const handleDrop = (e) => {
        e.preventDefault();
        setDragging(false);
        const droppedFiles = Array.from(e.dataTransfer.files);
        setFiles(prev => [...prev, ...droppedFiles]);
    };

    const handleFileSelect = (e) => {
        const selectedFiles = Array.from(e.target.files);
        setFiles(prev => [...prev, ...selectedFiles]);
    };

    const removeFile = (index) => {
        setFiles(prev => prev.filter((_, i) => i !== index));
    };

    const handleUpload = async () => {
        if (files.length === 0 || uploading) return;
        setUploading(true);
        setProgress(10);

        const progressInterval = setInterval(() => {
            setProgress(prev => Math.min(prev + 5, 90));
        }, 500);

        try {
            await onUpload(files);
            setProgress(100);
            setTimeout(() => {
                setFiles([]);
                setProgress(0);
                setUploading(false);
            }, 500);
        } catch (err) {
            console.error('Upload error:', err);
            setUploading(false);
            setProgress(0);
        } finally {
            clearInterval(progressInterval);
        }
    };

    return (
        <div>
            <div
                className={`upload-zone ${dragging ? 'dragging' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
            >
                <Upload size={36} className="upload-icon" />
                <p>Drag & drop documents here or click to browse</p>
                <p className="file-types">Supports: *.*</p>
                <input
                    ref={inputRef}
                    type="file"
                    multiple
                    onChange={handleFileSelect}
                    style={{ display: 'none' }}
                    accept="*.*"
                />
            </div>

            {files.length > 0 && (
                <div style={{ maxWidth: '800px', margin: '8px auto', padding: '0 24px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
                        {files.map((file, i) => (
                            <div key={i} style={{
                                display: 'flex', alignItems: 'center', gap: '8px',
                                padding: '8px 12px', background: 'var(--bg-secondary)',
                                borderRadius: '8px', border: '1px solid var(--border)',
                                fontSize: '13px', color: 'var(--text-secondary)'
                            }}>
                                <FileText size={14} style={{ color: 'var(--accent)' }} />
                                <span style={{ flex: 1 }}>{file.name}</span>
                                <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                                    {(file.size / 1024).toFixed(1)} KB
                                </span>
                                {!uploading && (
                                    <button className="btn-icon" onClick={(e) => { e.stopPropagation(); removeFile(i); }}>
                                        <X size={14} />
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                    <button
                        className="btn btn-primary"
                        onClick={handleUpload}
                        disabled={uploading || disabled}
                        style={{ width: '100%' }}
                    >
                        {uploading ? 'Processing Documents...' : `Upload ${files.length} Document(s)`}
                    </button>
                </div>
            )}

            {uploading && (
                <div className="upload-progress">
                    <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${progress}%` }}></div>
                    </div>
                    <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px', textAlign: 'center' }}>
                        Converting & extracting content... {progress}%
                    </p>
                </div>
            )}
        </div>
    );
}
