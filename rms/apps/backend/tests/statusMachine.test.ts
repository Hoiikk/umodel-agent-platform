import {
  CANDIDATE_STATUSES,
  CandidateStatus,
  getAvailableTransitions,
  validateStatusTransition,
} from '@rms/shared';

/**
 * 状态机单测（AGENTS.md §3.4 必测项；spec.md §三.1 验收标准）。
 * 穷举 5×5 全部状态对：6 条合法边 + 19 条非法边。
 */

const LEGAL: ReadonlyArray<readonly [CandidateStatus, CandidateStatus]> = [
  ['APPLIED', 'SCREENING'],
  ['APPLIED', 'REJECTED'],
  ['SCREENING', 'INTERVIEWING'],
  ['SCREENING', 'REJECTED'],
  ['INTERVIEWING', 'HIRED'],
  ['INTERVIEWING', 'REJECTED'],
];

const ILLEGAL: ReadonlyArray<readonly [CandidateStatus, CandidateStatus]> = [
  // 原地不动
  ['APPLIED', 'APPLIED'],
  ['SCREENING', 'SCREENING'],
  ['INTERVIEWING', 'INTERVIEWING'],
  ['HIRED', 'HIRED'],
  ['REJECTED', 'REJECTED'],
  // 越级跳跃
  ['APPLIED', 'INTERVIEWING'],
  ['APPLIED', 'HIRED'],
  ['SCREENING', 'HIRED'],
  // 回退
  ['SCREENING', 'APPLIED'],
  ['INTERVIEWING', 'APPLIED'],
  ['INTERVIEWING', 'SCREENING'],
  // 终态 HIRED 无出边
  ['HIRED', 'APPLIED'],
  ['HIRED', 'SCREENING'],
  ['HIRED', 'INTERVIEWING'],
  ['HIRED', 'REJECTED'],
  // 终态 REJECTED 无出边
  ['REJECTED', 'APPLIED'],
  ['REJECTED', 'SCREENING'],
  ['REJECTED', 'INTERVIEWING'],
  ['REJECTED', 'HIRED'],
];

describe('validateStatusTransition - 合法路径', () => {
  it.each(LEGAL)('%s → %s 应允许', (from, to) => {
    expect(validateStatusTransition(from, to)).toBe(true);
  });
});

describe('validateStatusTransition - 非法路径', () => {
  it.each(ILLEGAL)('%s → %s 应拒绝', (from, to) => {
    expect(validateStatusTransition(from, to)).toBe(false);
  });
});

describe('用例完备性', () => {
  it('合法 + 非法用例恰好穷举全部 25 种状态对，无遗漏无重复', () => {
    const seen = new Set<string>();
    for (const [from, to] of [...LEGAL, ...ILLEGAL]) {
      const key = `${from}->${to}`;
      expect(seen.has(key)).toBe(false);
      seen.add(key);
    }
    expect(seen.size).toBe(CANDIDATE_STATUSES.length * CANDIDATE_STATUSES.length);
    expect(LEGAL).toHaveLength(6);
    expect(ILLEGAL).toHaveLength(19);
  });
});

describe('getAvailableTransitions', () => {
  it('非终态返回合法后继', () => {
    expect(getAvailableTransitions('APPLIED')).toEqual(['SCREENING', 'REJECTED']);
    expect(getAvailableTransitions('INTERVIEWING')).toEqual(['HIRED', 'REJECTED']);
  });

  it('终态返回空数组', () => {
    expect(getAvailableTransitions('HIRED')).toEqual([]);
    expect(getAvailableTransitions('REJECTED')).toEqual([]);
  });
});
