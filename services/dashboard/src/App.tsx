import { useState, useEffect } from 'react';
import './App.css';
import { Header } from './components/Header';
import { EventStream } from './components/EventStream';
import { AgentTimeline } from './components/AgentTimeline';
import { TaskInput } from './components/TaskInput';
import { useWebSocket } from './hooks/useWebSocket';

const ORCHESTRATOR_URL = import.meta.env.VITE_ORCHESTRATOR_URL || 'http://localhost:8001';

function App() {
  const { events, status, clearEvents } = useWebSocket();
  const [isLoading, setIsLoading] = useState(false);
  const [codeOutput, setCodeOutput] = useState<string | null>(null);
  const [lastTask, setLastTask] = useState<string | null>(null);

  // Update code output based on WebSocket events in real-time
  useEffect(() => {
    if (events.length === 0) return;

    const latestEvent = events[0]; // events are prepended, so [0] is most recent

    // Show code when written
    if (latestEvent.type === 'code_written' && typeof latestEvent.data?.code === 'string') {
      setCodeOutput(latestEvent.data.code);
    }

    // Show execution result
    if (latestEvent.type === 'execution') {
      const { success, output, exit_code } = latestEvent.data || {};
      const prefix = success ? '// ✓ Execution successful' : `// ✗ Execution failed (exit ${exit_code})`;
      setCodeOutput(prev => prev ? `${prev}\n\n${prefix}\n${output}` : `${prefix}\n${output}`);
    }

    // Show errors
    if (latestEvent.type === 'error') {
      setCodeOutput(prev => prev ? `${prev}\n\n// Error: ${latestEvent.data?.error}` : `// Error: ${latestEvent.data?.error}`);
    }
  }, [events]);

  const handleTaskSubmit = async (task: string) => {
    setIsLoading(true);
    setLastTask(task);
    setCodeOutput(null);
    clearEvents();

    try {
      const response = await fetch(`${ORCHESTRATOR_URL}/orchestrate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ task }),
      });

      const data = await response.json();

      if (data.success) {
        setCodeOutput(data.code);
      } else {
        setCodeOutput(`// Error: ${data.execution_output || 'Task failed'}`);
      }
    } catch (error) {
      setCodeOutput(`// Connection error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <Header status={status} />

      <main className="main-content">
        <aside className="sidebar">
          <AgentTimeline activeAgent={status.activeAgent} />
        </aside>

        <section className="content-area">
          <div className="content-grid">
            <div className="event-panel">
              <TaskInput onSubmit={handleTaskSubmit} isLoading={isLoading} />
              <EventStream events={events} onClear={clearEvents} />
            </div>

            <div className="metrics-panel card">
              <div className="card-header">
                <span>📊 SYSTEM METRICS</span>
              </div>
              <div className="metrics-placeholder">
                <p className="glitch-text">GPU/CPU TELEMETRY</p>
                <p className="text-muted">Connect to metrics service</p>
              </div>
            </div>

            <div className="code-panel card">
              <div className="card-header">
                <span>💻 CODE OUTPUT</span>
                {lastTask && <span className="task-label">Task: {lastTask.slice(0, 40)}...</span>}
              </div>
              <div className="code-placeholder scanlines">
                <pre className="code-content">
                  {codeOutput || `// Awaiting code generation...
// Submit a task above to see agent output

async function orchestrate(task: string) {
  const plan = await architect.analyze(task);
  const code = await coder.generate(plan);
  const review = await reviewer.check(code);
  return executor.run(code);
}`}
                </pre>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="footer-text flicker">
          <span className="accent">◈</span> AGENTLENS v0.1.0 <span className="accent">◈</span> GLASS-BOX OBSERVABILITY <span className="accent">◈</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
