// DEMO: 홈 → 처리중 → 분석 화면 전환이 실제로 동작하는지 확인하기 위한 데모 흐름.
// 8번(전체 조립) 완성본이 아니며, Editor.jsx/ChatPanel.jsx가 실제로 붙기 전까지의
// 임시 배선입니다.
import { useState } from 'react';
import Upload from './components/Upload';
import Processing from './components/Processing';
import ResizablePanels from './components/ResizablePanels';
import Button from './components/common/Button';
import { useSessionReset } from './hooks/useSessionReset';

const SCREENS = {
  HOME: 'home',
  PROCESSING: 'processing',
  ANALYSIS: 'analysis',
};

function App() {
  const [screen, setScreen] = useState(SCREENS.HOME);
  const [file, setFile] = useState(null);

  const confirmAndReset = useSessionReset({
    isActive: screen === SCREENS.ANALYSIS,
    onReset: () => {
      setFile(null);
      setScreen(SCREENS.HOME);
    },
  });

  const handleFileSelected = (selectedFile) => {
    setFile(selectedFile);
    setScreen(SCREENS.PROCESSING);
  };

  if (screen === SCREENS.HOME) {
    return <Upload onFileSelected={handleFileSelected} />;
  }

  if (screen === SCREENS.PROCESSING) {
    return (
      <Processing
        fileName={file?.name}
        fileType={file?.type}
        onComplete={() => setScreen(SCREENS.ANALYSIS)}
      />
    );
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      <div className="flex h-[52px] flex-shrink-0 items-center border-b-[0.5px] border-border bg-surface px-5">
        <Button variant="icon" aria-label="홈으로" onClick={confirmAndReset}>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
        </Button>
      </div>

      <div className="min-h-0 flex-1">
        <ResizablePanels>
          <div className="p-6 text-sm text-text-secondary">
            {/* TODO: 소현 - 실제 Editor.jsx로 교체 */}
            문서 패널 (Editor.jsx 자리 — 소현 담당)
          </div>
          <div className="p-6 text-sm text-text-secondary">
            {/* TODO: 소현 - 실제 ChatPanel.jsx로 교체 */}
            채팅 패널 (ChatPanel.jsx 자리 — 소현 담당)
          </div>
        </ResizablePanels>
      </div>
    </div>
  );
}

export default App;
