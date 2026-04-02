from locust import HttpUser, task, between

class TripUser(HttpUser):
    wait_time = between(1, 2)

    # 🔥 지연 테스트 (핵심)
    @task(5)
    def get_products(self):
        self.client.get("/api/v1/products")

    # 참고용: 다른 API (비교용)
    @task(1)
    def get_product_detail(self):
        self.client.get("/api/v1/products/1")