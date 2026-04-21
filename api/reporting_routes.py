import logging
from enum import Enum
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SQLAlchemySession

from pipeline.models import DataIssue, Event, IssueType

logger = logging.getLogger("town-council-api")

REPORT_ISSUE_RATE_LIMIT = "5/minute"
MEETING_NOT_FOUND_DETAIL = "Meeting not found"
REPORT_SAVE_ERROR_DETAIL = "Internal server error while saving report"
REPORT_SUCCESS_MESSAGE = "Thank you for your report. Our team will review it."


class IssueReport(BaseModel):
    """
    Schema for the data quality report submitted by the user.
    """

    event_id: int = Field(..., description="The ID of the meeting being reported")
    issue_type: str = Field(..., description="The type of problem (e.g., 'broken_link')")
    description: Optional[str] = Field(None, max_length=500, description="Optional details about the issue")


def _valid_issue_type_values(issue_type_enum: type[Enum]) -> list[str]:
    return [issue_type.value for issue_type in issue_type_enum]


def build_reporting_router(
    limiter: Any,
    get_db_dependency: Callable[..., Any],
    verify_api_key_dependency: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()

    @router.post("/report-issue", dependencies=[Depends(verify_api_key_dependency)])
    @limiter.limit(REPORT_ISSUE_RATE_LIMIT)
    def report_data_issue(
        request: Request,
        report: IssueReport,
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, str]:
        """
        Allows users to report errors in the data, such as broken links or OCR errors.
        """
        _ = request
        event = db.query(Event).filter(Event.id == report.event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail=MEETING_NOT_FOUND_DETAIL)

        valid_issue_types = _valid_issue_type_values(IssueType)
        if report.issue_type not in valid_issue_types:
            raise HTTPException(status_code=400, detail=f"Invalid issue_type. Must be one of: {valid_issue_types}")

        try:
            data_issue = DataIssue(
                event_id=report.event_id,
                issue_type=report.issue_type,
                description=report.description,
            )
            db.add(data_issue)
            db.commit()

            logger.info("User reported an issue for event %s: %s", report.event_id, report.issue_type)
            return {"status": "success", "message": REPORT_SUCCESS_MESSAGE}
        except SQLAlchemyError as error:
            db.rollback()
            logger.error("Failed to save data issue: %s", error, exc_info=True)
            raise HTTPException(status_code=500, detail=REPORT_SAVE_ERROR_DETAIL) from error

    return router
