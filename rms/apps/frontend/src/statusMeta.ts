import { CandidateStatus } from '@rms/shared';

/** 看板列顺序与中文文案（纯展示元数据，不含流转规则）。 */
export const STATUS_ORDER: readonly CandidateStatus[] = [
  'APPLIED',
  'SCREENING',
  'INTERVIEWING',
  'HIRED',
  'REJECTED',
];

export const STATUS_LABELS: Record<CandidateStatus, string> = {
  APPLIED: '已投递',
  SCREENING: '筛选中',
  INTERVIEWING: '面试中',
  HIRED: '已录用',
  REJECTED: '已淘汰',
};

/** 列头颜色对应参考图：首列深灰、过程列暗金、录用深绿、淘汰中性灰。 */
export const STATUS_TITLE_CLASS: Record<CandidateStatus, string> = {
  APPLIED: 'col-title-slate',
  SCREENING: 'col-title-amber',
  INTERVIEWING: 'col-title-amber',
  HIRED: 'col-title-emerald',
  REJECTED: 'col-title-muted',
};
