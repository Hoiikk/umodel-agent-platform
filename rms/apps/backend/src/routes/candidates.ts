import { Router } from 'express';
import { isCandidateStatus } from '@rms/shared';
import {
  CandidateNotFoundError,
  InvalidTransitionError,
  createCandidateService,
} from '../services/candidateService';
import { listAiMatchScores } from '../services/aiParserService';
import { createCandidateRepository } from '../repositories';

/**
 * 路由层（controller）：只做参数解析、调用 service、组装响应。
 * 禁止在本层写业务规则（AGENTS.md §3.5）。
 */
export const candidatesRouter = Router();
const candidates = createCandidateService(createCandidateRepository());

candidatesRouter.get('/', async (_req, res, next) => {
  try { res.json(await candidates.listCandidates()); } catch (error) { next(error); }
});

/**
 * AI 简历匹配分（批量）：独立接口，与 GET / 主表返回完全解耦。
 * 返回 AiMatchScore[]，仅含 candidateId / score / matchedKeywords。
 */
candidatesRouter.get('/ai-matches', (_req, res) => {
  res.json(listAiMatchScores());
});

candidatesRouter.patch('/:id/status', async (req, res, next) => {
  const { status } = req.body ?? {};
  if (!isCandidateStatus(status)) {
    return res.status(400).json({
      error: { code: 'VALIDATION_ERROR', message: '请求体必须包含合法的 status 字段' },
    });
  }
  try {
    const updated = await candidates.transitionCandidateStatus(req.params.id, status);
    return res.json(updated);
  } catch (err) {
    if (err instanceof CandidateNotFoundError) {
      return res.status(404).json({ error: { code: err.code, message: err.message } });
    }
    if (err instanceof InvalidTransitionError) {
      return res.status(409).json({ error: { code: err.code, message: err.message } });
    }
    next(err);
  }
});
