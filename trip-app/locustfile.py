import os
from datetime import date, timedelta
from locust import HttpUser, between, task

DEFAULT_HOST = "http://100.64.0.1:30088"

HEADERS = {
    "Content-Type": "application/json",
    "X-User-Id": "1",
}

SCENARIO = os.getenv("TRIP_ERROR_SCENARIO", "payment")


class TripUser(HttpUser):
    wait_time = between(1, 1)
    host = DEFAULT_HOST

    def _departure_date(self):
        return (date.today() + timedelta(days=7)).isoformat()

    def _get_product(self):
        res = self.client.get(
            "/api/v1/products",
            headers=HEADERS,
            name="1. GET /products",
        )
        res.raise_for_status()

        data = res.json().get("data", [])
        return data[0]

    def _preview(self, product_id):
        payload = {
            "products": [
                {
                    "productId": product_id,
                    "quantity": 1,
                    "departureDate": self._departure_date(),
                }
            ]
        }

        res = self.client.post(
            "/api/v1/orders/preview",
            json=payload,
            headers=HEADERS,
            name="2. POST /orders/preview",
        )
        res.raise_for_status()

        data = res.json().get("data", {})
        return data["orderId"], data["totalPrice"]

    @task
    def run_scenario(self):
        product = self._get_product()
        order_id, total_price = self._preview(product["product_id"])

        # 🔥 1️⃣ 정상 시나리오
        if SCENARIO == "success":
            payload = {
                "orderId": order_id,
                "totalAmount": total_price,
                "paymentMethod": "CARD",
            }

            self.client.post(
                "/api/v1/orders/payment",
                json=payload,
                headers=HEADERS,
                name="3. POST /orders/payment (SUCCESS)",
            )

        # 🔥 2️⃣ 결제 금액 오류 (추천 ⭐)
        elif SCENARIO == "payment":
            payload = {
                "orderId": order_id,
                "totalAmount": total_price + 1,  # ❌ 의도적 에러
                "paymentMethod": "CARD",
            }

            self.client.post(
                "/api/v1/orders/payment",
                json=payload,
                headers=HEADERS,
                name="3. POST /orders/payment (ERROR)",
            )

        # 🔥 3️⃣ 장바구니 오류
        elif SCENARIO == "cart":
            payload = {
                "productId": 999999,
                "quantity": 1,
                "departureDate": self._departure_date(),
            }

            self.client.post(
                "/api/v1/carts",
                json=payload,
                headers=HEADERS,
                name="CART ERROR",
            )

        # 🔥 한 번만 실행하고 종료
        self.environment.runner.quit()