import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SQLAlchemySession, joinedload

from pipeline.models import Membership, Organization, Person

logger = logging.getLogger("town-council-api")

PEOPLE_DATABASE_ERROR_DETAIL = "Database error"
PERSON_NOT_FOUND_DETAIL = "Official not found"
DEFAULT_PEOPLE_LIMIT = 50
MAX_PEOPLE_LIMIT = 200


def build_people_router(get_db_dependency: Callable[..., Any]) -> APIRouter:
    router = APIRouter()

    @router.get("/people")
    def list_people(
        limit: int = Query(DEFAULT_PEOPLE_LIMIT, ge=1, le=MAX_PEOPLE_LIMIT),
        offset: int = Query(0, ge=0),
        include_mentions: bool = Query(False, description="Include mention-only names for diagnostics"),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ):
        """
        Returns a paginated list of identified officials.
        """
        try:
            # Mention-only names are available via include_mentions=true for diagnostics.
            people_query = db.query(Person)
            if not include_mentions:
                people_query = people_query.filter(Person.person_type == "official")

            total = people_query.count()
            people = people_query.order_by(Person.name).limit(limit).offset(offset).all()
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "include_mentions": include_mentions,
                "results": people,
            }
        except SQLAlchemyError as error:
            logger.error("Failed to list people: %s", error, exc_info=True)
            raise HTTPException(status_code=500, detail=PEOPLE_DATABASE_ERROR_DETAIL) from error

    @router.get("/person/{person_id}")
    def get_person_history(
        person_id: int = Path(..., ge=1),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ):
        """
        Returns a person's full profile and roles.
        """
        person = (
            db.query(Person)
            .options(joinedload(Person.memberships).joinedload(Membership.organization).joinedload(Organization.place))
            .filter(Person.id == person_id)
            .first()
        )

        if not person:
            raise HTTPException(status_code=404, detail=PERSON_NOT_FOUND_DETAIL)

        role_history = []
        for membership in person.memberships:
            role_history.append(
                {
                    "body": membership.organization.name,
                    "city": membership.organization.place.name.title(),
                    "role": membership.label or "Member",
                }
            )

        return {
            "name": person.name,
            "bio": person.biography,
            "current_role": person.current_role,
            "roles": role_history,
        }

    return router
