import { Candidate } from '@rms/shared';
import * as store from '../data/store';
import { CandidateRepository } from './candidateRepository';

export class MemoryCandidateRepository implements CandidateRepository {
  async list(): Promise<Candidate[]> { return store.listCandidates(); }
  async getById(id: string): Promise<Candidate | undefined> { return store.getCandidate(id); }
  async save(candidate: Candidate): Promise<void> { store.saveCandidate(candidate); }
}
