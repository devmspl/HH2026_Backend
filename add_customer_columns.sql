-- Add new columns to customers table
-- Run this script in your PostgreSQL database

ALTER TABLE customers ADD COLUMN IF NOT EXISTS first_name VARCHAR(100);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS last_name VARCHAR(100);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS age INTEGER;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS gender VARCHAR(20);

-- Verify columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'customers' 
AND column_name IN ('first_name', 'last_name', 'age', 'gender');
