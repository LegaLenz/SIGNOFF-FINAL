import Badge from './common/Badge';

/**
 * props:
 *   clauses            — /analyze 응답의 clauses 배열
 *   onClauseClick      — High 조항 클릭 시 콜백 (clause) => void
 *   selectedClauseIndex — 현재 선택된 조항 인덱스 (선택 윤곽선 표시용, optional)
 */
export default function Editor({ clauses = [], onClauseClick, selectedClauseIndex = null }) {
  return (
    <div className="h-full overflow-y-auto bg-surface px-12 py-8">
      {clauses.map((clause) => {
        const isHigh = clause.risk_level === 'High';
        const isSelected = selectedClauseIndex === clause.clause_index;

        if (isHigh) {
          return (
            <div
              key={clause.clause_index}
              onClick={() => onClauseClick?.(clause)}
              className={[
                'mb-5 cursor-pointer rounded px-3 py-2 text-[14px] leading-loose text-text-primary',
                'bg-risk-high-bg hover:bg-risk-high-bg-hover transition-colors duration-100',
                isSelected ? 'outline outline-2 outline-primary outline-offset-1' : '',
              ].join(' ')}
            >
              <div className="mb-1 flex items-center gap-2">
                {clause.article_number && (
                  <span className="text-[11px] font-medium text-text-secondary">
                    {clause.article_number}
                  </span>
                )}
                <Badge variant="high">High</Badge>
              </div>
              {clause.text}
            </div>
          );
        }

        return (
          <p key={clause.clause_index} className="mb-5 text-[14px] leading-loose text-text-primary">
            {clause.article_number && (
              <span className="mr-1 text-[11px] font-medium text-text-secondary">
                {clause.article_number}
              </span>
            )}
            {clause.text}
          </p>
        );
      })}
    </div>
  );
}
