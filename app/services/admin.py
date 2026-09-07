from sqlalchemy.orm import Session

from app.repositories import admin as admin_repo
from app.schemas.admin import AdminReportResponse, ProductSoldItem


def get_report(db: Session) -> AdminReportResponse:
    stats = admin_repo.get_report_stats(db)
    stats["products_sold"] = [ProductSoldItem(**p) for p in stats["products_sold"]]
    return AdminReportResponse(**stats)
