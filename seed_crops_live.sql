-- ============================================
-- SEED SCRIPT FOR LIVE SERVER
-- Run this on your production PostgreSQL DB
-- ============================================

-- Step 1: Insert Crop Families (with colors for Domination Map)
INSERT INTO crop_families (id, family_name, color) VALUES
(1, 'Grains',      '#F59E0B'),
(2, 'Tubers',      '#9b59b6'),
(3, 'Legumes',     '#3498db'),
(4, 'Fruits',      '#f39c12'),
(5, 'Vegetables',  '#e74c3c')
ON CONFLICT (id) DO UPDATE SET
    family_name = EXCLUDED.family_name,
    color = EXCLUDED.color;

-- Step 2: Insert National Crops (linked to their families)
INSERT INTO national_crops (id, crop_name, family_id) VALUES
(1, 'Grains Standard',      1),
(2, 'Tubers Standard',      2),
(3, 'Legumes Standard',     3),
(4, 'Fruits Standard',      4),
(5, 'Vegetables Standard',  5)
ON CONFLICT (id) DO UPDATE SET
    crop_name = EXCLUDED.crop_name,
    family_id = EXCLUDED.family_id;

-- Step 3: Reset sequences so future inserts get correct IDs
SELECT setval('crop_families_id_seq', (SELECT MAX(id) FROM crop_families));
SELECT setval('national_crops_id_seq', (SELECT MAX(id) FROM national_crops));
