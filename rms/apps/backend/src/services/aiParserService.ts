import { AiMatchScore } from '@rms/shared';
import * as store from '../data/store';
import { getResumeText } from '../data/resumeStore';

/**
 * AI 简历匹配分服务（演示用确定性启发式打分，无外部 AI 依赖）。
 *
 * 设计约束：
 * - 打分逻辑只存在于本文件（任务红线），路由层只做参数解析与响应组装；
 * - 只读取候选人主表的 id / position 用于关联与选词典，绝不写主表；
 * - 简历原文来自 sidecar 存储 resumeStore，不进 candidates 主表；
 * - 打分是纯函数：相同输入必然相同输出，便于单测（AGENTS.md §3.4）。
 */

/** 关键词规则：weight 为命中加分，score 最终截断到 [0, 100]。 */
interface KeywordRule {
  keyword: string;
  weight: number;
}

/** 通用背景关键词（所有职位共用，权重小，只起微调作用）。 */
const GENERAL_KEYWORDS: readonly KeywordRule[] = [
  { keyword: '本科', weight: 4 },
  { keyword: '硕士', weight: 8 },
  { keyword: '博士', weight: 12 },
];

/** 职位技能词典：按候选人应聘职位选用；未收录的职位只用通用关键词。 */
const POSITION_KEYWORDS: Readonly<Record<string, readonly KeywordRule[]>> = {
  前端工程师: [
    { keyword: 'React', weight: 20 },
    { keyword: 'Vue', weight: 15 },
    { keyword: 'TypeScript', weight: 15 },
    { keyword: 'JavaScript', weight: 10 },
    { keyword: 'Vite', weight: 8 },
    { keyword: 'Webpack', weight: 8 },
    { keyword: 'CSS', weight: 6 },
    { keyword: 'HTML', weight: 6 },
    { keyword: '性能优化', weight: 8 },
    { keyword: '组件化', weight: 6 },
    { keyword: '小程序', weight: 6 },
  ],
  后端工程师: [
    { keyword: 'Java', weight: 15 },
    { keyword: 'Spring', weight: 12 },
    { keyword: 'Node.js', weight: 12 },
    { keyword: 'Python', weight: 12 },
    { keyword: 'MySQL', weight: 10 },
    { keyword: 'Redis', weight: 10 },
    { keyword: '微服务', weight: 10 },
    { keyword: 'Kubernetes', weight: 10 },
    { keyword: 'Express', weight: 8 },
    { keyword: 'Docker', weight: 8 },
    { keyword: 'MongoDB', weight: 8 },
    { keyword: '接口设计', weight: 6 },
  ],
  测试工程师: [
    { keyword: '自动化测试', weight: 18 },
    { keyword: '性能测试', weight: 12 },
    { keyword: 'Selenium', weight: 12 },
    { keyword: '接口测试', weight: 10 },
    { keyword: '测试用例', weight: 10 },
    { keyword: 'Pytest', weight: 10 },
    { keyword: 'JMeter', weight: 10 },
    { keyword: 'JUnit', weight: 8 },
    { keyword: 'Postman', weight: 6 },
    { keyword: '缺陷管理', weight: 6 },
  ],
  产品经理: [
    { keyword: '需求分析', weight: 15 },
    { keyword: '原型设计', weight: 12 },
    { keyword: '数据分析', weight: 12 },
    { keyword: 'Axure', weight: 10 },
    { keyword: 'PRD', weight: 10 },
    { keyword: '用户调研', weight: 10 },
    { keyword: '竞品分析', weight: 10 },
    { keyword: '项目管理', weight: 8 },
    { keyword: 'SQL', weight: 6 },
  ],
};

const SCORE_MAX = 100;

/**
 * 关键词命中判定：
 * - 纯中文关键词直接子串匹配；
 * - 含 ASCII 的关键词用「非字母数字」边界匹配（忽略大小写），
 *   避免 Java 误命中 JavaScript、C 误命中 CSS 这类子串假阳性。
 */
export function matchesKeyword(resumeText: string, keyword: string): boolean {
  if (/^[\u4e00-\u9fff]+$/.test(keyword)) {
    return resumeText.includes(keyword);
  }
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?<![A-Za-z0-9])${escaped}(?![A-Za-z0-9])`, 'i').test(resumeText);
}

/** 打分结果（不含 candidateId，由编排层补充）。 */
export interface ResumeScore {
  score: number;
  matchedKeywords: string[];
}

/**
 * 对单份简历按目标职位打分（纯函数）。
 * score = 命中关键词权重之和，截断到 [0, 100]；空简历得 0 分。
 */
export function scoreResume(resumeText: string, position: string): ResumeScore {
  if (!resumeText) {
    return { score: 0, matchedKeywords: [] };
  }
  const rules = [...GENERAL_KEYWORDS, ...(POSITION_KEYWORDS[position] ?? [])];
  const matched = rules.filter((rule) => matchesKeyword(resumeText, rule.keyword));
  const raw = matched.reduce((sum, rule) => sum + rule.weight, 0);
  return {
    score: Math.min(SCORE_MAX, raw),
    matchedKeywords: matched.map((rule) => rule.keyword),
  };
}

/**
 * 批量匹配分编排：遍历候选人主表（只读），关联 sidecar 简历原文逐个打分。
 * 未录入简历的候选人不出现在结果中（前端据此不渲染分数标签）。
 */
export function listAiMatchScores(): AiMatchScore[] {
  const results: AiMatchScore[] = [];
  for (const candidate of store.listCandidates()) {
    const resumeText = getResumeText(candidate.id);
    if (resumeText === undefined) continue;
    results.push({ candidateId: candidate.id, ...scoreResume(resumeText, candidate.position) });
  }
  return results;
}
