// TEMP: useSessionReset 훅 확인용 임시 렌더링. 본격 화면 전환 연결 전까지만 사용.
import { useSessionReset } from './hooks/useSessionReset'

function App() {
  const confirmAndReset = useSessionReset({
    isActive: true, // TEMP: 8번(전체 조립)에서 실제 화면 상태로 대체
    onReset: () => console.log('reset! (홈 화면으로 전환됐다고 가정)'),
  })

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-4 bg-background">
      <p className="text-sm text-text-secondary">
        새로고침/탭 닫기를 시도하면 브라우저 기본 이탈 경고가 떠야 합니다.
      </p>
      <button
        type="button"
        onClick={confirmAndReset}
        className="rounded-md border border-border bg-surface px-4 py-2 text-sm text-text-primary hover:bg-primary-subtle"
      >
        뒤로가기 (confirmAndReset 테스트)
      </button>
    </div>
  )
}

export default App
