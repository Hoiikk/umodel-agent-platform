import {
  listAiMatchScores,
  matchesKeyword,
  scoreResume,
} from '../src/services/aiParserService';
import { loadSeed } from '../src/data/store';
import { loadResumeSeed } from '../src/data/resumeStore';

/**
 * AI 简历匹配分单测（AGENTS.md §3.4：核心领域逻辑必测）。
 * 覆盖：关键词边界匹配、打分纯函数、批量编排与种子数据联动。
 */

describe('matchesKeyword - 关键词命中判定', () => {
  it('纯中文关键词走子串匹配', () => {
    expect(matchesKeyword('主导过性能优化项目', '性能优化')).toBe(true);
    expect(matchesKeyword('主导过性能调优项目', '性能优化')).toBe(false);
  });

  it('ASCII 关键词忽略大小写', () => {
    expect(matchesKeyword('精通 react 框架', 'React')).toBe(true);
    expect(matchesKeyword('精通 TYPESCRIPT', 'TypeScript')).toBe(true);
  });

  it('ASCII 关键词要求非字母数字边界，避免子串假阳性', () => {
    // Java 不得误命中 JavaScript
    expect(matchesKeyword('精通 JavaScript', 'Java')).toBe(false);
    expect(matchesKeyword('精通 Java 与 Spring', 'Java')).toBe(true);
  });

  it('含特殊字符的关键词（Node.js）可正常命中', () => {
    expect(matchesKeyword('熟悉 Node.js 与 Express', 'Node.js')).toBe(true);
  });

  it('关键词位于文本末尾也可命中', () => {
    expect(matchesKeyword('熟练掌握 CSS', 'CSS')).toBe(true);
  });
});

describe('scoreResume - 单份简历打分（纯函数）', () => {
  it('空简历得 0 分且无命中关键词', () => {
    expect(scoreResume('', '前端工程师')).toEqual({ score: 0, matchedKeywords: [] });
  });

  it('按职位词典累计命中权重', () => {
    const result = scoreResume('精通 React 与 TypeScript', '前端工程师');
    expect(result.score).toBe(20 + 15);
    expect(result.matchedKeywords).toEqual(['React', 'TypeScript']);
  });

  it('通用背景关键词对所有职位生效', () => {
    const result = scoreResume('硕士学历', '未知职位');
    expect(result.score).toBe(8);
    expect(result.matchedKeywords).toEqual(['硕士']);
  });

  it('未收录职位只使用通用关键词', () => {
    const result = scoreResume('精通 React，本科学历', '量子计算研究员');
    expect(result.score).toBe(4);
    expect(result.matchedKeywords).toEqual(['本科']);
  });

  it('分数上限截断到 100', () => {
    const everything =
      'React Vue TypeScript JavaScript Vite Webpack CSS HTML 性能优化 组件化 小程序 本科 硕士 博士';
    expect(scoreResume(everything, '前端工程师').score).toBe(100);
  });

  it('JavaScript 不会给后端工程师的 Java 加分', () => {
    const result = scoreResume('精通 JavaScript 与 CSS', '后端工程师');
    expect(result.score).toBe(0);
    expect(result.matchedKeywords).toEqual([]);
  });

  it('确定性：相同输入两次打分结果完全一致', () => {
    const text = '熟悉 MySQL 与 Redis，硕士';
    expect(scoreResume(text, '后端工程师')).toEqual(scoreResume(text, '后端工程师'));
  });
});

describe('listAiMatchScores - 批量编排（联动种子数据）', () => {
  beforeAll(() => {
    loadSeed();
    loadResumeSeed();
  });

  it('为 sidecar 中已录入简历的每个种子候选人各返回一条结果', () => {
    const results = listAiMatchScores();
    expect(results).toHaveLength(6);
    expect(new Set(results.map((r) => r.candidateId)).size).toBe(6);
  });

  it('结果只含 candidateId / score / matchedKeywords，不夹带主表字段', () => {
    for (const result of listAiMatchScores()) {
      expect(Object.keys(result).sort()).toEqual(['candidateId', 'matchedKeywords', 'score']);
      expect(result.score).toBeGreaterThanOrEqual(0);
      expect(result.score).toBeLessThanOrEqual(100);
      expect(Number.isInteger(result.score)).toBe(true);
    }
  });

  it('种子数据打分符合预期：强前端简历显著高于弱产品简历', () => {
    const results = listAiMatchScores();
    const strong = results.find((r) => r.candidateId === 'cand-001');
    const weak = results.find((r) => r.candidateId === 'cand-006');
    expect(strong?.score).toBe(87);
    expect(weak?.score).toBe(20);
    expect(strong!.score).toBeGreaterThan(weak!.score);
  });
});
