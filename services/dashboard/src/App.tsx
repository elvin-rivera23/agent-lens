import { useState, useEffect } from 'react';
import './App.css';
import { Header } from './components/Header';
import { EventStream } from './components/EventStream';
import { TaskInput } from './components/TaskInput';
import { CodeTabs } from './components/CodeTabs';
import { AgentMetricsCard, defaultAgents } from './components/AgentMetricsCard';
import { PreviewPanel } from './components/PreviewPanel';
import { useWebSocket } from './hooks/useWebSocket';

const ORCHESTRATOR_URL = import.meta.env.VITE_ORCHESTRATOR_URL || 'http://localhost:8001';

function App() {
  const { events, status, clearEvents } = useWebSocket();
  const [isLoading, setIsLoading] = useState(false);
  const [lastTask, setLastTask] = useState<string | null>(null);
  const [agentMetrics, setAgentMetrics] = useState(defaultAgents);

  // Multi-file workspace state
  const [workspaceFiles, setWorkspaceFiles] = useState<Record<string, string>>({});
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  // Live streaming code (shows tokens as they arrive)
  const [streamingCode, setStreamingCode] = useState<string>('');
  const [streamingFile, setStreamingFile] = useState<string | null>(null);

  // Token tracking
  const [totalTokens, setTotalTokens] = useState(0);

  // Execution output state
  const [executionOutput, setExecutionOutput] = useState('');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewType, setPreviewType] = useState<'iframe' | 'terminal' | 'none'>('terminal');

  // Architect plan (plain English summary)
  const [architectPlan, setArchitectPlan] = useState<string>('');

  // Update agent metrics and workspace files based on WebSocket events
  useEffect(() => {
    if (events.length === 0) return;

    const latestEvent = events[0];

    // Handle workspace reset
    if (latestEvent.type === 'workspace_reset') {
      setWorkspaceFiles({});
      setSelectedFile(null);
      setStreamingCode('');
      setStreamingFile(null);
    }

    // Token handling moved to agent status section below

    // Handle file creation (complete file)
    if (latestEvent.type === 'file_created') {
      const file_path = String(latestEvent.data?.file_path || '');
      const content = String(latestEvent.data?.content || '');
      if (file_path && content) {
        setWorkspaceFiles(prev => ({ ...prev, [file_path]: content }));
        setSelectedFile(current => current || file_path);
        setStreamingCode('');
        setStreamingFile(null);

        // Auto-enable iframe preview for HTML files
        if (file_path.endsWith('.html') || file_path.endsWith('index.html')) {
          const previewFile = file_path.startsWith('/') ? file_path.slice(1) : file_path;
          setPreviewUrl(`${ORCHESTRATOR_URL}/preview/${previewFile}`);
          setPreviewType('iframe');
        }
      }
    }

    // Handle legacy code_written (single file mode)
    if (latestEvent.type === 'code_written') {
      const file_path = String(latestEvent.data?.file_path || '');
      const code = String(latestEvent.data?.code || '');
      if (file_path && code) {
        setWorkspaceFiles(prev => ({ ...prev, [file_path]: code }));
        setSelectedFile(file_path);
        setStreamingCode('');
        setStreamingFile(null);
      }
    }

    // Update agent status
    if (latestEvent.type === 'agent_start') {
      setAgentMetrics(prev => prev.map(agent =>
        agent.id === latestEvent.agent
          ? { ...agent, status: 'working' as const, tokens: 0 }
          : agent
      ));
    }

    // Real-time token counting during streaming
    if (latestEvent.type === 'token') {
      const token = String(latestEvent.data?.token || '');
      const file_path = String(latestEvent.data?.file_path || '/output.py');
      if (token) {
        setStreamingCode(prev => prev + token);
        setStreamingFile(file_path);
        setSelectedFile(file_path);
        // Increment token count on active agent
        setAgentMetrics(prev => prev.map(agent =>
          agent.status === 'working'
            ? { ...agent, tokens: (agent.tokens || 0) + 1 }
            : agent
        ));
        setTotalTokens(prev => prev + 1);
      }
    }

    if (latestEvent.type === 'agent_end') {
      const latency: number = Number(latestEvent.data?.latency) || Math.random() * 3 + 0.5;
      setAgentMetrics(prev => prev.map(agent =>
        agent.id === latestEvent.agent
          ? {
            ...agent,
            status: 'complete' as const,
            latency,
            // Keep existing token count or set to 0 for non-LLM agents
            tokens: agent.tokens ?? 0
          }
          : agent
      ));
    }

    if (latestEvent.type === 'error') {
      setAgentMetrics(prev => prev.map(agent =>
        agent.id === latestEvent.agent
          ? { ...agent, status: 'error' as const }
          : agent
      ));
    }

    // Handle plan_created event from Architect
    if (latestEvent.type === 'plan_created' && latestEvent.data?.summary) {
      setArchitectPlan(String(latestEvent.data.summary));
    }

    // Handle execution events
    if (latestEvent.type === 'execution') {
      const output = String(latestEvent.data?.output || '');
      setExecutionOutput(prev => prev + (prev ? '\n' : '') + output);
    }

    // Handle execution step events
    if (latestEvent.type === 'execution_step') {
      const output = String(latestEvent.data?.output || '');
      const label = String(latestEvent.data?.label || '');
      if (output) {
        setExecutionOutput(prev => prev + `\n=== ${label} ===\n${output}`);
      }
    }
  }, [events]);

  const handleTaskSubmit = async (task: string) => {
    setIsLoading(true);
    setLastTask(task);
    clearEvents();
    setAgentMetrics(defaultAgents);

    // Reset workspace for new task
    setWorkspaceFiles({});
    setSelectedFile(null);
    setTotalTokens(0);
    setExecutionOutput('');
    setPreviewUrl(null);

    try {
      const response = await fetch(`${ORCHESTRATOR_URL}/orchestrate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      });

      const data = await response.json();

      // Load files from response
      if (data.files && Object.keys(data.files).length > 0) {
        setWorkspaceFiles(data.files);
        setSelectedFile(Object.keys(data.files)[0]);

        // Check for web files and set preview URL
        const hasHtmlFile = Object.keys(data.files).some(f => f.endsWith('.html'));
        if (hasHtmlFile || data.preview_url) {
          const url = data.preview_url || `${ORCHESTRATOR_URL}/preview/index.html`;
          setPreviewUrl(url);
          setPreviewType('iframe');
        }
      } else if (data.code && data.file_path) {
        // Fallback to single file mode
        setWorkspaceFiles({ [data.file_path]: data.code });
        setSelectedFile(data.file_path);
      }
    } catch (error) {
      // Show error in placeholder file
      const errorContent = `# Error\n${error instanceof Error ? error.message : 'Unknown error'}`;
      setWorkspaceFiles({ '/error.md': errorContent });
      setSelectedFile('/error.md');
    } finally {
      setIsLoading(false);
    }
  };

  // Get current file content for editor
  // Show streaming content if actively streaming, otherwise show completed file

  // Normalize path lookup - try with and without leading slash
  const getFileContent = (path: string | null): string | null => {
    if (!path) return null;
    // Try exact match
    if (workspaceFiles[path]) return workspaceFiles[path];
    // Try without leading slash
    if (path.startsWith('/') && workspaceFiles[path.slice(1)]) return workspaceFiles[path.slice(1)];
    // Try with leading slash
    if (!path.startsWith('/') && workspaceFiles['/' + path]) return workspaceFiles['/' + path];
    return null;
  };

  return (
    <div className="app">
      <Header status={status} />

      <main className="dashboard">
        {/* Left: Task Input + Architect Plan */}
        <section className="panel-left">
          <TaskInput onSubmit={handleTaskSubmit} isLoading={isLoading} />

          {/* Architect's Plan Summary */}
          <div className="plan-panel">
            <div className="panel-header">
              <span className="panel-icon">◇</span>
              PROJECT PLAN
            </div>
            <div className="plan-content">
              {architectPlan ? (
                <p className="plan-text">{architectPlan}</p>
              ) : lastTask ? (
                <p className="plan-placeholder">Generating plan for: {lastTask.slice(0, 50)}...</p>
              ) : (
                <p className="plan-placeholder">Enter a task to see the AI's plan</p>
              )}

              {/* Workspace Files List */}
              {Object.keys(workspaceFiles).length > 0 && (
                <div className="workspace-files">
                  <div className="workspace-files-header">📁 FILES</div>
                  <ul className="workspace-files-list">
                    {Object.keys(workspaceFiles).map(filepath => (
                      <li
                        key={filepath}
                        className={`workspace-file ${selectedFile === filepath ? 'active' : ''}`}
                        onClick={() => setSelectedFile(filepath)}
                      >
                        <span className="file-icon">
                          {filepath.endsWith('.html') ? '🌐' :
                            filepath.endsWith('.css') ? '🎨' :
                              filepath.endsWith('.js') ? '⚡' :
                                filepath.endsWith('.py') ? '🐍' : '📄'}
                        </span>
                        {filepath.split('/').pop()}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Compact file tabs */}
            <CodeTabs
              files={workspaceFiles}
              selectedFile={selectedFile}
              onSelectFile={setSelectedFile}
            />
          </div>
        </section>

        {/* Center: Split - Live Code (top) + Preview (bottom) */}
        <section className="panel-center">
          {/* Live Coding Panel */}
          <div className="live-code-panel">
            <div className="panel-header">
              <span className="panel-icon">◈</span>
              LIVE CODE
              {streamingFile && <span className="streaming-file">{streamingFile.split('/').pop()}</span>}
            </div>
            <div className="live-code-content">
              {streamingCode ? (
                <pre className="streaming-code">{streamingCode}</pre>
              ) : selectedFile ? (
                <pre className="streaming-code">{getFileContent(selectedFile) || 'Select a file...'}</pre>
              ) : (
                <div className="code-placeholder">Code will stream here as it's generated...</div>
              )}
            </div>
          </div>

          {/* Preview/Execution Panel */}
          <div className="preview-panel-wrapper">
            <PreviewPanel
              previewUrl={previewUrl}
              executionOutput={executionOutput || (isLoading ? 'Processing task...' : '')}
              previewType={previewType}
            />
          </div>
        </section>

        {/* Right: Agent Telemetry + Events */}
        <section className="panel-right">
          <div className="agents-panel">
            <div className="panel-header">
              <span className="panel-icon">⬡</span>
              AGENTS
              <span className="token-counter">{totalTokens.toLocaleString()} tkn</span>
            </div>
            <div className="agents-stack">
              {agentMetrics.map(agent => (
                <AgentMetricsCard
                  key={agent.id}
                  agent={agent}
                  isActive={status.activeAgent === agent.id}
                />
              ))}
            </div>
          </div>

          <EventStream events={events} onClear={clearEvents} />

          <div className="gpu-panel">
            <div className="panel-header">
              <span className="panel-icon">◈</span>
              SYSTEM
            </div>
            <div className="gpu-grid">
              <div className="gpu-metric">
                <div className="metric-bar" style={{ '--fill': '42%' } as React.CSSProperties} />
                <span className="metric-label">GPU</span>
                <span className="metric-val cyan">42%</span>
              </div>
              <div className="gpu-metric">
                <div className="metric-bar" style={{ '--fill': '68%' } as React.CSSProperties} />
                <span className="metric-label">VRAM</span>
                <span className="metric-val magenta">68%</span>
              </div>
              <div className="gpu-metric">
                <div className="metric-bar" style={{ '--fill': '24%' } as React.CSSProperties} />
                <span className="metric-label">TPS</span>
                <span className="metric-val green">24.5</span>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
