"""Additive package contracts. Monetary inputs have at most two decimal places."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TreatmentIn(StrictInput):
    name: str = Field(min_length=2, max_length=120)


class PackageIn(StrictInput):
    patient_id: str
    treatment_id: str
    name: str = Field(min_length=2, max_length=120)
    duration_value: Literal[1, 3, 6, 12, 24]
    duration_unit: Literal["months"] = "months"
    start_date: date
    amount: Decimal = Field(gt=0, le=100000000, decimal_places=2)

    @field_validator("start_date")
    @classmethod
    def supported_date(cls, value):
        if not 1900 <= value.year <= 2100:
            raise ValueError("Start date must be between 1900 and 2100")
        return value


class RenewalIn(StrictInput):
    name: str = Field(min_length=2, max_length=120)
    duration_value: Literal[1, 3, 6, 12, 24]
    start_date: date
    amount: Decimal = Field(gt=0, le=100000000, decimal_places=2)


class PackagePaymentIn(StrictInput):
    amount: Decimal = Field(gt=0, le=100000000, decimal_places=2)
    payment_date: date
    payment_mode: Literal["CASH", "PHONEPE", "CARD", "OTHER"]
    case_id: str | None = None
    reference: str = Field(default="", max_length=200)
    idempotency_key: str = Field(min_length=16, max_length=100)


class ReversalIn(StrictInput):
    reason: str = Field(min_length=5, max_length=500)
    idempotency_key: str = Field(min_length=16, max_length=100)


class PackageLinkIn(StrictInput):
    package_id: str


class PackageVisitIn(StrictInput):
    medicines_taken: bool = True


class PackageFollowupIn(StrictInput):
    scheduled_date: date
    message: str = Field(default="Package follow-up", min_length=1, max_length=1000)


class CompletePackageIn(StrictInput):
    reason: str = Field(min_length=5, max_length=500)


class RecordResponse(BaseModel):
    """All documents are projected without BSON IDs before reaching this envelope."""
    package: dict


class PackageListResponse(BaseModel):
    packages: list[dict]
    total: int
    page: int
    page_size: int
    summary: dict


class TreatmentListResponse(BaseModel):
    treatments: list[dict]