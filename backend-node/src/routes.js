const path = require('node:path');
const fs = require('node:fs');
const express = require('express');
const multer = require('multer');
const user = require('./models/userModel');
const catalog = require('./models/catalogModel');

const upload = multer({ dest: path.join(__dirname, '..', 'uploads'), limits: { fileSize: 5 * 1024 * 1024 }, fileFilter: (req, file, cb) => cb(null, /^image\//.test(file.mimetype)) });
const requireAuth = (req, res, next) => req.session.user ? next() : res.redirect('/login');
const flash = (req, message) => { req.session.notice = message; };

function registerRoutes(app) {
  app.get('/', (req, res) => res.render('home', { title: 'Librería', books: catalog.books() }));
  app.get('/login', (req, res) => res.render('login', { title: 'Acceso', error: null }));
  app.post('/login', (req, res) => { const found = user.findByEmail(req.body.email || ''); if (!found || !user.verify(req.body.password || '', found.password_hash)) return res.status(401).render('login', { title: 'Acceso', error: 'Correo o contraseña incorrectos.' }); req.session.user = { id: found.id, name: found.name, role: found.role }; res.redirect('/admin'); });
  app.post('/logout', (req, res) => req.session.destroy(() => res.redirect('/')));
  app.get('/admin', requireAuth, (req, res) => res.render('dashboard', { title: 'Panel de gestión', books: catalog.books(), authors: catalog.all('authors'), categories: catalog.all('categories'), concepts: catalog.concepts(), images: catalog.images(), users: user.list() }));
  app.post('/authors', requireAuth, (req, res) => { catalog.create('authors', req.body); flash(req, 'Autor creado.'); res.redirect('/admin'); });
  app.post('/authors/:id/edit', requireAuth, (req, res) => { catalog.update('authors', req.params.id, req.body); flash(req, 'Autor actualizado.'); res.redirect('/admin'); });
  app.post('/authors/:id/delete', requireAuth, (req, res) => { catalog.remove('authors', req.params.id); flash(req, 'Autor eliminado.'); res.redirect('/admin'); });
  app.post('/categories', requireAuth, (req, res) => { catalog.create('categories', req.body); flash(req, 'Categoría creada.'); res.redirect('/admin'); });
  app.post('/categories/:id/edit', requireAuth, (req, res) => { catalog.update('categories', req.params.id, req.body); flash(req, 'Categoría actualizada.'); res.redirect('/admin'); });
  app.post('/categories/:id/delete', requireAuth, (req, res) => { catalog.remove('categories', req.params.id); flash(req, 'Categoría eliminada.'); res.redirect('/admin'); });
  app.post('/books', requireAuth, (req, res) => { catalog.createBook(req.body); flash(req, 'Libro creado.'); res.redirect('/admin'); });
  app.post('/books/:id/edit', requireAuth, (req, res) => { catalog.updateBook(req.params.id, req.body); flash(req, 'Libro actualizado.'); res.redirect('/admin'); });
  app.post('/books/:id/delete', requireAuth, (req, res) => { catalog.remove('books', req.params.id); flash(req, 'Libro eliminado.'); res.redirect('/admin'); });
  app.post('/concepts', requireAuth, (req, res) => { catalog.addConcept(req.body); flash(req, 'Definición guardada.'); res.redirect('/admin'); });
  app.post('/concepts/:id/edit', requireAuth, (req, res) => { catalog.updateConcept(req.params.id, req.body); flash(req, 'Definición actualizada.'); res.redirect('/admin'); });
  app.post('/concepts/:id/delete', requireAuth, (req, res) => { catalog.removeConcept(req.params.id); flash(req, 'Definición eliminada.'); res.redirect('/admin'); });
  app.post('/images', requireAuth, upload.single('image'), (req, res) => { if (!req.file) return res.redirect('/admin'); catalog.addImage({ ...req.body, filename: req.file.filename, originalname: req.file.originalname, mimetype: req.file.mimetype }); flash(req, 'Imagen subida.'); res.redirect('/admin'); });
  app.post('/images/:id/delete', requireAuth, (req, res) => { const image = catalog.images().find(item => item.id === Number(req.params.id)); if (image) { fs.rmSync(path.join(__dirname, '..', 'uploads', image.filename), { force: true }); catalog.removeImage(req.params.id); } flash(req, 'Imagen eliminada.'); res.redirect('/admin'); });
  app.post('/users', requireAuth, (req, res) => { user.create(req.body); flash(req, 'Usuario creado.'); res.redirect('/admin'); });
  app.post('/users/:id/edit', requireAuth, (req, res) => { user.update(req.params.id, req.body); flash(req, 'Usuario actualizado.'); res.redirect('/admin'); });
  app.post('/users/:id/delete', requireAuth, (req, res) => { if (Number(req.params.id) !== req.session.user.id) user.remove(req.params.id); flash(req, 'Usuario eliminado.'); res.redirect('/admin'); });
}
module.exports = { registerRoutes };
