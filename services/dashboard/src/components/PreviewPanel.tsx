import { useState } from 'react';
import { Terminal, Globe, RefreshCw, ExternalLink, Play } from 'lucide-react';
import './PreviewPanel.css';

interface PreviewPanelProps {
    previewUrl: string | null;
    executionOutput: string;
    previewType: 'iframe' | 'terminal' | 'none';
    onRefresh?: () => void;
}

export function PreviewPanel({
    previewUrl,
    executionOutput,
    previewType,
    onRefresh
}: PreviewPanelProps) {
    const [activeTab, setActiveTab] = useState<'preview' | 'output'>('output');

    // Auto-switch to preview tab when iframe URL is available
    const effectiveTab = previewUrl && previewType === 'iframe' ? 'preview' : activeTab;

    return (
        <div className="preview-panel">
            <div className="preview-header">
                <div className="preview-tabs">
                    <button
                        className={`preview-tab ${effectiveTab === 'output' ? 'active' : ''}`}
                        onClick={() => setActiveTab('output')}
                    >
                        <Terminal size={12} />
                        OUTPUT
                    </button>
                    {previewUrl && previewType === 'iframe' && (
                        <button
                            className={`preview-tab ${effectiveTab === 'preview' ? 'active' : ''}`}
                            onClick={() => setActiveTab('preview')}
                        >
                            <Globe size={12} />
                            PREVIEW
                        </button>
                    )}
                </div>
                <div className="preview-actions">
                    {previewUrl && (
                        <>
                            <button
                                className="preview-action"
                                onClick={onRefresh}
                                title="Refresh"
                            >
                                <RefreshCw size={12} />
                            </button>
                            <a
                                href={previewUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="preview-action"
                                title="Open in new tab"
                            >
                                <ExternalLink size={12} />
                            </a>
                        </>
                    )}
                </div>
            </div>

            <div className="preview-content">
                {effectiveTab === 'preview' && previewUrl ? (
                    <iframe
                        src={previewUrl}
                        className="preview-iframe"
                        title="App Preview"
                        sandbox="allow-scripts allow-same-origin allow-forms"
                    />
                ) : (
                    <div className="terminal-output">
                        {executionOutput ? (
                            <pre className="terminal-text">{executionOutput}</pre>
                        ) : (
                            <div className="terminal-empty">
                                <Play size={24} />
                                <span>Execution output will appear here</span>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
