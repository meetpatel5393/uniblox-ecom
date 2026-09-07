from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    coupon_every_n_orders: int = 5
    coupon_discount_pct: int = 10
    coupon_min_order_cents: int = 500
    currency: str = "USD"

    class Config:
        env_file = ".env"


settings = Settings()
