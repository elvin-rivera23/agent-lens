import './App.css';
import { Header } from './components/Header';
import { EventStream } from './components/EventStream';
import { AgentTimeline } from './components/AgentTimeline';
import { useWebSocket } from './hooks/useWebSocket';

function App() {
  const { events, status, clearEvents } = useWebSocket();

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
              </div>
              <div className="code-placeholder scanlines">
                <pre className="code-content">
                  {`// Awaiting code generation...
// Agent output will appear here

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
