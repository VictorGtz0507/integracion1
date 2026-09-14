const bcrypt = require('bcryptjs');
const db = require('../db');

function seedAdmin() {
  if (!db.prepare('SELECT id FROM users LIMIT 1').get()) {
    const hash = bcrypt.hashSync(process.env.ADMIN_PASSWORD || 'admin1234', 10);
    db.prepare('INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)').run('Administrador', process.env.ADMIN_EMAIL || 'admin@libreria.local', hash, 'admin');
  }
}
function findByEmail(email) { return db.prepare('SELECT * FROM users WHERE lower(email) = lower(?)').get(email); }
function list() { return db.prepare('SELECT id, name, email, role, created_at FROM users ORDER BY name').all(); }
function create(data) { return db.prepare('INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)').run(data.name, data.email, bcrypt.hashSync(data.password, 10), data.role || 'staff'); }
function update(id, data) { const fields = data.password ? ['name = ?', 'email = ?', 'password_hash = ?', 'role = ?'] : ['name = ?', 'email = ?', 'role = ?']; const values = data.password ? [data.name, data.email, bcrypt.hashSync(data.password, 10), data.role] : [data.name, data.email, data.role]; return db.prepare(`UPDATE users SET ${fields.join(', ')} WHERE id = ?`).run(...values, id); }
function remove(id) { return db.prepare('DELETE FROM users WHERE id = ?').run(id); }
module.exports = { seedAdmin, findByEmail, list, create, update, remove, verify: bcrypt.compareSync };
