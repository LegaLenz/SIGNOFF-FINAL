import { useState, useEffect, useRef, useCallback } from 'react';
import Button from './common/Button';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * props:
 *   selectedClause   — Editor에서 클릭된 High 조항 객체 (null이면 빈 상태)
 *                      부모가 같은 조항을 재클릭할 때도 새 참조를 내려줘야 flash+scroll이 동작함
 *   documentCategory — /analyze 응답의 document_category (대안 문구 요청에 포함)
 */
export default function ChatPanel({ selectedClause = null, documentCategory = '' }) {
  // { id, userTag, reason, alternative, sourceUrl, isLoadingAlt }
  const [messages, setMessages] = useState([]);
  const [flashId, setFlashId] = useState(null);

  const bottomRef = useRef(null);
  const msgRefs = useRef({});    // clause_index → reason bubble DOM element
  const prevCountRef = useRef(0);

  const fetchAlternative = useCallback(async (clause) => {
    try {
      const res = await fetch(`${API_BASE}/clauses/alternative`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clause_index: clause.clause_index,
          article_number: clause.article_number ?? null,
          text: clause.text,
          risk_level: clause.risk_level,
          reason: clause.reason,
          document_category: documentCategory,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMessages(prev =>
        prev.map(m =>
          m.id === clause.clause_index
            ? { ...m, alternative: data.alternative, sourceUrl: data.source_url, isLoadingAlt: false }
            : m
        )
      );
    } catch {
      setMessages(prev =>
        prev.map(m =>
          m.id === clause.clause_index
            ? { ...m, alternative: '대안 문구를 가져오지 못했습니다.', sourceUrl: null, isLoadingAlt: false }
            : m
        )
      );
    }
  }, [documentCategory]);

  useEffect(() => {
    if (!selectedClause) return;

    const existing = messages.find(m => m.id === selectedClause.clause_index);
    if (existing) {
      msgRefs.current[existing.id]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      setFlashId(existing.id);
      setTimeout(() => setFlashId(null), 1000);
      return;
    }

    setMessages(prev => [
      ...prev,
      {
        id: selectedClause.clause_index,
        userTag: selectedClause.article_number ?? `조항 ${selectedClause.clause_index + 1}`,
        reason: selectedClause.reason,
        alternative: null,
        sourceUrl: null,
        isLoadingAlt: true,
      },
    ]);
    fetchAlternative(selectedClause);
  }, [selectedClause]); // eslint-disable-line react-hooks/exhaustive-deps

  // 새 메시지 추가 시에만 하단 스크롤
  useEffect(() => {
    if (messages.length > prevCountRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
      prevCountRef.current = messages.length;
    }
  }, [messages.length]);

  return (
    <div className="flex h-full flex-col bg-background">

      {/* 헤더 */}
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-[18px] py-[11px]">
        <span className="h-2 w-2 rounded-full bg-primary" />
        <span className="text-[13px] font-medium text-text-primary">AI 에이전트</span>
      </div>

      {/* 메시지 목록 */}
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="m-auto max-w-[200px] text-center text-[12.5px] leading-relaxed text-text-disabled">
            하이라이트된 조항을 클릭하거나<br />직접 질문을 입력해보세요
          </p>
        )}

        {messages.map(msg => (
          <div key={msg.id} className="flex flex-col gap-2">

            {/* 사용자 말풍선 */}
            <div
              className="chat-fadein self-end max-w-[90%] text-[13px] leading-relaxed text-text-primary"
              style={{ background: 'var(--color-primary-subtle)', borderRadius: '10px 10px 2px 10px', padding: '9px 13px' }}
            >
              <span className="mb-[3px] block text-[10.5px] font-medium text-text-secondary">
                {msg.userTag}
              </span>
              이 조항이 왜 위험한가요?
            </div>

            {/* 분류 근거 말풍선 (캐시된 값 — 즉시 표시) */}
            <div
              ref={el => { msgRefs.current[msg.id] = el; }}
              className={`chat-fadein self-start max-w-[90%] border border-[0.5px] border-border bg-surface text-[13px] leading-relaxed text-text-primary ${flashId === msg.id ? 'chat-flash' : ''}`}
              style={{ borderRadius: '10px 10px 10px 2px', padding: '9px 13px' }}
            >
              {msg.reason}
            </div>

            {/* 대안 문구 말풍선 — 로딩 중 / 근거 없음 / 대안 문구 */}
            {msg.isLoadingAlt ? (
              <div
                className="chat-fadein self-start flex gap-1"
                style={{ padding: '9px 13px' }}
              >
                <span className="chat-dot" />
                <span className="chat-dot" style={{ animationDelay: '0.15s' }} />
                <span className="chat-dot" style={{ animationDelay: '0.3s' }} />
              </div>
            ) : msg.alternative !== null ? (
              <div
                className="chat-fadein self-start max-w-[90%] border border-[0.5px] border-border bg-surface text-[13px] leading-relaxed text-text-primary"
                style={{ borderRadius: '10px 10px 10px 2px', padding: '9px 13px' }}
              >
                {msg.alternative}
                {msg.sourceUrl && (
                  <a
                    href={msg.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 block text-[11.5px] text-text-secondary underline hover:text-text-primary"
                  >
                    공정거래위원회 표준계약서 보기 →
                  </a>
                )}
              </div>
            ) : (
              <div
                className="chat-fadein self-start max-w-[90%] border border-[0.5px] border-border bg-surface text-[13px] leading-relaxed text-text-secondary"
                style={{ borderRadius: '10px 10px 10px 2px', padding: '9px 13px' }}
              >
                <p className="mb-1">⚠️ 관련 표준계약서를 찾지 못했습니다.</p>
                <p className="text-[12px]">
                  <span className="font-medium text-text-primary">[위험 판단 근거]</span>{' '}
                  {msg.reason}
                </p>
              </div>
            )}
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      {/* 입력 영역 — UI만 구현, 실제 호출은 TODO */}
      <div className="flex shrink-0 items-center gap-2 border-t border-border px-[14px] py-3">
        <input
          type="text"
          placeholder="조항에 대해 질문하기"
          // TODO (8번 이후): 자유 텍스트 → POST /chat 연결 (백엔드 미구현)
          className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 font-pretendard text-[13px] text-text-primary outline-none placeholder:text-text-disabled focus:border-border-strong"
        />
        <Button
          variant="send"
          // TODO (8번 이후): 자유 텍스트 전송 핸들러 연결
          aria-label="전송"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-[15px] w-[15px]"
          >
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </Button>
      </div>

    </div>
  );
}
