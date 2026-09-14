const db = require('../db');

const tables = {
  authors: { fields: ['name', 'biography'] },
  categories: { fields: ['name', 'description'] }
};
function all(table) { return db.prepare(`SELECT * FROM ${table} ORDER BY id DESC`).all(); }
function create(table, data) { const fields = tables[table].fields; return db.prepare(`INSERT INTO ${table} (${fields.join(',')}) VALUES (${fields.map(() => '?').join(',')})`).run(...fields.map(field => data[field] || '')); }
function update(table, id, data) { const fields = tables[table].fields; return db.prepare(`UPDATE ${table} SET ${fields.map(field => `${field}=?`).join(',')} WHERE id=?`).run(...fields.map(field => data[field] || ''), id); }
function remove(table, id) { return db.prepare(`DELETE FROM ${table} WHERE id = ?`).run(id); }
function books() { return db.prepare(`SELECT b.*, group_concat(DISTINCT a.name) authors, group_concat(DISTINCT c.name) categories, (SELECT filename FROM images i WHERE i.book_id=b.id ORDER BY i.id DESC LIMIT 1) image FROM books b LEFT JOIN book_authors ba ON ba.book_id=b.id LEFT JOIN authors a ON a.id=ba.author_id LEFT JOIN book_categories bc ON bc.book_id=b.id LEFT JOIN categories c ON c.id=bc.category_id GROUP BY b.id ORDER BY b.id DESC`).all(); }
function book(id) { return db.prepare('SELECT * FROM books WHERE id=?').get(id); }
function createBook(data) { const result = db.prepare('INSERT INTO books (title,isbn,description,price_cents,stock,published_year) VALUES (?,?,?,?,?,?)').run(data.title, data.isbn, data.description || '', Math.round(Number(data.price || 0) * 100), Number(data.stock || 0), data.published_year || null); syncRelations(result.lastInsertRowid, data.authors, data.categories); return result; }
function updateBook(id, data) { const result = db.prepare('UPDATE books SET title=?,isbn=?,description=?,price_cents=?,stock=?,published_year=? WHERE id=?').run(data.title, data.isbn, data.description || '', Math.round(Number(data.price || 0) * 100), Number(data.stock || 0), data.published_year || null, id); syncRelations(id, data.authors, data.categories); return result; }
function syncRelations(bookId, authors, categories) { const tx = db.transaction(() => { db.prepare('DELETE FROM book_authors WHERE book_id=?').run(bookId); db.prepare('DELETE FROM book_categories WHERE book_id=?').run(bookId); for (const id of [].concat(authors || [])) db.prepare('INSERT OR IGNORE INTO book_authors VALUES (?,?)').run(bookId, id); for (const id of [].concat(categories || [])) db.prepare('INSERT OR IGNORE INTO book_categories VALUES (?,?)').run(bookId, id); }); tx(); }
function addConcept(data) { return db.prepare('INSERT INTO concepts (book_id,term,definition) VALUES (?,?,?)').run(data.book_id, data.term, data.definition); }
function concepts() { return db.prepare('SELECT c.*, b.title FROM concepts c JOIN books b ON b.id=c.book_id ORDER BY c.id DESC').all(); }
function updateConcept(id, data) { return db.prepare('UPDATE concepts SET term=?,definition=? WHERE id=?').run(data.term, data.definition, id); }
function removeConcept(id) { return db.prepare('DELETE FROM concepts WHERE id=?').run(id); }
function addImage(data) { return db.prepare('INSERT INTO images (book_id,filename,original_name,mime_type) VALUES (?,?,?,?)').run(data.book_id, data.filename, data.originalname, data.mimetype); }
function images() { return db.prepare('SELECT i.*, b.title FROM images i JOIN books b ON b.id=i.book_id ORDER BY i.id DESC').all(); }
function removeImage(id) { return db.prepare('DELETE FROM images WHERE id=?').run(id); }
module.exports = { all, create, update, remove, books, book, createBook, updateBook, syncRelations, addConcept, concepts, updateConcept, removeConcept, addImage, images, removeImage };
