from collections.abc import Generator
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.integrations.razorpay.gateway import (
    HttpRazorpayGateway,
    RazorpayCredentials,
    RazorpayGateway,
)


def get_razorpay_gateway(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Generator[RazorpayGateway, None, None]:
    gateway = build_razorpay_gateway(settings)
    try:
        yield gateway
    finally:
        gateway.close()


def build_razorpay_gateway(settings: Settings) -> HttpRazorpayGateway:
    return HttpRazorpayGateway(
        RazorpayCredentials(
            key_id=settings.razorpay_key_id,
            key_secret=settings.razorpay_key_secret,
            webhook_secret=settings.razorpay_webhook_secret,
        )
    )
