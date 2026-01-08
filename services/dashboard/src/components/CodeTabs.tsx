import { useState } from 'react';
import { ChevronDown, ChevronRight, FileCode } from 'lucide-react';
import './CodeTabs.css';

interface CodeTabsProps {
    files: Record<string, string>;
    selectedFile: string | null;
    onSelectFile: (path: string) => void;
}

export function CodeTabs({ files, selectedFile, onSelectFile }: CodeTabsProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const fileList = Object.keys(files);

    if (fileList.length === 0) {
        return (
            <div className="code-tabs empty">
                <span className="empty-text">No files generated yet</span>
            </div>
        );
    }

    const currentContent = selectedFile ? files[selectedFile] || files[selectedFile.slice(1)] || '' : '';
    const lineCount = currentContent.split('\n').length;

    return (
        <div className={`code-tabs ${isExpanded ? 'expanded' : 'collapsed'}`}>
            {/* Tab Bar */}
            <div className="tabs-header">
                <button
                    className="expand-toggle"
                    onClick={() => setIsExpanded(!isExpanded)}
                >
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
                <div className="tabs-scroll">
                    {fileList.map(path => {
                        const filename = path.split('/').pop() || path;
                        const isActive = selectedFile === path || selectedFile === '/' + path;
                        return (
                            <button
                                key={path}
                                className={`file-tab ${isActive ? 'active' : ''}`}
                                onClick={() => onSelectFile(path)}
                            >
                                <FileCode size={12} />
                                <span>{filename}</span>
                            </button>
                        );
                    })}
                </div>
                <span className="file-meta">{lineCount} lines</span>
            </div>

            {/* Collapsible Code View */}
            {isExpanded && selectedFile && (
                <div className="code-preview">
                    <pre className="code-content">
                        {currentContent.split('\n').slice(0, 50).map((line, i) => (
                            <div key={i} className="code-line">
                                <span className="line-num">{i + 1}</span>
                                <span className="line-text">{line || ' '}</span>
                            </div>
                        ))}
                        {lineCount > 50 && (
                            <div className="code-line truncated">
                                <span className="line-num">...</span>
                                <span className="line-text">+ {lineCount - 50} more lines</span>
                            </div>
                        )}
                    </pre>
                </div>
            )}
        </div>
    );
}
