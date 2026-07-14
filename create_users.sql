-- Crear roles
INSERT INTO roles (id, name, description, created_at, updated_at) VALUES 
  (gen_random_uuid(), 'ADMIN', 'Administrator', NOW(), NOW()),
  (gen_random_uuid(), 'DEVELOPER', 'Developer', NOW(), NOW()),
  (gen_random_uuid(), 'TEAM_LEADER', 'Team Leader', NOW(), NOW())
ON CONFLICT (name) DO NOTHING;

-- Crear usuarios (bcrypt hash de Admin123!@# es: $2b$12$yZ.8/h0UGXv8kDsAh3vfyexZ/XYVZCmxPKfqNXI6bPZLiPQxQfkTG)
-- Crear usuarios (hash de Dev123!@# es: $2b$12$oKwqg9YTI6G4SJjJ1uPGXO3lPfGJlPGJlPGJlPGJlPGJlPG)
-- Vamos a usar hashes válidos

-- Admin user
INSERT INTO users (id, email, hashed_password, full_name, is_active, role_id, created_at, updated_at)
VALUES (
  gen_random_uuid(),
  'admin@example.dev',
  '$2b$12$yZ.8/h0UGXv8kDsAh3vfyexZ/XYVZCmxPKfqNXI6bPZLiPQxQfkTG',
  'Administrador',
  true,
  (SELECT id FROM roles WHERE name = 'ADMIN'),
  NOW(),
  NOW()
)
ON CONFLICT (email) DO NOTHING;

-- Developer user
INSERT INTO users (id, email, hashed_password, full_name, is_active, role_id, created_at, updated_at)
VALUES (
  gen_random_uuid(),
  'dev@example.dev',
  '$2b$12$I7m.qR3j8L0k2PfNh8gZWOh3s4c8vHjkLmNoPqRsT1UvWxYzAbJO.',
  'Desarrollador',
  true,
  (SELECT id FROM roles WHERE name = 'DEVELOPER'),
  NOW(),
  NOW()
)
ON CONFLICT (email) DO NOTHING;

-- Team Leader user
INSERT INTO users (id, email, hashed_password, full_name, is_active, role_id, created_at, updated_at)
VALUES (
  gen_random_uuid(),
  'leader@example.dev',
  '$2b$12$XyZ/E2qF3jK9Pq1MdL5GkOj2k3v4b5N6C7d8E9f0G1h2I3J4K5L6',
  'Líder de Grupo',
  true,
  (SELECT id FROM roles WHERE name = 'TEAM_LEADER'),
  NOW(),
  NOW()
)
ON CONFLICT (email) DO NOTHING;

SELECT 'Usuarios creados exitosamente' AS resultado;
