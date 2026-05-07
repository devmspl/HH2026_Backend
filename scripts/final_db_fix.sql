-- FINAL DATABASE SCHEMA FIX FOR CHAT AND HIERARCHY
-- Run this on the production server to resolve UndefinedColumn errors

-- 1. Fix chat_messages table
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_messages' AND column_name='media_url') THEN
        ALTER TABLE chat_messages ADD COLUMN media_url VARCHAR(500);
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_messages' AND column_name='text' AND is_nullable='NO') THEN
        ALTER TABLE chat_messages ALTER COLUMN text DROP NOT NULL;
    END IF;
END $$;

-- 2. Fix chat_groups table
DO $$ 
BEGIN 
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
END $$;

-- 3. Fix users table (Ensuring role is varchar)
DO $$ 
BEGIN 
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='role' AND data_type='USER-DEFINED') THEN
        ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50) USING role::text;
    END IF;
END $$;

-- 4. Set default group_type for existing groups if null
UPDATE chat_groups SET group_type = 'DIRECT' WHERE group_type IS NULL AND (name NOT LIKE '%Team%' AND name NOT LIKE '%Group%');
UPDATE chat_groups SET group_type = 'TEAM' WHERE group_type IS NULL AND name LIKE '%Team%';
