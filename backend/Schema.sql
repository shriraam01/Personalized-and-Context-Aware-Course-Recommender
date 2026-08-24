-- ============================================================
--  Course Recommender — MySQL Setup
--  Run once:  mysql -u root -p < schema.sql
--
--  NOTE: This ONLY creates the tables. Your existing Udemy
--  courses data is loaded separately via CSV import.
-- ============================================================

CREATE DATABASE IF NOT EXISTS course_recommender
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE course_recommender;

-- ── users ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id                   INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
  username             VARCHAR(80)     NOT NULL UNIQUE,
  password             VARCHAR(64)     NOT NULL,           -- SHA-256 hex

  -- personalised parameters
  interest             VARCHAR(100)    DEFAULT NULL,
  career_goal          VARCHAR(100)    DEFAULT NULL,
  experience_years     VARCHAR(10)     DEFAULT NULL,
  known_tools          VARCHAR(200)    DEFAULT NULL,
  preferred_language   VARCHAR(50)     DEFAULT NULL,

  -- context-aware parameters
  budget               VARCHAR(50)     DEFAULT NULL,
  time_commitment      VARCHAR(50)     DEFAULT NULL,
  learning_style       VARCHAR(50)     DEFAULT NULL,
  certification_needed VARCHAR(10)     DEFAULT NULL,
  motivation           VARCHAR(100)    DEFAULT NULL,
  career_stage         VARCHAR(50)     DEFAULT NULL,

  created_at           TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
  updated_at           TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
                       ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ── courses ────────────────────────────────────────────────────────────
-- This table must match your Udemy CSV column names exactly.
-- Typical Udemy dataset columns:
--   course_id, course_title, url, is_paid, price, num_subscribers,
--   num_reviews, num_lectures, level, content_duration,
--   published_timestamp, subject
--
-- If your CSV has different column names, adjust this table definition
-- and the LOAD DATA command below to match.

CREATE TABLE IF NOT EXISTS courses (
  course_id            INT UNSIGNED    NOT NULL,
  course_title         VARCHAR(500)    NOT NULL,
  url                  VARCHAR(1000)   DEFAULT '',
  is_paid              TINYINT(1)      DEFAULT 0,
  price                DECIMAL(10, 2)  DEFAULT 0.00,
  num_subscribers      INT UNSIGNED    DEFAULT 0,
  num_reviews          INT UNSIGNED    DEFAULT 0,
  num_lectures         INT UNSIGNED    DEFAULT 0,
  level                VARCHAR(50)     DEFAULT 'All Levels',
  content_duration     FLOAT           DEFAULT 0,
  published_timestamp  DATETIME        DEFAULT NULL,
  subject              VARCHAR(200)    DEFAULT '',

  PRIMARY KEY (course_id),
  INDEX idx_subject (subject(64)),
  INDEX idx_level   (level)
) ENGINE=InnoDB;

-- ============================================================
--  LOAD YOUR UDEMY CSV
--  Replace the file path with the actual path on your machine.
-- ============================================================

LOAD DATA LOCAL INFILE 'C:/path/to/udemy_courses.csv'
INTO TABLE courses
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(course_id, course_title, url, is_paid, price, num_subscribers,
 num_reviews, num_lectures, level, content_duration,
 published_timestamp, subject);

-- Verify the load:
-- SELECT COUNT(*) FROM courses;
-- SELECT course_title, subject, level FROM courses LIMIT 5;