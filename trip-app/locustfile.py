import os
from datetime import date, timedelta
from locust import HttpUser, between, task

DEFAULT_HOST = "http://100.64.0.1:30088"

HEADERS = {
    "Content-Type": "application/json",
    "X-User-Id": "1",
}

# 실행 시 시나리오 선택
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
        if not data:
            raise Exception("상품 없음")

        product = data[0]

        # 🔥 snake_case 기준으로 가져오기
        product_id = product.get("product_id")

        if not product_id:
            raise Exception(f"product_id 못찾음: {product}")

        return product_id

    def _preview(self, product_id):
        payload = {
            "products": [
                {
                    "product_id": product_id,   # 🔥 핵심 수정
                    "quantity": 1,
                    "departureDate": self._departure_date(),  # 🔥 핵심 수정
                }
            ]
        }

        res = self.client.post(
            "/api/v1/orders/preview",
            json=payload,
            headers=HEADERS,
            name="2. POST /orders/preview",
        )

        if res.status_code != 200:
            print("❌ preview 실패:", res.text)
            return None, None

        data = res.json().get("data", {})
        return data.get("order_number"), data.get("total_price")
    @task
    def run_scenario(self):
        product_id = self._get_product()
        order_id, total_price = self._preview(product_id)

        # preview 실패하면 종료
        if not order_id:
            return

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

        # 🔥 2️⃣ 결제 에러 (트레이싱용 ⭐ 핵심)
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

        # 🔥 3️⃣ 장바구니 에러
        elif SCENARIO == "cart":
            payload = {
                "product_id": 999999,
                "quantity": 1,
                "departure_date": self._departure_date(),
            }

            self.client.post(
                "/api/v1/carts",
                json=payload,
                headers=HEADERS,
                name="CART ERROR",
            )

        # 🔥 한 번 실행하고 종료 (데모용)
        self.environment.runner.quit()