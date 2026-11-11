ALTER TABLE candidates
  ADD COLUMN reject_reason VARCHAR(255) NULL AFTER source;

UPDATE candidates SET reject_reason = '技能不匹配' WHERE id = 'cand-006';
