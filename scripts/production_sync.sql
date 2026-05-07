-- SAFE DATABASE SYNC SCRIPT
-- This script adds missing tables and columns without touching existing data.

DO $$ 
BEGIN
    -- 1. Create Hierarchy Tables if missing
    CREATE TABLE IF NOT EXISTS provinces (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS districts (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, province_id INTEGER REFERENCES provinces(id), created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS regions (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, district_id INTEGER REFERENCES districts(id), created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS camps (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, region_id INTEGER REFERENCES regions(id), created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP);

    -- 2. Add Hierarchy Columns to Users if missing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='province_id') THEN
        ALTER TABLE users ADD COLUMN province_id INTEGER REFERENCES provinces(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='district_id') THEN
        ALTER TABLE users ADD COLUMN district_id INTEGER REFERENCES districts(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='region_id') THEN
        ALTER TABLE users ADD COLUMN region_id INTEGER REFERENCES regions(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='camp_id') THEN
        ALTER TABLE users ADD COLUMN camp_id INTEGER REFERENCES camps(id);
    END IF;

    -- 3. Add Managed Counts Fields to Users (for Management Roles)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='managed_agents_count') THEN
        ALTER TABLE users ADD COLUMN managed_agents_count INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='managed_camps_count') THEN
        ALTER TABLE users ADD COLUMN managed_camps_count INTEGER DEFAULT 0;
    END IF;

    -- 4. Chat Groups Updates
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_groups' AND column_name='group_type') THEN
        ALTER TABLE chat_groups ADD COLUMN group_type VARCHAR(50);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_groups' AND column_name='province_id') THEN
        ALTER TABLE chat_groups ADD COLUMN province_id INTEGER REFERENCES provinces(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_groups' AND column_name='district_id') THEN
        ALTER TABLE chat_groups ADD COLUMN district_id INTEGER REFERENCES districts(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_groups' AND column_name='region_id') THEN
        ALTER TABLE chat_groups ADD COLUMN region_id INTEGER REFERENCES regions(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_groups' AND column_name='camp_id') THEN
        ALTER TABLE chat_groups ADD COLUMN camp_id INTEGER REFERENCES camps(id);
    END IF;

    -- 5. Additional Tables (Core)
    CREATE TABLE IF NOT EXISTS reports (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        title VARCHAR(255),
        content TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    RAISE NOTICE 'Database Schema Synchronization Completed Safely.';
END $$;
