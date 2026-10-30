/**
 * AI 简历匹配分数据契约。
 *
 * 与 Candidate 主表完全解耦（AGENTS.md §3.2 不适用本类型）：
 * - 不改动 Candidate 任何字段；
 * - 不进入 GET /api/candidates 返回体；
 * - 仅通过独立接口 GET /api/candidates/ai-matches 下发。
 */

/** 单个候选人的 AI 简历匹配结果。 */
export interface AiMatchScore {
  /** 候选人 id（关联 Candidate.id，不冗余候选人字段） */
  candidateId: string;
  /** 匹配分，0–100 整数；分数由后端 aiParserService 确定性算出 */
  score: number;
  /** 命中的技能 / 背景关键词（字典原文形式），供前端 tooltip 展示 */
  matchedKeywords: string[];
}
