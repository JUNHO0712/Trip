import os
from datetime import date, timedelta
from urllib.parse import urlparse

from locust import HttpUser, between, task


DEFAULT_HOST = "http://100.64.0.1:30088"
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "X-User-Id": "1",
}
ERROR_SCENARIO = os.getenv("TRIP_ERROR_SCENARIO", "all").lower()
REQUESTED_HOST = os.getenv("TRIP_HOST", DEFAULT_HOST)


def _resolve_scenario_from_path(requested_path):
    if requested_path.endswith("/orders/payment/retry"):
        return "payment_retry"
    if requested_path.endswith("/orders/payment"):
        return "payment"
    if requested_path.endswith("/carts"):
        return "cart"
    return ERROR_SCENARIO


def _normalize_host(requested_host):
    parsed = urlparse(requested_host)
    requested_path = parsed.path.rstrip("/")
    if parsed.scheme and parsed.netloc:
        normalized_host = f"{parsed.scheme}://{parsed.netloc}"
        return normalized_host, _resolve_scenario_from_path(requested_path)

    return requested_host, ERROR_SCENARIO


NORMALIZED_HOST, DEFAULT_SELECTED_SCENARIO = _normalize_host(REQUESTED_HOST)


class TripUser(HttpUser):
    wait_time = between(1, 3)
    host = NORMALIZED_HOST

    def on_start(self):
        self.selected_scenario = DEFAULT_SELECTED_SCENARIO

    def _should_run(self, scenario_name):
        selected = getattr(self, "selected_scenario", ERROR_SCENARIO)
        return selected in ("all", scenario_name)

    def _resolve_scenario(self, requested_path):
        return _resolve_scenario_from_path(requested_path)

    def _departure_date(self):
        return (date.today() + timedelta(days=7)).isoformat()

    def _get_first_product(self):
        response = self.client.get(
            "/api/v1/products",
            headers=DEFAULT_HEADERS,
            name="/products",
        )
        response.raise_for_status()

        payload = response.json()
        products = payload.get("data") or []
        if not products:
            raise RuntimeError("상품 목록이 비어 있어 오류 시나리오를 진행할 수 없습니다.")

        return products[0]

    def _create_order_preview(self):
        product = self._get_first_product()
        quantity = 1
        product_id = product["product_id"]

        preview_payload = {
            "products": [
                {
                    "productId": product_id,
                    "quantity": quantity,
                    "departureDate": self._departure_date(),
                }
            ]
        }

        response = self.client.post(
            "/api/v1/orders/preview",
            json=preview_payload,
            headers=DEFAULT_HEADERS,
            name="/orders/preview",
        )
        response.raise_for_status()

        order_data = response.json().get("data") or {}
        order_id = order_data.get("orderId") or order_data.get("orderNumber")
        total_price = order_data.get("totalPrice")
        if not order_id:
            raise RuntimeError("주문 미리보기 응답에서 orderId를 찾을 수 없습니다.")
        if total_price is None:
            raise RuntimeError("주문 미리보기 응답에서 totalPrice를 찾을 수 없습니다.")

        return order_id, total_price

    @task(1)
    def payment_error(self):
        if not self._should_run("payment"):
            return

        order_id, total_amount = self._create_order_preview()

        payment_payload = {
            "orderId": order_id,
            "totalAmount": total_amount + 1,
            "paymentMethod": "CARD",
        }

        self.client.post(
            "/api/v1/orders/payment",
            json=payment_payload,
            headers=DEFAULT_HEADERS,
            name="/orders/payment",
        )

    @task(1)
    def payment_retry_error(self):
        if not self._should_run("payment_retry"):
            return

        order_id, total_amount = self._create_order_preview()

        payment_payload = {
            "orderId": order_id,
            "totalAmount": total_amount,
            "paymentMethod": "CARD",
        }

        first_response = self.client.post(
            "/api/v1/orders/payment",
            json=payment_payload,
            headers=DEFAULT_HEADERS,
            name="/orders/payment/first-success",
        )
        first_response.raise_for_status()

        self.client.post(
            "/api/v1/orders/payment",
            json=payment_payload,
            headers=DEFAULT_HEADERS,
            name="/orders/payment/retry",
        )

    @task(1)
    def cart_error(self):
        if not self._should_run("cart"):
            return

        cart_payload = {
            "productId": 999999,
            "quantity": 1,
            "departureDate": self._departure_date(),
        }

        self.client.post(
            "/api/v1/carts",
            json=cart_payload,
            headers=DEFAULT_HEADERS,
            name="/carts",
        )
