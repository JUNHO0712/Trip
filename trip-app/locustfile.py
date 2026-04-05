import os
from datetime import date, timedelta
from urllib.parse import urlparse

from locust import HttpUser, task


DEFAULT_HOST = "http://100.64.0.1:30088"
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "X-User-Id": "1",
}

ERROR_SCENARIO = os.getenv("TRIP_ERROR_SCENARIO", "payment").lower()
REQUESTED_HOST = os.getenv("TRIP_HOST", DEFAULT_HOST)


def _normalize_host(requested_host):
    parsed = urlparse(requested_host)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return requested_host


NORMALIZED_HOST = _normalize_host(REQUESTED_HOST)


class TripUser(HttpUser):
    host = NORMALIZED_HOST

    def _departure_date(self):
        return (date.today() + timedelta(days=7)).isoformat()

    def _get_first_product(self):
        response = self.client.get(
            "/api/v1/products",
            headers=DEFAULT_HEADERS,
            name="/products",
        )
        response.raise_for_status()

        products = response.json().get("data") or []
        if not products:
            raise RuntimeError("상품 없음")

        return products[0]

    def _create_order_preview(self):
        product = self._get_first_product()
        product_id = product["product_id"]

        payload = {
            "products": [
                {
                    "productId": product_id,
                    "quantity": 1,
                    "departureDate": self._departure_date(),
                }
            ]
        }

        response = self.client.post(
            "/api/v1/orders/preview",
            json=payload,
            headers=DEFAULT_HEADERS,
            name="/orders/preview",
        )
        response.raise_for_status()

        data = response.json().get("data") or {}
        return data["orderId"], data["totalPrice"]

    @task
    def run_scenario(self):
        if ERROR_SCENARIO == "payment":
            self.payment_error()

        elif ERROR_SCENARIO == "payment_retry":
            self.payment_retry_error()

        elif ERROR_SCENARIO == "cart":
            self.cart_error()

        # 🔥 핵심: 1번 실행 후 종료
        self.environment.runner.quit()

    # ------------------------
    # 시나리오들
    # ------------------------

    def payment_error(self):
        order_id, total = self._create_order_preview()

        self.client.post(
            "/api/v1/orders/payment",
            json={
                "orderId": order_id,
                "totalAmount": total + 1,  # ❌ 일부러 틀림
                "paymentMethod": "CARD",
            },
            headers=DEFAULT_HEADERS,
            name="/orders/payment (error)",
        )

    def payment_retry_error(self):
        order_id, total = self._create_order_preview()

        payload = {
            "orderId": order_id,
            "totalAmount": total,
            "paymentMethod": "CARD",
        }

        # 정상 결제
        self.client.post(
            "/api/v1/orders/payment",
            json=payload,
            headers=DEFAULT_HEADERS,
            name="/orders/payment (success)",
        )

        # ❌ 중복 결제
        self.client.post(
            "/api/v1/orders/payment",
            json=payload,
            headers=DEFAULT_HEADERS,
            name="/orders/payment (retry error)",
        )

    def cart_error(self):
        self.client.post(
            "/api/v1/carts",
            json={
                "productId": 999999,  # ❌ 존재하지 않음
                "quantity": 1,
                "departureDate": self._departure_date(),
            },
            headers=DEFAULT_HEADERS,
            name="/carts (error)",
        )