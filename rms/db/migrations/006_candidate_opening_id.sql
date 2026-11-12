ALTER TABLE candidates
  ADD COLUMN opening_id VARCHAR(64) NULL AFTER reject_reason;

UPDATE candidates SET opening_id = 'job-001' WHERE id IN ('cand-001', 'cand-004', 'cand-007');
UPDATE candidates SET opening_id = 'job-002' WHERE id IN ('cand-002', 'cand-005', 'cand-008');
UPDATE candidates SET opening_id = 'job-003' WHERE id = 'cand-003';
UPDATE candidates SET opening_id = 'job-004' WHERE id = 'cand-006';

ALTER TABLE candidates
  MODIFY opening_id VARCHAR(64) NOT NULL,
  ADD CONSTRAINT fk_candidates_opening
  FOREIGN KEY (opening_id) REFERENCES openings (id);
