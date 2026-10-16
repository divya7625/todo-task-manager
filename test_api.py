"""API tests. Run:  python -m unittest -v test_api"""
import os
import tempfile
import unittest
from datetime import date, timedelta

from app import create_app


class TaskApiTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.client = create_app(self.path).test_client()

    def tearDown(self):
        os.remove(self.path)

    def make(self, **kw):
        body = {"title": "Write report", "description": "Q3", "deadline": "2030-01-01", "priority": "High"}
        body.update(kw)
        return self.client.post("/api/tasks", json=body)

    def test_create_and_get(self):
        r = self.make()
        self.assertEqual(r.status_code, 201)
        task = r.get_json()
        self.assertEqual(task["status"], "Pending")
        got = self.client.get(f"/api/tasks/{task['id']}")
        self.assertEqual(got.get_json()["title"], "Write report")

    def test_created_by(self):
        self.assertEqual(self.make().get_json()["created_by"], "Me")
        task = self.make(created_by="Maia").get_json()
        self.assertEqual(task["created_by"], "Maia")
        r = self.client.put(f"/api/tasks/{task['id']}", json={"title": "X", "created_by": "Raj"})
        self.assertEqual(r.get_json()["created_by"], "Raj")

    def test_title_required(self):
        for bad in ("", "   ", None):
            r = self.make(title=bad)
            self.assertEqual(r.status_code, 400)
            self.assertIn("title", r.get_json()["errors"])

    def test_invalid_fields(self):
        self.assertEqual(self.make(priority="Urgent").status_code, 400)
        self.assertEqual(self.make(deadline="31-12-2030").status_code, 400)
        self.assertEqual(self.make(status="Done").status_code, 400)

    def test_put_updates_task(self):
        tid = self.make().get_json()["id"]
        r = self.client.put(f"/api/tasks/{tid}", json={"title": "New", "priority": "Low"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["title"], "New")
        self.assertEqual(r.get_json()["priority"], "Low")
        self.assertEqual(self.client.put(f"/api/tasks/{tid}", json={"title": ""}).status_code, 400)

    def test_patch_status(self):
        tid = self.make().get_json()["id"]
        r = self.client.patch(f"/api/tasks/{tid}", json={"status": "Completed"})
        self.assertEqual(r.get_json()["status"], "Completed")
        self.assertEqual(self.client.patch(f"/api/tasks/{tid}", json={}).status_code, 400)

    def test_delete(self):
        tid = self.make().get_json()["id"]
        self.assertEqual(self.client.delete(f"/api/tasks/{tid}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/tasks/{tid}").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/tasks/{tid}").status_code, 404)

    def test_filters_search_priority(self):
        a = self.make(title="Buy milk", priority="Low").get_json()["id"]
        self.make(title="Pay rent", priority="High")
        self.client.patch(f"/api/tasks/{a}", json={"status": "Completed"})
        count = lambda q: self.client.get("/api/tasks" + q).get_json()["total"]
        self.assertEqual(count(""), 2)
        self.assertEqual(count("?status=Completed"), 1)
        self.assertEqual(count("?status=Pending"), 1)
        self.assertEqual(count("?search=rent"), 1)
        self.assertEqual(count("?priority=High"), 1)

    def test_overdue(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        tid = self.make(title="Late", deadline=yesterday).get_json()
        self.assertTrue(tid["overdue"])
        self.make(title="Future")
        data = self.client.get("/api/tasks?overdue=true").get_json()
        self.assertEqual(data["total"], 1)
        self.client.patch(f"/api/tasks/{tid['id']}", json={"status": "Completed"})
        self.assertEqual(self.client.get("/api/tasks?overdue=true").get_json()["total"], 0)

    def test_pagination(self):
        for i in range(12):
            self.make(title=f"T{i}")
        d = self.client.get("/api/tasks?per_page=5&page=3").get_json()
        self.assertEqual(len(d["items"]), 2)
        self.assertEqual(d["total"], 12)

    def test_persistence(self):
        self.make(title="Persist me")
        again = create_app(self.path).test_client()
        self.assertEqual(again.get("/api/tasks").get_json()["total"], 1)


if __name__ == "__main__":
    unittest.main()
