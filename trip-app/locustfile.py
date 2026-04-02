from locust import HttpUser, task, between

class TripUser(HttpUser):
    wait_time = between(1, 3)

    # ✅ 정상 요청 (60%)
    @task(3)
    def get_trip(self):
        self.client.get("/api/trips")

    # ❗ 404 에러 (10%)
    @task(1)
    def wrong_url(self):
        self.client.get("/wrong-url")

    # ❗ 400 에러 (10%)
    @task(1)
    def bad_request(self):
        self.client.post("/api/trips", json={})

    # 🔥 500 에러 유도 (핵심 ⭐)
    @task(1)
    def server_error(self):
        # 👉 방법 1: 존재하지 않는 ID (서버에서 처리 안 하면 500 가능)
        self.client.get("/api/trips/999999999")

        # 👉 만약 위가 500 안 나오면 아래로 바꿔
        # self.client.get("/error-test")

    # ❗ 응답 검증 (실패 강제 표시)
    @task(1)
    def check_fail(self):
        with self.client.get("/api/trips", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"error 발생: {response.status_code}")