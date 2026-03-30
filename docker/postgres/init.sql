-- Init script executed only on first DB bootstrapping (empty volume).
-- Creates a separate DB for Metabase internal storage.

CREATE DATABASE metabase;
GRANT ALL PRIVILEGES ON DATABASE metabase TO pcparts;

