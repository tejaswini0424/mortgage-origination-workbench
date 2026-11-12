"""Exercise the deployed stack through Nginx using a disposable synthetic case."""

import os
import sys
import time

import httpx

from benchmarks.run import fixture, values_for

def main():
    base_url = os.getenv("WORKBENCH_URL", "http://127.0.0.1:8080")
    with httpx.Client(base_url=base_url, timeout=10) as client:
        assert "Mortgage Origination Workbench" in client.get("/").raise_for_status().text
        login = {"username": "reviewer", "password": os.environ["REVIEWER_PASSWORD"]}
        client.post("/api/v1/session", json=login).raise_for_status()
        if len(sys.argv) == 2:
            case = client.get("/api/v1/cases/" + sys.argv[1]).raise_for_status().json()
            assert case["status"] == "exported"
            assert client.get("/api/v1/cases/" + case["id"] + "/exports/latest").raise_for_status().json()["review_note"]
            return
        borrower = "Fictional Compose Borrower"
        case = client.post("/api/v1/cases", json={"title": "Compose smoke test", "borrower": borrower}).raise_for_status().json()
        path = "/api/v1/cases/" + case["id"]
        document = fixture("pay_stub", values_for(borrower)["pay_stub"])
        client.post(path + "/documents", files={"file": ("pay.pdf", document, "application/pdf")}).raise_for_status()
        for _ in range(40):
            status = client.get(path).raise_for_status().json()
            doc = status["documents"][0]
            if doc["status"] == "completed":
                break
            if doc["status"] == "failed":
                raise RuntimeError(doc["error"])
            time.sleep(1)
        else:
            raise RuntimeError("Worker did not complete processing.")
        for field in doc["fields"]:
            client.put(f"/api/v1/documents/{doc['id']}/fields/{field['key']}", json={"value": field["value"]}).raise_for_status()
        client.post(path + "/release", json={"note": "Synthetic Compose integration test."}).raise_for_status()
        assert client.get(path + "/exports/latest").raise_for_status().json()["case"]["id"] == case["id"]
        print(case["id"])

if __name__ == "__main__":
    main()
