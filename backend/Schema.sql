-- ============================================================
-- Personalized & Context-Aware Course Recommender
-- MySQL Database Setup
-- ============================================================

CREATE DATABASE IF NOT EXISTS course_recommender
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE course_recommender;

-- ============================================================
-- DROP OLD TABLES
-- ============================================================

DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS users;

-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    username VARCHAR(80) NOT NULL UNIQUE,
    password VARCHAR(64) NOT NULL,

    -- PERSONALIZATION
    interests TEXT,
    career_goal VARCHAR(150),

    education_level VARCHAR(100),
    degree_field VARCHAR(150),
    current_year VARCHAR(50),
    academic_performance DECIMAL(5,2),

    existing_skills TEXT,
    experience_level VARCHAR(50),
    experience_years DECIMAL(4,1),

    desired_skills TEXT,
    target_job_role VARCHAR(150),
    target_industry VARCHAR(150),

    preferred_difficulty VARCHAR(50),
    preferred_language VARCHAR(50),

    learning_objective VARCHAR(150),
    content_preference VARCHAR(100),
    teaching_style VARCHAR(100),

    -- CONTEXT AWARE
    budget VARCHAR(100),
    available_hours_per_week DECIMAL(5,2),
    completion_time VARCHAR(100),
    learning_mode VARCHAR(100),
    certification_needed BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================
-- COURSES
-- ============================================================

CREATE TABLE courses (
    course_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    course_name VARCHAR(500) NOT NULL,
    university VARCHAR(500),
    difficulty_level VARCHAR(50),
    course_rating DECIMAL(3,2),

    course_url VARCHAR(1000),

    course_description TEXT,
    skills TEXT,

    course_format VARCHAR(100),
    is_free_to_audit BOOLEAN,

    budget_tier VARCHAR(100),
    certification_offered BOOLEAN,

    estimated_duration_hours DECIMAL(6,2),
    time_commitment_tier VARCHAR(100),

    learning_mode VARCHAR(150),

    primary_domain VARCHAR(150),
    secondary_domain VARCHAR(150),

    INDEX idx_difficulty (difficulty_level),
    INDEX idx_rating (course_rating),
    INDEX idx_primary_domain (primary_domain),
    INDEX idx_secondary_domain (secondary_domain),
    INDEX idx_budget (budget_tier),
    INDEX idx_format (course_format)
) ENGINE=InnoDB;

-- ============================================================
-- LOAD COURSES CSV
-- ============================================================

LOAD DATA LOCAL INFILE 'courses.csv'
INTO TABLE courses
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(
    course_name,
    university,
    difficulty_level,
    course_rating,
    course_url,
    course_description,
    skills,
    course_format,
    is_free_to_audit,
    budget_tier,
    certification_offered,
    estimated_duration_hours,
    time_commitment_tier,
    learning_mode,
    primary_domain,
    secondary_domain
);