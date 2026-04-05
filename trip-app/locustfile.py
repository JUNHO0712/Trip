from locust import HttpUser, task, between, tag

class TracingDemoUser(HttpUser):
    wait_time = between(1, 2)

    # 기본 host는 Locust 요구사항 때문에만 둡니다.
    # 실제 요청은 각 서비스의 절대 URL(NodePort)로 직접 보냅니다.
    host = "http://100.64.0.1:30088"

    headers = {
        "Content-Type": "application/json",
        "X-User-Id": "1",
    }

    @tag("backend")
    @task
    def backend_500(self):
        # 장애 대상: trip-backend 파드
        # 설명: 백엔드에 실제 존재하는 테스트용 강제 에러 엔드포인트 호출
        self.client.get(
            "http://100.64.0.1:30088/error-test?test=true",
            headers=self.headers,
            name="trip-backend 500",
        )

    @tag("cart")
    @task
    def cart_404(self):
        # 장애 대상: trip-cart 파드
        # 설명: trip-cart의 NodePort(31371)로 없는 경로를 직접 호출하여 404 유도
        self.client.get(
            "http://100.64.0.1:31371/wrong-path-demo",
            headers=self.headers,
            name="trip-cart 404",
        )

    @tag("payment")
    @task
    def payment_404(self):
        # 장애 대상: trip-payment 파드
        # 설명: trip-payment의 NodePort(30839)로 없는 경로를 직접 호출하여 404 유도
        self.client.get(
            "http://100.64.0.1:30839/wrong-path-demo",
            headers=self.headers,
            name="trip-payment 404",
        )