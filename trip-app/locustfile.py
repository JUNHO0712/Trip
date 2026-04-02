from locust import HttpUser, task, between

class TripUser(HttpUser):
    wait_time = between(1, 3)

    # ✅ 정상 요청
    @task(3)
    def get_trip(self):
        self.client.get("/api/trips")

    # ❗ 404 에러 유도
    @task(1)
    def wrong_url(self):
        self.client.get("/wrong-url")

    # ❗ 400 에러 유도 (필수값 누락)
    @task(1)
    def bad_request(self):
        self.client.post("/api/trips", json={})

    # ❗ 상태코드 체크해서 강제 실패 처리
    @task(1)
    def check_fail(self):
        with self.client.get("/api/trips", catch_response=True) as response:
            if response.status_code != 200:
                response.failure("error 발생")