from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import uuid
# Mock database of verified orders, transactions, and tracking records
MOCK_EXTERNAL_DATABASE = {
    "cust-a-freshcart": {
        "ORD-FRESH-101": {
            "order_id": "ORD-FRESH-101",
            "customer_id": "cust-sarah-101",
            "customer_name": "Sarah Connor",
            "customer_phone": "+1-555-0101",
            "status": "DELIVERED",
            "delivered_at": (datetime.utcnow() - timedelta(minutes=35)).isoformat(),
            "items": [
                {"name": "Organic Whole Milk 1L", "price": 4.50, "qty": 1},
                {"name": "Hass Avocados (Pack of 3)", "price": 5.00, "qty": 1},
                {"name": "Greek Strawberry Yogurt 200g", "price": 3.50, "qty": 2},
                {"name": "Artisan Sourdough Bread", "price": 4.50, "qty": 1}
            ],
            "subtotal": 21.00,
            "delivery_fee": 0.00,
            "total_paid": 21.00,
            "payment_method": "FreshCart Wallet / UPI",
            "rider_name": "Ramesh Kumar"
        },
        "ORD-FRESH-102": {
            "order_id": "ORD-FRESH-102",
            "customer_id": "cust-david-102",
            "customer_name": "David Miller",
            "customer_phone": "+1-555-0102",
            "status": "IN_TRANSIT",
            "eta_minutes": 8,
            "items": [
                {"name": "Cold Pressed Orange Juice 500ml", "price": 6.00, "qty": 2},
                {"name": "Farm Fresh Eggs (12 pack)", "price": 4.50, "qty": 1}
            ],
            "total_paid": 16.50,
            "payment_method": "Credit Card ending in 4242",
            "rider_name": "Sanjay Rao"
        }
    },
    "cust-b-biterush": {
        "ORD-BITE-201": {
            "order_id": "ORD-BITE-201",
            "customer_id": "cust-amit-201",
            "customer_name": "Amit Sharma",
            "customer_phone": "+1-555-0201",
            "restaurant_name": "Spice Garden Kitchen",
            "status": "DELIVERED",
            "delivered_at": (datetime.utcnow() - timedelta(minutes=40)).isoformat(),
            "items": [
                {"name": "Butter Chicken Deluxe", "price": 14.00, "qty": 1},
                {"name": "Garlic Butter Naan", "price": 3.00, "qty": 2},
                {"name": "Mango Lassi Special", "price": 4.00, "qty": 1}
            ],
            "total_paid": 24.00,
            "packaging_fee": 1.50,
            "rider_name": "Kunal Ghosh"
        },
        "ORD-BITE-202": {
            "order_id": "ORD-BITE-202",
            "customer_id": "cust-riya-202",
            "customer_name": "Riya Sen",
            "customer_phone": "+1-555-0202",
            "restaurant_name": "Luigi's Woodfired Pizza",
            "status": "PREPARING",
            "delay_warning": "Kitchen experiencing peak rush; ETA extended by 12 mins.",
            "items": [
                {"name": "Margherita 12-inch Pizza", "price": 16.00, "qty": 1},
                {"name": "Tiramisu Cup", "price": 7.00, "qty": 1}
            ],
            "total_paid": 23.00
        }
    },
    "cust-c-swiftride": {
        "RIDE-SWIFT-301": {
            "order_id": "RIDE-SWIFT-301",
            "customer_id": "cust-vikram-301",
            "customer_name": "Vikram Patel",
            "customer_phone": "+1-555-0301",
            "status": "COMPLETED",
            "completed_at": (datetime.utcnow() - timedelta(minutes=25)).isoformat(),
            "driver_name": "Suresh Gowda",
            "vehicle_number": "KA-05-AB-9876",
            "vehicle_model": "White Suzuki Dzire Sedan",
            "origin": "Indiranagar 100ft Road",
            "destination": "Kempegowda Int'l Airport",
            "estimated_fare": 21.00,
            "actual_fare": 28.50,
            "fare_difference": 7.50,
            "route_detour_detected": True,
            "detour_reason": "Driver took alternate ring road without highway toll"
        }
    },
    "cust-d-stylenova": {
        "ORD-STYLE-401": {
            "order_id": "ORD-STYLE-401",
            "customer_id": "cust-meera-401",
            "customer_name": "Meera Kapoor",
            "customer_phone": "+1-555-0401",
            "status": "DELIVERED",
            "delivered_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
            "items": [
                {
                    "item_id": "ITM-STYLE-001",
                    "name": "Floral Tiered Midi Dress",
                    "size": "M",
                    "color": "Sage Green",
                    "price": 45.00,
                    "available_sizes_for_exchange": ["XS", "S", "L", "XL"]
                }
            ],
            "total_paid": 45.00,
            "return_window_expiry": (datetime.utcnow() + timedelta(days=13)).isoformat()
        }
    },
    "cust-e-voltexpress": {
        "AWB-VOLT-501": {
            "order_id": "AWB-VOLT-501",
            "customer_id": "cust-apex-501",
            "customer_name": "Apex Electronics Ltd",
            "customer_phone": "+1-555-0501",
            "status": "IN_TRANSIT",
            "current_location": "Bangalore North Fulfillment Hub",
            "scheduled_delivery_date": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "weight_kg": 4.8,
            "contents": "Dual Monitor Desk Mount Bracket",
            "rescheduling_available": True
        }
    }
}

class MockExternalAPIService:
    """Verified backend service integration for all 5 customer tenants."""

    @staticmethod
    def get_order_details(
        tenant_id: str,
        order_id: str,
        customer_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve an order only when it belongs to the specified tenant
        and customer.
        """
        if not tenant_id or not order_id or not customer_id:
            return None

        tenant_orders = MOCK_EXTERNAL_DATABASE.get(tenant_id, {})
        normalized_id = order_id.strip().upper()

        order = tenant_orders.get(normalized_id)

        if not order:
            return None

        order_customer_id = order.get("customer_id")

        if not order_customer_id:
            return None

        if order_customer_id.strip().casefold() != customer_id.strip().casefold():
            return None

        return order

    @staticmethod
    def get_customer_contact(
        tenant_id: str,
        customer_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve customer contact details from this tenant's
        verified mock order records.
        """
        if not tenant_id or not customer_id:
            return None

        tenant_orders = MOCK_EXTERNAL_DATABASE.get(tenant_id, {})

        for order in tenant_orders.values():
            order_customer_id = order.get("customer_id")

            if (
                order_customer_id
                and order_customer_id.strip().casefold()
                == customer_id.strip().casefold()
            ):
                return {
                    "customer_name": order.get("customer_name"),
                    "customer_phone": order.get("customer_phone"),
                    "customer_email": None
                }

        return None

    @staticmethod
    def execute_instant_refund(
        tenant_id: str,
        order_id: str,
        customer_id: str,
        amount: float,
        reason: str
    ) -> Dict[str, Any]:
        """
        Simulate a refund only after verifying order ownership and amount.
        This does not execute a real payment-provider refund.
        """

        order = MockExternalAPIService.get_order_details(
            tenant_id=tenant_id,
            order_id=order_id,
            customer_id=customer_id
        )

        if not order:
            return {
                "success": False,
                "error": "Order not found or customer ownership verification failed."
            }

        try:
            refund_amount = float(amount)
            order_total = float(
                order.get("total_paid", order.get("actual_fare", 0))
            )
        except (TypeError, ValueError):
            return {
                "success": False,
                "error": "Invalid refund amount."
            }

        if refund_amount <= 0 or refund_amount > order_total:
            return {
                "success": False,
                "error": "Refund amount is invalid or exceeds the order total."
            }

        txn_id = (
            f"TXN-REF-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            f"-{uuid.uuid4().hex[:6].upper()}"
        )

        return {
            "success": True,
            "transaction_id": txn_id,
            "order_id": order_id.strip().upper(),
            "refund_amount": refund_amount,
            "refund_mode": "MOCK_ORIGINAL_PAYMENT_METHOD_AND_WALLET",
            "estimated_credit_time": "Simulated - Instant to 2 hours",
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def execute_size_exchange(
        tenant_id: str,
        order_id: str,
        new_size: str
    ) -> Dict[str, Any]:
        exchange_id = f"EXC-{order_id}-{datetime.utcnow().strftime('%H%M%S')}"
        return {
            "success": True,
            "exchange_ticket_id": exchange_id,
            "order_id": order_id,
            "new_size": new_size,
            "pickup_and_delivery_type": "DOORSTEP_SWAP",
            "pickup_eta": "Tomorrow between 10:00 AM - 2:00 PM",
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def execute_manifest_reschedule(
        tenant_id: str,
        order_id: str,
        new_slot: str
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "consignment_id": order_id,
            "new_delivery_schedule": new_slot,
            "manifest_status": "RESCHEDULED_CONFIRMED",
            "hub_notified": True,
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def establish_masked_call_bridge(
        tenant_id: str,
        order_id: str,
        customer_phone: str
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "bridge_number": "+1-888-555-CALL",
            "extension_pin": "4920",
            "valid_minutes": 120,
            "message": "Call masked bridge active for 2 hours. Driver and customer numbers remain private."
        }
