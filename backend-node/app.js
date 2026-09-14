const fs = require('node:fs');
const path = require('node:path');

// Carga .env sin exigirlo en instalaciones nuevas.
const envPath = path.join(__dirname, '.env');
if (fs.existsSync(envPath)) {
	for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
		const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
		if (match && !Object.hasOwn(process.env, match[1])) process.env[match[1]] = match[2].replace(/^['"]|['"]$/g, '');
	}
}

// Punto de entrada compatible con la estructura MVC del curso.
require('./src/server');