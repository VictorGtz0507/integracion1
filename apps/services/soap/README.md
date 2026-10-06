# Library Book Service (Flask + PostgreSQL)

This microservice exposes CRUD endpoints for the library books catalog using the database schema from the project.

## Files

- `app.py`: Flask API with PostgreSQL connection and CORS enabled.
- `.env`: local environment variables for database credentials.
- `.env.example`: template used to configure the service.
- `requirements.txt`: Python dependencies.
- `library.xml`: sample XML reference built from the same book structure.

## Setup

1. Create and activate a Python virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure the database settings in `.env` if needed.

4. Run the service:

   ```bash
   python app.py
   ```

The service listens on port 5001 by default (Login uses port 5000):

```text
http://localhost:5001
```

## Endpoints

### Health check
- `GET /health`

### List all books
- `GET /books`

### Get one book
- `GET /books/<id>`

### Search by column
- `GET /books/search?title=...`
- `GET /books/search?isbn=...`
- `GET /books/search?author=...`
- `GET /books/search?category=...`
- `GET /books/search?published_year=2020`
- `GET /books/search?min_price=10&max_price=30`

### Create a book
- `POST /books`

All book writes require an administrator JWT in `Authorization: Bearer <JWT>`. Public GET catalog routes remain available without a token; Redis cache failures fall back to PostgreSQL for these reads.

### Update a book
- `PUT /books/<id>`
- `PATCH /books/<id>`

### Delete a book
- `DELETE /books/<id>`

## Example payload

```json
{
  "title": "The Pragmatic Programmer",
  "isbn": "9780201616224",
  "description": "Software engineering classic",
  "price": 39.99,
  "stock": 18,
  "published_year": 1999,
  "authors": ["Andrew Hunt", "David Thomas"],
  "categories": ["Technology"],
  "concepts": [
    {"term": "Refactoring", "definition": "Improve code without changing behavior."}
  ],
  "images": [
    {"filename": "book-cover.jpg", "original_name": "book-cover.jpg", "mime_type": "image/jpeg"}
  ]
}
```
