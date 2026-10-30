import { AiMatchScore, Candidate, CandidateStatus } from '@rms/shared';

export interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let body: ApiErrorBody = {};
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    // 响应体不是 JSON 时忽略
  }
  const code = body.error?.code ?? 'UNKNOWN';
  const message = body.error?.message ?? `请求失败（HTTP ${res.status}）`;
  return new ApiError(res.status, code, message);
}

export async function fetchCandidates(): Promise<Candidate[]> {
  const res = await fetch('/api/candidates');
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as Candidate[];
}

/** 批量拉取 AI 简历匹配分（独立接口，与候选人主表接口解耦）。 */
export async function fetchAiMatches(): Promise<AiMatchScore[]> {
  const res = await fetch('/api/candidates/ai-matches');
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as AiMatchScore[];
}

export async function patchCandidateStatus(
  id: string,
  status: CandidateStatus,
): Promise<Candidate> {
  const res = await fetch(`/api/candidates/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as Candidate;
}
