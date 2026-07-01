# Hot Crust Cafe

A simple Flask menu website with admin upload, image import, and WhatsApp ordering.

## Features

- Admin login to add menu items
- Upload item image, name, description, and price
- Menu page shows stored items and detected static images
- Edit menu items in admin
- Delete stored menu items and static images
- Import images from `static/` and `static/uploads/` into SQLite-backed menu
- Data stored in SQLite (`data/menu.db`) with automatic migration from `data/menu.json`

## Setup

```bash
python -m pip install -r requirements.txt
```

## Run locally

```bash
set FLASK_DEBUG=1
python app.py
```

Then open http://127.0.0.1:5000

## Admin login

Username: `admin`
Password: set `ADMIN_PASSWORD` environment variable, or use default `hotcrust2026`.

## Recommended environment variables

- `SECRET_KEY` — Flask session secret
- `ADMIN_PASSWORD` — admin password
- `WHATSAPP_NUMBER` — phone number for prefilled WhatsApp order links
- `PORT` — port for production server

## Production

Use a WSGI server instead of Flask debug server.

Example with Waitress:

```bash
pip install waitress
waitress-serve --port=8080 app:app
```

Example with Gunicorn:

```bash
pip install gunicorn
gunicorn --workers 3 --bind 0.0.0.0:8000 app:app
```

## Notes

- Data now persists in `data/menu.db`.
- Existing `data/menu.json` is migrated automatically on first run.
- Keep `data/` and `static/uploads/` writable.
- For multiple workers, use a single shared `data/menu.db` file or migrate to a proper database server.
