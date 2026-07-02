"""Pydantic models for payment extraction."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class PaymentData(BaseModel):
    """Structured payment data extracted from a screenshot."""

    nombre: str = Field(description="Short description of the payment")
    monto: float = Field(description="Payment amount as a number")
    fecha: Optional[date] = Field(default=None, description="Payment date in YYYY-MM-DD format")
    comercio: Optional[str] = Field(default=None, description="Merchant or payee name")
    categoria: Optional[str] = Field(default=None, description="Expense category")
    referencia: Optional[str] = Field(default=None, description="Transaction reference number")
    estado: Optional[str] = Field(default="Exitoso", description="Transaction status")
    notas: Optional[str] = Field(default=None, description="Additional notes or raw extracted text")
