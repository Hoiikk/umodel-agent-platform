/**
 * 候选人数据契约（对应 AGENTS.md §3.2 软冻结字段清单）。
 *
 * 冻结规则：
 * - 禁止对下列字段改名、删除、修改类型或语义；
 * - 允许新增字段，但必须在同一任务内同步更新 AGENTS.md §3.2 清单。
 *
 * 状态机约束见 AGENTS.md §3.1：五态线性、无回退，
 * 流转校验函数（canTransition / assertTransition）唯一定义于本包。
 */

export const CANDIDATE_STATUSES = [
  'APPLIED',
  'SCREENING',
  'INTERVIEWING',
  'HIRED',
  'REJECTED',
] as const;

export type CandidateStatus = (typeof CANDIDATE_STATUSES)[number];

export interface Candidate {
  /** 唯一标识 */
  id: string;
  /** 姓名 */
  name: string;
  /** 电话 */
  phone: string;
  /** 邮箱 */
  email: string;
  /** 应聘职位 */
  position: string;
  /** 当前状态（五态之一） */
  status: CandidateStatus;
  /** 来源渠道 */
  source: string;
  /** 淘汰原因；种子里没写就是 null */
  rejectReason: string | null;
  /** 创建时间（ISO 8601） */
  createdAt: string;
}
