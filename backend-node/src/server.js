const path = require('node:path');
const fs = require('node:fs');
const express = require('express');
const session = require('express-session');
const db = require('./db');
const { seedAdmin } = require('./models/userModel');
const { registerRoutes } = require('./routes');

const app = express();
const port = Number(process.env.PORT || 3000);
fs.mkdirSync(path.join(__dirname, '..', 'uploads'), { recursive: true });
seedAdmin();

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.urlencoded({ extended: true }));
app.use('/uploads', express.static(path.join(__dirname, '..', 'uploads')));
app.use(express.static(path.join(__dirname, 'public')));
app.use(session({
  secret: process.env.SESSION_SECRET || 'cambia-esta-clave-en-produccion',
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', maxAge: 8 * 60 * 60 * 1000 }
}));
app.use((req, res, next) => {
  res.locals.user = req.session.user || null;
  res.locals.notice = req.session.notice || null;
  delete req.session.notice;
  next();
});
registerRoutes(app);
app.use((req, res) => res.status(404).render('error', { title: 'No encontrado', message: 'La página solicitada no existe.' }));
app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).render('error', { title: 'Error', message: 'No fue posible completar la operación.' });
});
app.listen(port, () => console.log(`Libreria disponible en http://localhost:${port}`));
process.on('SIGINT', () => { db.close(); process.exit(0); });
