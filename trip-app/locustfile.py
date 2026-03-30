from locust import HttpUser, task, between

class TripUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def test_api(self):
        self.client.get("/")