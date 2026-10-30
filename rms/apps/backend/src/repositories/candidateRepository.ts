import { Candidate } from '@rms/shared';

export interface CandidateRepository {
  list(): Promise<Candidate[]>;
  getById(id: string): Promise<Candidate | undefined>;
  save(candidate: Candidate): Promise<void>;
}
