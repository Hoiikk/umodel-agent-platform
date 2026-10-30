import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AiMatchScore, Candidate, CandidateStatus, getAvailableTransitions } from '@rms/shared';
import { ApiError, fetchAiMatches, fetchCandidates, patchCandidateStatus } from './api';
import { STATUS_LABELS, STATUS_ORDER, STATUS_TITLE_CLASS } from './statusMeta';

function formatCreatedAt(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** 分数档位样式：≥80 高、≥60 中、其余低。 */
function aiScoreClass(score: number): string {
  if (score >= 80) return 'ai-score ai-score-high';
  if (score >= 60) return 'ai-score ai-score-mid';
  return 'ai-score ai-score-low';
}

export default function App() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [aiMatches, setAiMatches] = useState<AiMatchScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const pendingRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 匹配分加载失败不阻塞看板，仅退化为不显示分数标签
      const [list, matches] = await Promise.all([
        fetchCandidates(),
        fetchAiMatches().catch(() => [] as AiMatchScore[]),
      ]);
      setCandidates(list);
      setAiMatches(matches);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载候选人列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const aiMatchById = useMemo(
    () => new Map(aiMatches.map((m) => [m.candidateId, m])),
    [aiMatches],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const handleTransition = async (id: string, to: CandidateStatus) => {
    if (pendingRef.current) return;
    pendingRef.current = id;
    setPendingId(id);
    setError(null);
    try {
      await patchCandidateStatus(id, to);
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(`非法状态流转：${err.message}`);
      } else {
        setError(err instanceof Error ? err.message : '状态更新失败');
      }
    } finally {
      pendingRef.current = null;
      setPendingId(null);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <div className="brand-sub">招聘管理系统</div>
          <h1>招聘流程看板</h1>
        </div>
        <button className="refresh-btn" onClick={() => void load()}>
          刷新
        </button>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button aria-label="关闭" onClick={() => setError(null)}>
            ×
          </button>
        </div>
      )}

      {loading ? (
        <div className="loading">加载中…</div>
      ) : (
        <div className="board">
          {STATUS_ORDER.map((status) => {
            const columnCandidates = candidates.filter((c) => c.status === status);
            return (
              <section key={status} className="column">
                <div className="column-header">
                  <span className={STATUS_TITLE_CLASS[status]}>{STATUS_LABELS[status]}</span>
                  <span className="column-count">{columnCandidates.length}</span>
                </div>
                {columnCandidates.length === 0 && (
                  <div className="column-empty">暂无候选人</div>
                )}
                {columnCandidates.map((candidate) => {
                  const actions = getAvailableTransitions(candidate.status);
                  const advance = actions.filter((to) => to !== 'REJECTED');
                  const canReject = actions.includes('REJECTED');
                  const aiMatch = aiMatchById.get(candidate.id);
                  return (
                    <article key={candidate.id} className="card">
                      <div className="card-head">
                        <div className="card-name">{candidate.name}</div>
                        <span className="card-position-pill">{candidate.position}</span>
                      </div>
                      {aiMatch && (
                        <div
                          className={aiScoreClass(aiMatch.score)}
                          title={
                            aiMatch.matchedKeywords.length > 0
                              ? `命中关键词：${aiMatch.matchedKeywords.join('、')}`
                              : '未命中关键词'
                          }
                        >
                          AI 匹配 {aiMatch.score}
                        </div>
                      )}
                      <div className="card-meta">
                        <div className="meta-row">
                          <span className="meta-label">电话</span>
                          <span className="meta-value">{candidate.phone}</span>
                        </div>
                        <div className="meta-row">
                          <span className="meta-label">邮箱</span>
                          <span className="meta-value meta-ellipsis" title={candidate.email}>
                            {candidate.email}
                          </span>
                        </div>
                        <div className="meta-row">
                          <span className="meta-label">创建</span>
                          <span className="meta-value">{formatCreatedAt(candidate.createdAt)}</span>
                        </div>
                      </div>
                      {actions.length === 0 ? (
                        <div className="card-done">流程已完成</div>
                      ) : (
                        <div className="card-actions">
                          {canReject && (
                            <button
                              className="action-btn action-secondary"
                              disabled={pendingId === candidate.id}
                              onClick={() => void handleTransition(candidate.id, 'REJECTED')}
                            >
                              淘汰
                            </button>
                          )}
                          {advance.map((to) => (
                            <button
                              key={to}
                              className="action-btn action-primary"
                              disabled={pendingId === candidate.id}
                              onClick={() => void handleTransition(candidate.id, to)}
                            >
                              推进到{STATUS_LABELS[to]}
                            </button>
                          ))}
                        </div>
                      )}
                    </article>
                  );
                })}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
