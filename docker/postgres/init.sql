-- Exécuté une seule fois, à la création du volume.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS raw;      -- semaine 2 : tables brutes
CREATE SCHEMA IF NOT EXISTS rejects;  -- semaine 2 : zone de rejets
