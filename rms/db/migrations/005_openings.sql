CREATE TABLE openings (
  id VARCHAR(64) NOT NULL, title VARCHAR(128) NOT NULL, headcount INT NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO openings (id, title, headcount) VALUES
('job-001', '前端工程师', 2),
('job-002', '后端工程师', 1),
('job-003', '测试工程师', 1),
('job-004', '产品经理', 1);
