from datetime import datetime
import os

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select
import razorpay

from src.infrastructure.db.session import SessionLocal
from src.application.booking_service import BookingService
from src.api.schemas.schemas import (
    BookingRequest,
    BookingResponse,
    SeedInventoryRequest,
    PaymentRequest,
    EventCreate,
    EventResponse,
    EventSeatTypeResponse,
    EventBookingRequest,
    EventBookingResponse,
    DiningTableSlotCreate,
    DiningTableSlotResponse,
    DiningTableBookingResponse,
    RazorpayVerifyRequest,
    EventWaitlistJoinRequest,
    EventWaitlistJoinResponse,
    EventWaitlistStatusResponse,
)
from src.domain.exceptions import (
    InsufficientInventoryError,
    IdempotencyConflictError,
    InvalidStateTransitionError,
)
from src.infrastructure.db.models import (
    SeatInventory,
    Event,
    EventSeatType,
    EventBooking,
    EventWaitlistEntry,
    DiningTableSlot,
    DiningTableBooking,
)
from src.infrastructure.repositories.seat_repository import SeatRepository


router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _razorpay_client() -> razorpay.Client:
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Razorpay keys not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.",
        )
    return razorpay.Client(auth=(key_id, key_secret))


def _razorpay_key_id() -> str:
    key_id = os.getenv("RAZORPAY_KEY_ID")
    if not key_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Razorpay key id not configured.",
        )
    return key_id


def _inventory_stats(inventory: SeatInventory) -> dict:
    booked_seats = inventory.total_seats - inventory.available_seats
    return {
        "event_id": inventory.event_id,
        "total_seats": inventory.total_seats,
        "available_seats": inventory.available_seats,
        "booked_seats": booked_seats,
    }


def _waitlist_position(db: Session, entry: EventWaitlistEntry) -> int:
    stmt = (
        select(EventWaitlistEntry)
        .where(EventWaitlistEntry.event_id == entry.event_id)
        .where(EventWaitlistEntry.seat_type == entry.seat_type)
        .where(EventWaitlistEntry.status == "WAITING")
        .order_by(EventWaitlistEntry.created_at)
    )
    entries = list(db.execute(stmt).scalars().all())
    for index, item in enumerate(entries, start=1):
        if item.id == entry.id:
            return index
    return len(entries)


def _process_waitlist(db: Session, event_id: str, seat_type_name: str) -> None:
    seat_stmt = (
        select(EventSeatType)
        .where(EventSeatType.event_id == event_id)
        .where(EventSeatType.seat_type == seat_type_name)
        .with_for_update()
    )
    seat_type = db.execute(seat_stmt).scalar_one_or_none()
    if not seat_type:
        return

    waitlist_stmt = (
        select(EventWaitlistEntry)
        .where(EventWaitlistEntry.event_id == event_id)
        .where(EventWaitlistEntry.seat_type == seat_type_name)
        .where(EventWaitlistEntry.status == "WAITING")
        .order_by(EventWaitlistEntry.created_at)
        .with_for_update()
    )
    waitlist_entries = list(db.execute(waitlist_stmt).scalars().all())

    for entry in waitlist_entries:
        if seat_type.available_seats < entry.seat_count:
            break

        amount_paise = seat_type.price * entry.seat_count * 100
        seat_type.available_seats -= entry.seat_count
        booking = EventBooking(
            event_id=event_id,
            seat_type=entry.seat_type,
            seat_count=entry.seat_count,
            status="PENDING",
            amount_paise=amount_paise,
            currency="INR",
        )
        db.add(booking)
        db.flush()

        client = _razorpay_client()
        order = client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": booking.id,
            }
        )
        booking.order_id = order.get("id")
        entry.status = "READY"
        entry.booking_id = booking.id


@router.get("/", response_class=HTMLResponse)
def landing_page(
    request: Request,
    event_id: str | None = None,
    db: Session = Depends(get_db),
):
    inventories: list[SeatInventory] = []

    if event_id:
        inventory = SeatRepository(db).get_by_event_id(event_id)
        if inventory:
            inventories = [inventory]
    else:
        stmt = select(SeatInventory).order_by(SeatInventory.event_id)
        inventories = list(db.execute(stmt).scalars().all())

    stats = [_inventory_stats(inv) for inv in inventories]

    stmt_events = select(Event).order_by(Event.date_time)
    events = list(db.execute(stmt_events).scalars().all())
    event_cards = []
    for event in events:
        seat_stmt = select(EventSeatType).where(EventSeatType.event_id == event.id)
        seat_types = list(db.execute(seat_stmt).scalars().all())
        event_cards.append(
            {
                "id": event.id,
                "title": event.title,
                "type": event.type,
                "date_time": event.date_time.isoformat(),
                "location": event.location,
                "seat_types": [
                    {
                        "seat_type": seat.seat_type,
                        "price": seat.price,
                        "total_seats": seat.total_seats,
                        "available_seats": seat.available_seats,
                    }
                    for seat in seat_types
                ],
            }
        )

    stmt_tables = select(DiningTableSlot).order_by(DiningTableSlot.date_time)
    table_slots = list(db.execute(stmt_tables).scalars().all())

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "inventories": stats,
            "selected_event_id": event_id,
            "events": event_cards,
            "table_slots": table_slots,
        },
    )


@router.get("/events/{event_id}/page", response_class=HTMLResponse)
def event_detail_page(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    seat_stmt = select(EventSeatType).where(EventSeatType.event_id == event.id)
    seat_types = list(db.execute(seat_stmt).scalars().all())
    return templates.TemplateResponse(
        "event_detail.html",
        {
            "request": request,
            "event": event,
            "seat_types": seat_types,
        },
    )


@router.get("/restaurants/tables/{slot_id}/page", response_class=HTMLResponse)
def table_detail_page(
    slot_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    slot = db.execute(select(DiningTableSlot).where(DiningTableSlot.id == slot_id)).scalar_one_or_none()
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table slot not found",
        )
    return templates.TemplateResponse(
        "table_detail.html",
        {
            "request": request,
            "slot": slot,
        },
    )


@router.get("/health")
def health():
    return {"message": "District Integrity Engine is running"}


@router.get("/inventory")
def list_inventory(db: Session = Depends(get_db)):
    stmt = select(SeatInventory).order_by(SeatInventory.event_id)
    inventories = list(db.execute(stmt).scalars().all())
    return [_inventory_stats(inv) for inv in inventories]


@router.get("/inventory/{event_id}")
def get_inventory(event_id: str, db: Session = Depends(get_db)):
    inventory = SeatRepository(db).get_by_event_id(event_id)
    if not inventory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory not found",
        )
    return _inventory_stats(inventory)


@router.get("/events", response_model=list[EventResponse])
def list_events(db: Session = Depends(get_db)):
    stmt = select(Event).order_by(Event.date_time)
    events = list(db.execute(stmt).scalars().all())
    results = []
    for event in events:
        seat_stmt = select(EventSeatType).where(EventSeatType.event_id == event.id)
        seat_types = list(db.execute(seat_stmt).scalars().all())
        results.append(
            EventResponse(
                id=event.id,
                title=event.title,
                type=event.type,
                date_time=event.date_time.isoformat(),
                location=event.location,
                seat_types=[
                    EventSeatTypeResponse(
                        seat_type=seat.seat_type,
                        price=seat.price,
                        total_seats=seat.total_seats,
                        available_seats=seat.available_seats,
                    )
                    for seat in seat_types
                ],
            )
        )
    return results


@router.post("/events", response_model=EventResponse)
def create_event(request: EventCreate, db: Session = Depends(get_db)):
    try:
        event_time = datetime.fromisoformat(request.date_time)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date_time format. Use ISO format.",
        ) from exc

    event = Event(
        title=request.title,
        type=request.type,
        date_time=event_time,
        location=request.location,
    )
    db.add(event)
    db.flush()

    seat_types = []
    for seat in request.seat_types:
        seat_type = EventSeatType(
            event_id=event.id,
            seat_type=seat.seat_type,
            price=seat.price,
            total_seats=seat.total_seats,
            available_seats=seat.total_seats,
        )
        db.add(seat_type)
        seat_types.append(seat_type)

    db.flush()

    return EventResponse(
        id=event.id,
        title=event.title,
        type=event.type,
        date_time=event.date_time.isoformat(),
        location=event.location,
        seat_types=[
            EventSeatTypeResponse(
                seat_type=seat.seat_type,
                price=seat.price,
                total_seats=seat.total_seats,
                available_seats=seat.available_seats,
            )
            for seat in seat_types
        ],
    )


@router.get("/events/{event_id}", response_model=EventResponse)
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    seat_stmt = select(EventSeatType).where(EventSeatType.event_id == event.id)
    seat_types = list(db.execute(seat_stmt).scalars().all())
    return EventResponse(
        id=event.id,
        title=event.title,
        type=event.type,
        date_time=event.date_time.isoformat(),
        location=event.location,
        seat_types=[
            EventSeatTypeResponse(
                seat_type=seat.seat_type,
                price=seat.price,
                total_seats=seat.total_seats,
                available_seats=seat.available_seats,
            )
            for seat in seat_types
        ],
    )


@router.post("/events/{event_id}/book", response_model=EventBookingResponse)
def book_event(
    event_id: str,
    request: EventBookingRequest,
    db: Session = Depends(get_db),
):
    seat_stmt = (
        select(EventSeatType)
        .where(EventSeatType.event_id == event_id)
        .where(EventSeatType.seat_type == request.seat_type)
        .with_for_update()
    )
    seat_type = db.execute(seat_stmt).scalar_one_or_none()
    if not seat_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seat type not found",
        )
    if seat_type.available_seats < request.seat_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Insufficient seats available",
        )

    amount_paise = seat_type.price * request.seat_count * 100
    seat_type.available_seats -= request.seat_count
    booking = EventBooking(
        event_id=event_id,
        seat_type=request.seat_type,
        seat_count=request.seat_count,
        status="PENDING",
        amount_paise=amount_paise,
        currency="INR",
    )
    db.add(booking)
    db.flush()

    client = _razorpay_client()
    order = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": booking.id,
        }
    )
    booking.order_id = order.get("id")

    return EventBookingResponse(
        booking_id=booking.id,
        status=booking.status,
        order_id=booking.order_id,
        amount=amount_paise,
        currency="INR",
        key_id=_razorpay_key_id(),
    )


@router.post("/events/{event_id}/waitlist", response_model=EventWaitlistJoinResponse)
def join_event_waitlist(
    event_id: str,
    request: EventWaitlistJoinRequest,
    db: Session = Depends(get_db),
):
    seat_stmt = (
        select(EventSeatType)
        .where(EventSeatType.event_id == event_id)
        .where(EventSeatType.seat_type == request.seat_type)
    )
    seat_type = db.execute(seat_stmt).scalar_one_or_none()
    if not seat_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seat type not found",
        )
    if seat_type.available_seats >= request.seat_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seats are available. Please book directly.",
        )

    entry = EventWaitlistEntry(
        event_id=event_id,
        seat_type=request.seat_type,
        seat_count=request.seat_count,
        status="WAITING",
    )
    db.add(entry)
    db.flush()

    position = _waitlist_position(db, entry)
    return EventWaitlistJoinResponse(
        waitlist_id=entry.id,
        status=entry.status,
        position=position,
    )


@router.get("/events/waitlist/{waitlist_id}/page", response_class=HTMLResponse)
def waitlist_status_page(
    waitlist_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    entry = db.execute(
        select(EventWaitlistEntry).where(EventWaitlistEntry.id == waitlist_id)
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Waitlist entry not found",
        )

    position = None
    if entry.status == "WAITING":
        position = _waitlist_position(db, entry)

    event = db.execute(select(Event).where(Event.id == entry.event_id)).scalar_one_or_none()
    return templates.TemplateResponse(
        "waitlist_status.html",
        {
            "request": request,
            "entry": entry,
            "position": position,
            "event": event,
        },
    )


@router.post("/events/waitlist/{waitlist_id}/initiate", response_model=EventBookingResponse)
def initiate_waitlist_payment(
    waitlist_id: str,
    db: Session = Depends(get_db),
):
    entry = db.execute(
        select(EventWaitlistEntry).where(EventWaitlistEntry.id == waitlist_id)
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Waitlist entry not found",
        )
    if entry.status != "READY" or not entry.booking_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Waitlist entry is not ready for payment yet.",
        )

    booking = db.execute(
        select(EventBooking).where(EventBooking.id == entry.booking_id)
    ).scalar_one_or_none()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found for waitlist entry.",
        )

    if not booking.order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order not created for this booking.",
        )

    return EventBookingResponse(
        booking_id=booking.id,
        status=booking.status,
        order_id=booking.order_id,
        amount=booking.amount_paise,
        currency=booking.currency,
        key_id=_razorpay_key_id(),
    )


@router.post("/events/bookings/{booking_id}/verify", response_model=EventBookingResponse)
def verify_event_booking(
    booking_id: str,
    request: RazorpayVerifyRequest,
    db: Session = Depends(get_db),
):
    booking = db.execute(
        select(EventBooking).where(EventBooking.id == booking_id)
    ).scalar_one_or_none()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    if not booking.order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order not created for this booking",
        )

    client = _razorpay_client()
    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": request.razorpay_order_id,
                "razorpay_payment_id": request.razorpay_payment_id,
                "razorpay_signature": request.razorpay_signature,
            }
        )
    except razorpay.errors.SignatureVerificationError as exc:
        booking.status = "FAILED"
        seat_stmt = (
            select(EventSeatType)
            .where(EventSeatType.event_id == booking.event_id)
            .where(EventSeatType.seat_type == booking.seat_type)
            .with_for_update()
        )
        seat_type = db.execute(seat_stmt).scalar_one_or_none()
        if seat_type:
            seat_type.available_seats += booking.seat_count
            _process_waitlist(db, booking.event_id, booking.seat_type)
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment signature",
        ) from exc

    booking.status = "SUCCESS"
    booking.payment_id = request.razorpay_payment_id
    booking.payment_signature = request.razorpay_signature
    return EventBookingResponse(
        booking_id=booking.id,
        status=booking.status,
    )


@router.post("/events/bookings/{booking_id}/cancel", response_model=EventBookingResponse)
def cancel_event_booking(
    booking_id: str,
    db: Session = Depends(get_db),
):
    booking = db.execute(
        select(EventBooking).where(EventBooking.id == booking_id)
    ).scalar_one_or_none()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    if booking.status not in {"PENDING", "SUCCESS"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel booking in status {booking.status}.",
        )

    seat_stmt = (
        select(EventSeatType)
        .where(EventSeatType.event_id == booking.event_id)
        .where(EventSeatType.seat_type == booking.seat_type)
        .with_for_update()
    )
    seat_type = db.execute(seat_stmt).scalar_one_or_none()
    if seat_type:
        seat_type.available_seats += booking.seat_count
        _process_waitlist(db, booking.event_id, booking.seat_type)

    booking.status = "CANCELLED"
    return EventBookingResponse(
        booking_id=booking.id,
        status=booking.status,
    )


@router.get("/restaurants/tables", response_model=list[DiningTableSlotResponse])
def list_table_slots(db: Session = Depends(get_db)):
    stmt = select(DiningTableSlot).order_by(DiningTableSlot.date_time)
    slots = list(db.execute(stmt).scalars().all())
    return [
        DiningTableSlotResponse(
            id=slot.id,
            restaurant_name=slot.restaurant_name,
            table_number=slot.table_number,
            capacity=slot.capacity,
            price_per_table=slot.price_per_table,
            date_time=slot.date_time.isoformat(),
            status=slot.status,
        )
        for slot in slots
    ]


@router.post("/restaurants/tables", response_model=DiningTableSlotResponse)
def create_table_slot(
    request: DiningTableSlotCreate,
    db: Session = Depends(get_db),
):
    try:
        slot_time = datetime.fromisoformat(request.date_time)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date_time format. Use ISO format.",
        ) from exc

    slot = DiningTableSlot(
        restaurant_name=request.restaurant_name,
        table_number=request.table_number,
        capacity=request.capacity,
        price_per_table=request.price_per_table,
        date_time=slot_time,
        status="AVAILABLE",
    )
    db.add(slot)
    db.flush()

    return DiningTableSlotResponse(
        id=slot.id,
        restaurant_name=slot.restaurant_name,
        table_number=slot.table_number,
        capacity=slot.capacity,
        price_per_table=slot.price_per_table,
        date_time=slot.date_time.isoformat(),
        status=slot.status,
    )


@router.post("/restaurants/tables/{slot_id}/book", response_model=DiningTableBookingResponse)
def book_table(
    slot_id: str,
    db: Session = Depends(get_db),
):
    slot_stmt = select(DiningTableSlot).where(DiningTableSlot.id == slot_id).with_for_update()
    slot = db.execute(slot_stmt).scalar_one_or_none()
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table slot not found",
        )
    if slot.status != "AVAILABLE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Table slot not available",
        )

    amount_paise = slot.price_per_table * 100
    slot.status = "HELD"
    booking = DiningTableBooking(
        slot_id=slot.id,
        status="PENDING",
        amount_paise=amount_paise,
        currency="INR",
    )
    db.add(booking)
    db.flush()

    client = _razorpay_client()
    order = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": booking.id,
        }
    )
    booking.order_id = order.get("id")

    return DiningTableBookingResponse(
        booking_id=booking.id,
        status=booking.status,
        order_id=booking.order_id,
        amount=amount_paise,
        currency="INR",
        key_id=_razorpay_key_id(),
    )


@router.post("/restaurants/bookings/{booking_id}/verify", response_model=DiningTableBookingResponse)
def verify_table_booking(
    booking_id: str,
    request: RazorpayVerifyRequest,
    db: Session = Depends(get_db),
):
    booking = db.execute(
        select(DiningTableBooking).where(DiningTableBooking.id == booking_id)
    ).scalar_one_or_none()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    if not booking.order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order not created for this booking",
        )

    client = _razorpay_client()
    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": request.razorpay_order_id,
                "razorpay_payment_id": request.razorpay_payment_id,
                "razorpay_signature": request.razorpay_signature,
            }
        )
    except razorpay.errors.SignatureVerificationError as exc:
        booking.status = "FAILED"
        slot = db.execute(
            select(DiningTableSlot).where(DiningTableSlot.id == booking.slot_id)
        ).scalar_one_or_none()
        if slot:
            slot.status = "AVAILABLE"
        db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment signature",
        ) from exc

    booking.status = "SUCCESS"
    booking.payment_id = request.razorpay_payment_id
    booking.payment_signature = request.razorpay_signature
    slot = db.execute(
        select(DiningTableSlot).where(DiningTableSlot.id == booking.slot_id)
    ).scalar_one_or_none()
    if slot:
        slot.status = "BOOKED"
    return DiningTableBookingResponse(
        booking_id=booking.id,
        status=booking.status,
    )


@router.post("/inventory/seed")
def seed_inventory(
    request: SeedInventoryRequest,
    db: Session = Depends(get_db),
):
    repo = SeatRepository(db)
    inventory = repo.create_or_reset_inventory(
        event_id=request.event_id,
        total_seats=request.total_seats,
    )
    return {
        "event_id": inventory.event_id,
        "total_seats": inventory.total_seats,
        "available_seats": inventory.available_seats,
    }


@router.post("/bookings", response_model=BookingResponse)
def create_booking(
    request: BookingRequest,
    db: Session = Depends(get_db),
):

    service = BookingService(db)

    try:
        booking = service.create_booking(
            user_id=request.user_id,
            event_id=request.event_id,
            seat_count=request.seat_count,
            idempotency_key=request.idempotency_key,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InsufficientInventoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return BookingResponse(
        booking_id=booking.id,
        status=booking.status.value,
    )


@router.post("/bookings/{booking_id}/pay", response_model=BookingResponse)
def pay_booking(
    booking_id: str,
    request: PaymentRequest,
    db: Session = Depends(get_db),
):
    service = BookingService(db)

    try:
        booking = service.confirm_payment(
            booking_id=booking_id,
            result=request.result,
        )
    except InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


    return BookingResponse(
        booking_id=booking.id,
        status=booking.status.value,
    )
