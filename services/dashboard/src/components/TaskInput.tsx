import { useState } from 'react';
import './TaskInput.css';

interface TaskInputProps {
    onSubmit: (task: string) => void;
    isLoading: boolean;
}

export function TaskInput({ onSubmit, isLoading }: TaskInputProps) {
    const [task, setTask] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (task.trim() && !isLoading) {
            onSubmit(task.trim());
        }
    };

    const exampleTasks = [
        'Write a fibonacci function',
        'Create a REST API endpoint',
        'Build a simple calculator',
    ];

    return (
        <div className="task-input-container card">
            <div className="card-header">
                <span>🚀 TASK INPUT</span>
            </div>
            <form onSubmit={handleSubmit} className="task-form">
                <textarea
                    className="task-textarea"
                    value={task}
                    onChange={(e) => setTask(e.target.value)}
                    placeholder="Describe your coding task..."
                    disabled={isLoading}
                    rows={3}
                />
                <div className="task-actions">
                    <div className="quick-tasks">
                        {exampleTasks.map((example, i) => (
                            <button
                                key={i}
                                type="button"
                                className="quick-task-btn"
                                onClick={() => setTask(example)}
                                disabled={isLoading}
                            >
                                {example}
                            </button>
                        ))}
                    </div>
                    <button
                        type="submit"
                        className={`submit-btn ${isLoading ? 'loading' : ''}`}
                        disabled={!task.trim() || isLoading}
                    >
                        {isLoading ? (
                            <>
                                <span className="spinner"></span>
                                PROCESSING...
                            </>
                        ) : (
                            'EXECUTE TASK'
                        )}
                    </button>
                </div>
            </form>
        </div>
    );
}
