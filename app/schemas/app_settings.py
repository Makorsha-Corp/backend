"""App settings schemas"""
from pydantic import BaseModel, ConfigDict


class AppSettingsBase(BaseModel):
    """Base app settings schema"""
    name: str
    enabled: bool


class AppSettingsCreate(AppSettingsBase):
    """App settings creation schema"""
    pass


class AppSettingsUpdate(BaseModel):
    """App settings update schema"""
    enabled: bool | None = None


class AppSettingsResponse(AppSettingsBase):
    """App settings response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
