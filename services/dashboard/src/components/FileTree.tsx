import { useState } from 'react';
import { ChevronRight, ChevronDown, FileCode, Folder, FolderOpen } from 'lucide-react';
import './FileTree.css';

interface FileNode {
    name: string;
    path: string;
    type: 'file' | 'folder';
    children?: FileNode[];
}

interface FileTreeProps {
    files: Record<string, string>;
    selectedFile: string | null;
    onSelectFile: (path: string) => void;
}

// Internal tree-building type with object children
interface InternalNode {
    name: string;
    path: string;
    type: 'file' | 'folder';
    children?: Record<string, InternalNode>;
}

// Convert flat file map to tree structure
function buildTree(files: Record<string, string>): FileNode[] {
    const root: Record<string, InternalNode> = {};

    Object.keys(files).forEach(filePath => {
        const parts = filePath.replace(/^\//, '').split('/');
        let current: Record<string, InternalNode> = root;

        parts.forEach((part, idx) => {
            if (!current[part]) {
                const isFile = idx === parts.length - 1;
                current[part] = {
                    name: part,
                    path: '/' + parts.slice(0, idx + 1).join('/'),
                    type: isFile ? 'file' : 'folder',
                    children: isFile ? undefined : {},
                };
            }
            if (!current[part].children && current[part].type === 'folder') {
                current[part].children = {};
            }
            current = current[part].children || {};
        });
    });

    // Convert object to array and sort (folders first, then files)
    function toArray(obj: Record<string, InternalNode>): FileNode[] {
        return Object.values(obj)
            .map(node => ({
                name: node.name,
                path: node.path,
                type: node.type,
                children: node.children ? toArray(node.children) : undefined,
            }))
            .sort((a, b) => {
                if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
                return a.name.localeCompare(b.name);
            });
    }

    return toArray(root);
}

function TreeNode({
    node,
    selectedFile,
    onSelectFile,
    depth = 0
}: {
    node: FileNode;
    selectedFile: string | null;
    onSelectFile: (path: string) => void;
    depth?: number;
}) {
    const [isOpen, setIsOpen] = useState(true);
    const isSelected = selectedFile === node.path;

    if (node.type === 'folder') {
        return (
            <div className="tree-node">
                <div
                    className="tree-item folder"
                    style={{ paddingLeft: `${depth * 12 + 8}px` }}
                    onClick={() => setIsOpen(!isOpen)}
                >
                    <span className="tree-chevron">
                        {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                    </span>
                    <span className="tree-icon">
                        {isOpen ? <FolderOpen size={14} /> : <Folder size={14} />}
                    </span>
                    <span className="tree-name">{node.name}</span>
                </div>
                {isOpen && node.children && (
                    <div className="tree-children">
                        {node.children.map(child => (
                            <TreeNode
                                key={child.path}
                                node={child}
                                selectedFile={selectedFile}
                                onSelectFile={onSelectFile}
                                depth={depth + 1}
                            />
                        ))}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div
            className={`tree-item file ${isSelected ? 'selected' : ''}`}
            style={{ paddingLeft: `${depth * 12 + 8}px` }}
            onClick={() => onSelectFile(node.path)}
        >
            <span className="tree-chevron" />
            <span className="tree-icon file-icon">
                <FileCode size={14} />
            </span>
            <span className="tree-name">{node.name}</span>
        </div>
    );
}

export function FileTree({ files, selectedFile, onSelectFile }: FileTreeProps) {
    const tree = buildTree(files);
    const fileCount = Object.keys(files).length;

    if (fileCount === 0) {
        return (
            <div className="file-tree empty">
                <div className="empty-state">
                    <span className="empty-icon">📁</span>
                    <span className="empty-text">No files yet</span>
                </div>
            </div>
        );
    }

    return (
        <div className="file-tree">
            <div className="file-tree-header">
                <span className="header-icon">◈</span>
                WORKSPACE
                <span className="file-count">{fileCount}</span>
            </div>
            <div className="file-tree-content">
                {tree.map(node => (
                    <TreeNode
                        key={node.path}
                        node={node}
                        selectedFile={selectedFile}
                        onSelectFile={onSelectFile}
                    />
                ))}
            </div>
        </div>
    );
}
