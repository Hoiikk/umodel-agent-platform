import { CANDIDATE_STATUSES, CandidateStatus } from './candidate';

/**
 * 候选人状态机唯一定义（AGENTS.md §3.1）：五态线性、无回退。
 * - 任意非终态可流转到 REJECTED；
 * - 只有 INTERVIEWING 可流转到 HIRED；
 * - HIRED / REJECTED 为终态，无出边。
 *
 * 修改本文件必须遵循 .cursor/skills/modify-candidate-state-machine 的 SOP，
 * 并同步更新单测与 AGENTS.md §3.1 流转表。
 */
export const STATUS_TRANSITIONS: Readonly<Record<CandidateStatus, readonly CandidateStatus[]>> = {
  APPLIED: ['SCREENING', 'REJECTED'],
  SCREENING: ['INTERVIEWING', 'REJECTED'],
  INTERVIEWING: ['HIRED', 'REJECTED'],
  HIRED: [],
  REJECTED: [],
};

/** 运行时类型守卫：判断任意值是否为合法状态枚举成员。 */
export function isCandidateStatus(value: unknown): value is CandidateStatus {
  return typeof value === 'string' && (CANDIDATE_STATUSES as readonly string[]).includes(value);
}

/**
 * 统一状态流转校验函数：合法返回 true，非法返回 false。
 * 后端任何修改 candidate.status 的代码路径必须调用本函数（AGENTS.md §3.1）。
 */
export function validateStatusTransition(from: CandidateStatus, to: CandidateStatus): boolean {
  return STATUS_TRANSITIONS[from].includes(to);
}

/** 查询某状态的全部合法后继（供「可用动作」能力使用）。 */
export function getAvailableTransitions(from: CandidateStatus): readonly CandidateStatus[] {
  return STATUS_TRANSITIONS[from];
}
