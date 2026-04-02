from locust import HttpUser, task, between

class TripUser(HttpUser):
    wait_time = between(1, 3)

    # 정상 요청
    @task(3)
    def get_products(self):
        self.client.get("/api/v1/products")

    # 404 에러
    @task(1)
    def wrong_url(self):
        self.client.get("/api/v1/unknown")

    # 500 유도 (존재하지 않는 ID)
    @task(1)
    def server_error(self):
        self.client.get("/api/v1/products/999999")

    # 응답 검증
    @task(1)
    def check_fail(self):
        with self.client.get("/api/v1/products", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"error 발생: {response.status_code}")