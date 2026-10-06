CREATE TABLE IF NOT EXISTS roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS auth_users (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    paternal_last_name VARCHAR(100) NOT NULL,
    maternal_last_name VARCHAR(100) NOT NULL DEFAULT '',
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    role_id INTEGER REFERENCES roles(role_id)
);

INSERT INTO roles (role_name) VALUES ('admin'), ('staff'), ('customer')
ON CONFLICT (role_name) DO NOTHING;

ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS role_id INTEGER REFERENCES roles(role_id);

UPDATE auth_users
SET role_id = (SELECT role_id FROM roles WHERE role_name = 'customer')
WHERE role_id IS NULL;

ALTER TABLE auth_users ALTER COLUMN role_id SET NOT NULL;
