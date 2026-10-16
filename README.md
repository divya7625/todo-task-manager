# To-Do Task Manager (Flask + SQLite)

Responsive task manager. Frontend: HTML/CSS/JS. Backend: Flask REST API. Database: SQLite.

## Run locally
```bash
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                                      # http://127.0.0.1:5000
```

## Run API tests
```bash
python -m unittest -v test_api
```

## REST API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/tasks?status=&priority=&search=&deadline=&overdue=&page=&per_page=` | List / filter / search / paginate |
| GET | `/api/tasks/<id>` | Get one task |
| POST | `/api/tasks` | Create (`title` required) |
| PUT | `/api/tasks/<id>` | Update task details |
| PATCH | `/api/tasks/<id>` | Partial update, e.g. `{"status": "Completed"}` |
| DELETE | `/api/tasks/<id>` | Delete |

Task fields: `title`, `description`, `deadline` (YYYY-MM-DD), `priority` (Low/Medium/High), `status` (Pending/Completed).
Responses include a computed `overdue` flag. Validation errors return `400` with `{"errors": {"title": "..."}}`.

Quick curl test:
```bash
curl -X POST localhost:5000/api/tasks -H "Content-Type: application/json" -d '{"title":"Test","priority":"High"}'
curl localhost:5000/api/tasks
```

## Deploy on Render
1. Push this folder to a GitHub repo.
2. Render → **New → Web Service** → connect the repo.
3. Settings: Runtime **Python 3**, Build `pip install -r requirements.txt`, Start `gunicorn app:app`
   (or choose **Blueprint** and Render reads `render.yaml`).
4. Deploy. Your app is live at `https://<name>.onrender.com`.

**Important:** Render's free plan has an ephemeral disk, so `tasks.db` resets on each redeploy/restart.
For permanent data, add a **Disk** (paid plan) mounted at `/var/data` and set env var `DB_PATH=/var/data/tasks.db`.
