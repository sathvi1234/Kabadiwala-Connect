import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    referral_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    referred_by_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    collector_profile = relationship("CollectorProfile", back_populates="user", uselist=False)
    recycler_profile = relationship("RecyclerProfile", back_populates="user", uselist=False)


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    code: Mapped[str] = mapped_column(String(8))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class CollectorProfile(Base):
    __tablename__ = "collector_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    area: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100), index=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    profile_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    id_proof_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    materials: Mapped[list] = mapped_column(JSON, default=list)
    emergency_contact: Mapped[str | None] = mapped_column(String(20), nullable=True)
    low_data_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    voice_nav_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    image_quality: Mapped[float] = mapped_column(Float, default=0.7)
    user = relationship("User", back_populates="collector_profile")


class RecyclerProfile(Base):
    __tablename__ = "recycler_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    business_name: Mapped[str] = mapped_column(String(200))
    licence_number: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(400))
    city: Mapped[str] = mapped_column(String(100), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    materials: Mapped[list] = mapped_column(JSON, default=list)
    working_hours: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    availability: Mapped[str] = mapped_column(String(20), default="offline")
    next_slot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rating_avg: Mapped[float] = mapped_column(Float, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    reliability_score: Mapped[float] = mapped_column(Float, default=0)
    user = relationship("User", back_populates="recycler_profile")


class RecyclerDocument(Base):
    __tablename__ = "recycler_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recycler_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(50))
    file_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Material(Base):
    __tablename__ = "materials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_hi: Mapped[str] = mapped_column(String(80))
    name_mr: Mapped[str] = mapped_column(String(80))
    co2_factor: Mapped[float] = mapped_column(Float, default=0)
    factor_source: Mapped[str] = mapped_column(String(300), default="")


class PriceFeed(Base):
    __tablename__ = "price_feed"
    __table_args__ = (Index("ix_price_feed_lookup", "material_id", "market", "recorded_on"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"), index=True)
    price_per_kg: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(120))
    market: Mapped[str] = mapped_column(String(100), index=True)
    recorded_on: Mapped[datetime] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    material = relationship("Material")


class Lot(Base):
    __tablename__ = "lots"
    __table_args__ = (Index("ix_lots_collector_created", "collector_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    collector_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"), index=True)
    components: Mapped[list] = mapped_column(JSON, default=list)
    weight_kg: Mapped[float] = mapped_column(Float)
    input_weight: Mapped[float] = mapped_column(Float)
    input_unit: Mapped[str] = mapped_column(String(4), default="kg")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    city: Mapped[str] = mapped_column(String(100), default="")
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    estimated_value: Mapped[float] = mapped_column(Float, default=0)
    price_per_kg: Mapped[float] = mapped_column(Float, default=0)
    price_source: Mapped[str] = mapped_column(String(120), default="")
    price_date: Mapped[str] = mapped_column(String(20), default="")
    price_market: Mapped[str] = mapped_column(String(100), default="")
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_material: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    condition: Mapped[str | None] = mapped_column(String(20), nullable=True)
    condition_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    duplicate_of: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duplicate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duplicate_status: Mapped[str] = mapped_column(String(20), default="none")
    offline_origin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    material = relationship("Material")
    photos = relationship("LotPhoto", cascade="all, delete-orphan")
    events = relationship("LotEvent", cascade="all, delete-orphan")


class LotPhoto(Base):
    __tablename__ = "lot_photos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lots.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="collection")
    path: Mapped[str] = mapped_column(String(500))
    phash: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class LotEvent(Base):
    __tablename__ = "lot_events"
    __table_args__ = (Index("ix_lot_events_lot_created", "lot_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lots.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str] = mapped_column(String(400), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Pickup(Base):
    __tablename__ = "pickups"
    __table_args__ = (Index("ix_pickups_recycler_created", "recycler_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lots.id"), index=True)
    recycler_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    collector_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="requested")
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    lot = relationship("Lot")


class RecyclerOffer(Base):
    __tablename__ = "recycler_offers"
    __table_args__ = (Index("ix_offers_recycler_created", "recycler_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recycler_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    material_id: Mapped[str | None] = mapped_column(ForeignKey("materials.id"), nullable=True)
    lot_id: Mapped[str | None] = mapped_column(ForeignKey("lots.id"), nullable=True, index=True)
    price_per_kg: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Handover(Base):
    __tablename__ = "handovers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lots.id"), unique=True, index=True)
    collector_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recycler_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    weight_verified_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_difference_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)
    certificate_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_collector_created", "collector_id", "created_at"),
        Index("ix_tx_recycler_created", "recycler_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lots.id"), index=True)
    collector_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    recycler_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    lot = relationship("Lot")


class PaymentLine(Base):
    __tablename__ = "payment_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    mode: Mapped[str] = mapped_column(String(20))
    reference: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True)
    receipt_number: Mapped[str] = mapped_column(String(32), unique=True)
    pdf_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (Index("ix_ledger_collector_created", "collector_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    collector_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(10))
    amount: Mapped[float] = mapped_column(Float)
    balance_after: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class RatingFeedback(Base):
    __tablename__ = "ratings_feedback"
    __table_args__ = (UniqueConstraint("lot_id", "collector_id", name="uq_rating_lot_collector"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lots.id"), index=True)
    collector_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    recycler_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    stars: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Dispute(Base):
    __tablename__ = "disputes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lots.id"), index=True)
    raised_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    against_user: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DisputeEvidence(Base):
    __tablename__ = "dispute_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dispute_id: Mapped[str] = mapped_column(ForeignKey("disputes.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    uploaded_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    rule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    message: Mapped[str] = mapped_column(String(400))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class PriceAlertRule(Base):
    __tablename__ = "price_alert_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    collector_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    material_id: Mapped[str | None] = mapped_column(ForeignKey("materials.id"), nullable=True)
    city: Mapped[str] = mapped_column(String(100), default="")
    direction: Mapped[str] = mapped_column(String(20), default="above")
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    auto: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_price_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Badge(Base):
    __tablename__ = "badges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300))
    threshold: Mapped[int] = mapped_column(Integer)


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    badge_id: Mapped[str] = mapped_column(ForeignKey("badges.id"))
    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    badge = relationship("Badge")


class Referral(Base):
    __tablename__ = "referrals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    referrer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    referred_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SyncQueueLog(Base):
    __tablename__ = "sync_queue_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str] = mapped_column(String(400), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(40), default="info")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Tutorial(Base):
    __tablename__ = "tutorials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    feature_key: Mapped[str] = mapped_column(String(40), index=True)
    lang: Mapped[str] = mapped_column(String(5), index=True)
    title: Mapped[str] = mapped_column(String(160))
    script: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CommunityEvent(Base):
    __tablename__ = "community_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(100))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    description: Mapped[str] = mapped_column(String(400), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Testimonial(Base):
    __tablename__ = "testimonials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(40))
    city: Mapped[str] = mapped_column(String(80))
    quote_en: Mapped[str] = mapped_column(String(500))
    quote_hi: Mapped[str] = mapped_column(String(500))
    quote_mr: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
