CREATE TABLE IF NOT EXISTS auth_users (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    paternal_last_name VARCHAR(100) NOT NULL,
    maternal_last_name VARCHAR(100) NOT NULL DEFAULT '',
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
