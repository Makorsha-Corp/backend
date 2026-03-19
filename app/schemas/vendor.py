"""Vendor schemas"""
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict


class VendorBase(BaseModel):
    """Base vendor schema"""
    name: str
    vendor_code: str | None = None
    primary_contact_person: str | None = None
    primary_email: str | None = None
    primary_phone: str | None = None
    secondary_contact_person: str | None = None
    secondary_email: str | None = None
    secondary_phone: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    note: str | None = None


class VendorCreate(VendorBase):
    """Vendor creation schema"""
    created_by: int


class VendorUpdate(BaseModel):
    """Vendor update schema"""
    name: str | None = None
    vendor_code: str | None = None
    primary_contact_person: str | None = None
    primary_email: str | None = None
    primary_phone: str | None = None
    secondary_contact_person: str | None = None
    secondary_email: str | None = None
    secondary_phone: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    note: str | None = None
    is_active: bool | None = None
    updated_by: int | None = None


class VendorSoftDelete(BaseModel):
    """Vendor soft delete schema"""
    deleted_by: int


class VendorResponse(VendorBase):
    """Vendor response schema"""
    id: int
    created_at: datetime
    created_by: int
    updated_at: datetime | None
    updated_by: int | None
    is_active: bool
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: int | None

    model_config = ConfigDict(from_attributes=True)
