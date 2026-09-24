# Library Login Microservice

This microservice provides a standalone authentication layer for the existing library platform. It does not modify the existing monolith architecture and uses its own table in the same PostgreSQL database called `library`.

## Relevant files

- `app.py`: Flask authentication service.
- `database-init.sql`: SQL script to create the auth table if needed.
- `.env.example`: environment variables template.
- `requirements.txt`: Python dependency list.

## Setup

1. Create a virtual environment.
2. Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set your PostgreSQL credentials.
4. Run the service:

```bash
python app.py
```

The app listens on port 5000 by default.

## Endpoints

### Register
- POST /register

### Login
- POST /login

### Logout
- POST /logout

### Session status
- GET /session

### Service health
- GET /health

### Swagger documentation
- /swagger.json
- /swagger.xml
- /docs

## Default response format

If no format is specified in the URL, the service returns XML by default.

Examples:

```http
GET /health?format=json
POST /login?format=xml
```

## Notes

- Passwords are never stored in plaintext.
- The service creates a Flask session to maintain an authenticated user.
- The service uses the same PostgreSQL database as the library project without modifying the existing tables used by other services.
