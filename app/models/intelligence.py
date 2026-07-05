from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.discovery import CandidateWallet


class WalletReview(Base):
    __tablename__ = "wallet_review"
    __table_args__ = (UniqueConstraint("wallet_id", name="uq_wallet_review_wallet"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("candidate_wallets.id", ondelete="CASCADE"))
    review_status: Mapped[str] = mapped_column(String(32), default="Pending")
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_for_signals: Mapped[bool] = mapped_column(Boolean, default=False)

    wallet: Mapped[CandidateWallet] = relationship()
