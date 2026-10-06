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

The app listens on port 5000 by default. It stores server-side sessions and one-time refresh tokens in the shared password-protected Redis instance.

## Endpoints

### Register
- POST /register

### Login
- POST /login

Successful login returns an HS256 access JWT with `user_id`, `role_id`, `role`, and `jti`; the access token expires after 20 minutes. Store the returned refresh token securely and call `POST /refresh` before expiry to rotate it.

### Logout
- POST /logout

### Session status
- GET /session

### Refresh access token
- POST /refresh with `{"refresh_token":"..."}`

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
- Flask sessions and refresh token records are stored in Redis with a seven-day TTL. Logout removes the refresh record, destroys the session, and revokes the active access token in Redis.
- The same `JWT_SECRET_KEY` must be configured in Login and every service that accepts its tokens.
- The service uses the same PostgreSQL database as the library project without modifying the existing tables used by other services.
