from typing import Literal
from pydantic import BaseModel, Field


class BookingRequest(BaseModel):
    user_id: str
    event_id: str
    seat_count: int = Field(gt=0)
    idempotency_key: str


class BookingResponse(BaseModel):
    booking_id: str
    status: str


class SeedInventoryRequest(BaseModel):
    event_id: str
    total_seats: int = Field(ge=0)


class PaymentRequest(BaseModel):
    result: Literal["success", "failed"]


class EventSeatTypeCreate(BaseModel):
    seat_type: str
    price: int = Field(ge=0)
    total_seats: int = Field(ge=0)


class EventCreate(BaseModel):
    title: str
    type: str
    date_time: str
    location: str
    seat_types: list[EventSeatTypeCreate]


class EventSeatTypeResponse(BaseModel):
    seat_type: str
    price: int
    total_seats: int
    available_seats: int


class EventResponse(BaseModel):
    id: str
    title: str
    type: str
    date_time: str
    location: str
    seat_types: list[EventSeatTypeResponse]


class EventBookingRequest(BaseModel):
    seat_type: str
    seat_count: int = Field(gt=0)


class EventBookingResponse(BaseModel):
    booking_id: str
    status: str
    order_id: str | None = None
    amount: int | None = None
    currency: str | None = None
    key_id: str | None = None


class EventWaitlistJoinRequest(BaseModel):
    seat_type: str
    seat_count: int = Field(gt=0)


class EventWaitlistJoinResponse(BaseModel):
    waitlist_id: str
    status: str
    position: int


class EventWaitlistStatusResponse(BaseModel):
    waitlist_id: str
    status: str
    position: int | None = None
    booking_id: str | None = None


class DiningTableSlotCreate(BaseModel):
    restaurant_name: str
    table_number: str
    capacity: int = Field(gt=0)
    price_per_table: int = Field(ge=0)
    date_time: str


class DiningTableSlotResponse(BaseModel):
    id: str
    restaurant_name: str
    table_number: str
    capacity: int
    price_per_table: int
    date_time: str
    status: str


class DiningTableBookingResponse(BaseModel):
    booking_id: str
    status: str
    order_id: str | None = None
    amount: int | None = None
    currency: str | None = None
    key_id: str | None = None


class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class DeferredEventBookingResponse(BaseModel):
    request_id: str
    status: str
    message: str


class DeferredEventBookingStatusResponse(BaseModel):
    request_id: str
    event_id: str
    seat_type: str
    seat_count: int
    status: str
    queued_at: str


class OutboxEventResponse(BaseModel):
    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    status: str
    attempts: int
    created_at: str
