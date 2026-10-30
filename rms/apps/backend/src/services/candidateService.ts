import { Candidate, CandidateStatus, validateStatusTransition } from '@rms/shared';
import { CandidateRepository } from '../repositories/candidateRepository';

export class CandidateNotFoundError extends Error {
  readonly code = 'NOT_FOUND';

  constructor(readonly candidateId: string) {
    super(`候选人不存在: ${candidateId}`);
  }
}

export class InvalidTransitionError extends Error {
  readonly code = 'INVALID_TRANSITION';

  constructor(readonly from: CandidateStatus, readonly to: CandidateStatus) {
    super(`非法状态流转: ${from} → ${to}`);
  }
}

export function createCandidateService(store: CandidateRepository) {
  return {
    listCandidates: (): Promise<Candidate[]> => store.list(),
    transitionCandidateStatus: async (id: string, to: CandidateStatus): Promise<Candidate> => {
      const candidate = await store.getById(id);
      if (!candidate) throw new CandidateNotFoundError(id);
      if (!validateStatusTransition(candidate.status, to)) throw new InvalidTransitionError(candidate.status, to);
      const updated: Candidate = { ...candidate, status: to };
      await store.save(updated);
      return updated;
    },
  };
}
