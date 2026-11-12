CREATE TABLE candidates (
  id VARCHAR(64) NOT NULL, name VARCHAR(128) NOT NULL, phone VARCHAR(32) NOT NULL,
  email VARCHAR(320) NOT NULL, position VARCHAR(128) NOT NULL,
  status ENUM('APPLIED','SCREENING','INTERVIEWING','HIRED','REJECTED') NOT NULL,
  source VARCHAR(128) NOT NULL, reject_reason VARCHAR(255) NULL, opening_id VARCHAR(64) NOT NULL,
  created_at DATETIME(3) NOT NULL, PRIMARY KEY (id),
  KEY idx_candidates_position_status_created_at (position, status, created_at),
  KEY idx_candidates_source_created_at (source, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE openings (
  id VARCHAR(64) NOT NULL, title VARCHAR(128) NOT NULL, headcount INT NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
