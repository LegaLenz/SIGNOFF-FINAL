import { useState } from 'react';
import Upload from './components/Upload';
import Processing from './components/Processing';
import Editor from './components/Editor';
import ChatPanel from './components/ChatPanel';
import ResizablePanels from './components/ResizablePanels';
import Button from './components/common/Button';
import Logo from './components/common/Logo';
import { useSessionReset } from './hooks/useSessionReset';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export default function App() {
  const [screen, setScreen] = useState('home'); // 'home' | 'loading' | 'result'
  const [file, setFile] = useState(null);
  const [documentCategory, setDocumentCategory] = useState('');
  const [clauses, setClauses] = useState([]);
  // 항상 새 참조를 내려야 ChatPanel의 재클릭 flash+scroll이 동작함
  const [selectedClause, setSelectedClause] = useState(null);
  const [selectedClauseIndex, setSelectedClauseIndex] = useState(null);

  const resetState = () => {
    setFile(null);
    setDocumentCategory('');
    setClauses([]);
    setSelectedClause(null);
    setSelectedClauseIndex(null);
    setScreen('home');
  };

  const confirmAndReset = useSessionReset({
    isActive: screen === 'result',
    onReset: resetState,
  });

  const handleFileSelected = async (selectedFile) => {
    setFile(selectedFile);
    setScreen('loading');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const res = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `HTTP ${res.status}`);
      }

      const data = await res.json();
      setDocumentCategory(data.document_category);
      setClauses(data.clauses);
      setScreen('result');
    } catch (err) {
      alert(`분석에 실패했습니다.\n${err.message}`);
      resetState();
    }
  };

  const handleClauseClick = (clause) => {
    // 같은 조항 재클릭 시에도 새 참조 → ChatPanel useEffect 재발동 → flash+scroll
    setSelectedClause({ ...clause });
    setSelectedClauseIndex(clause.clause_index);
  };

  // ── home ──────────────────────────────────────────────────────────────────
  if (screen === 'home') {
    return <Upload onFileSelected={handleFileSelected} />;
  }

  // ── loading ───────────────────────────────────────────────────────────────
  // estimated_seconds는 /analyze 응답에 포함되므로 로딩 중에는 알 수 없음 → null 전달
  if (screen === 'loading') {
    return (
      <Processing
        fileName={file?.name}
        fileType={file?.type}
        estimatedSeconds={null}
      />
    );
  }

  // ── result ────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen flex-col bg-background">

      {/* 상단 바 */}
      <div className="flex h-[52px] shrink-0 items-center gap-3 border-b border-border bg-surface px-5">
        <Button variant="icon" aria-label="홈으로" onClick={confirmAndReset}>
          <svg
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
        </Button>
        <Logo variant="topbar" showLabel={false} />
        {documentCategory && (
          <span className="text-[12px] text-text-secondary">{documentCategory}</span>
        )}
      </div>

      {/* 패널 영역 */}
      <div className="min-h-0 flex-1">
        <ResizablePanels>
          <Editor
            clauses={clauses}
            onClauseClick={handleClauseClick}
            selectedClauseIndex={selectedClauseIndex}
          />
          <ChatPanel
            selectedClause={selectedClause}
            documentCategory={documentCategory}
            clauses={clauses}
          />
        </ResizablePanels>
      </div>

    </div>
  );
}
