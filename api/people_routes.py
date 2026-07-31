import logging
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import and_, false, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Query as SQLAlchemyQuery
from sqlalchemy.orm import Session as SQLAlchemySession, joinedload

from pipeline.models import Membership, Organization, Person, Place
from pipeline.rollout_registry import CITY_METADATA_ALIASES, load_rollout_registry

logger = logging.getLogger("town-council-api")

PEOPLE_DATABASE_ERROR_DETAIL = "Database error"
PERSON_NOT_FOUND_DETAIL = "Official not found"
ROSTER_AUTHORIZATION_ERROR_DETAIL = "Roster authorization unavailable"
DEFAULT_PEOPLE_LIMIT = 50
MAX_PEOPLE_LIMIT = 200


def _authorized_roster_bodies() -> set[tuple[str, str]]:
    authorized_roster_bodies: set[tuple[str, str]] = set()
    for rollout_entry in load_rollout_registry():
        if not rollout_entry.roster_authorized:
            continue
        city_slug = CITY_METADATA_ALIASES.get(rollout_entry.city_slug, rollout_entry.city_slug)
        authorized_roster_bodies.add((city_slug, rollout_entry.roster_body_name))
    return authorized_roster_bodies


def _membership_has_roster_evidence(membership: Membership) -> bool:
    person = membership.person
    organization = membership.organization
    return bool(
        person
        and organization
        and organization.place
        and person.legistar_client
        and person.legistar_person_id is not None
        and person.roster_source_url
        and person.roster_synced_at
        and membership.legistar_client
        and membership.legistar_office_record_id is not None
        and membership.legistar_office_record_guid
        and membership.roster_source_url
        and membership.roster_last_modified_at
        and membership.roster_synced_at
        and membership.start_date
        and organization.legistar_body_id is not None
        and organization.legistar_body_guid
        and organization.roster_source_url
        and organization.roster_synced_at
        and person.legistar_client == membership.legistar_client
        and membership.legistar_client == organization.place.legistar_client
    )


def _authorized_memberships(
    person: Person,
    authorized_roster_bodies: set[tuple[str, str]],
) -> list[Membership]:
    return [
        membership
        for membership in person.memberships
        if _membership_has_roster_evidence(membership)
        and any(
            membership.organization.place.ocd_division_id.endswith(
                f"/place:{city_slug}"
            )
            and membership.organization.name == roster_body_name
            for city_slug, roster_body_name in authorized_roster_bodies
        )
    ]


def _load_authorized_roster_bodies() -> set[tuple[str, str]]:
    try:
        return _authorized_roster_bodies()
    except (OSError, ValueError) as error:
        logger.error("Failed to load roster authorization registry: %s", error, exc_info=True)
        raise HTTPException(status_code=503, detail=ROSTER_AUTHORIZATION_ERROR_DETAIL) from error


def _authorized_people_query(
    db: SQLAlchemySession,
    authorized_roster_bodies: set[tuple[str, str]],
) -> SQLAlchemyQuery[Person]:
    roster_body_filters = [
        Person.memberships.any(
            and_(
                Membership.legistar_client == Person.legistar_client,
                Membership.legistar_office_record_id.is_not(None),
                Membership.legistar_office_record_guid.is_not(None),
                Membership.roster_source_url.is_not(None),
                Membership.roster_last_modified_at.is_not(None),
                Membership.roster_synced_at.is_not(None),
                Membership.start_date.is_not(None),
                Membership.organization.has(
                    and_(
                        Organization.name == roster_body_name,
                        Organization.legistar_body_id.is_not(None),
                        Organization.legistar_body_guid.is_not(None),
                        Organization.roster_source_url.is_not(None),
                        Organization.roster_synced_at.is_not(None),
                        Organization.place.has(
                            and_(
                                Place.ocd_division_id.endswith(
                                    f"/place:{city_slug}",
                                    autoescape=True,
                                ),
                                Place.legistar_client == Person.legistar_client,
                            )
                        ),
                    )
                ),
            )
        )
        for city_slug, roster_body_name in authorized_roster_bodies
    ]
    roster_authorization_filter = (
        or_(*roster_body_filters) if roster_body_filters else false()
    )
    return db.query(Person).filter(
        Person.legistar_client.is_not(None),
        Person.legistar_person_id.is_not(None),
        Person.roster_source_url.is_not(None),
        Person.roster_synced_at.is_not(None),
        roster_authorization_filter,
    )


def build_people_router(get_db_dependency: Callable[..., object]) -> APIRouter:
    router = APIRouter()

    @router.get("/people")
    def list_people(
        limit: int = Query(DEFAULT_PEOPLE_LIMIT, ge=1, le=MAX_PEOPLE_LIMIT),
        offset: int = Query(0, ge=0),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, object]:
        """
        Returns roster-authorized officials.
        """
        authorized_roster_bodies = _load_authorized_roster_bodies()
        try:
            people_query = _authorized_people_query(db, authorized_roster_bodies)
            total = people_query.count()
            people = (
                people_query.order_by(Person.name, Person.id)
                .limit(limit)
                .offset(offset)
                .all()
            )
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "results": [{"id": person.id, "name": person.name} for person in people],
            }
        except SQLAlchemyError as error:
            logger.error("Failed to list people: %s", error, exc_info=True)
            raise HTTPException(status_code=500, detail=PEOPLE_DATABASE_ERROR_DETAIL) from error

    @router.get("/person/{person_id}")
    def get_person_history(
        person_id: int = Path(..., ge=1),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, object]:
        """
        Returns a roster-authorized person's role history.
        """
        authorized_roster_bodies = _load_authorized_roster_bodies()
        person = (
            db.query(Person)
            .options(joinedload(Person.memberships).joinedload(Membership.organization).joinedload(Organization.place))
            .filter(Person.id == person_id)
            .first()
        )

        if not person:
            raise HTTPException(status_code=404, detail=PERSON_NOT_FOUND_DETAIL)

        authorized_memberships = _authorized_memberships(person, authorized_roster_bodies)
        if not authorized_memberships:
            raise HTTPException(status_code=404, detail=PERSON_NOT_FOUND_DETAIL)

        return {
            "name": person.name,
            "roles": [
                {
                    "body": membership.organization.name,
                    "city": membership.organization.place.name.title(),
                    "role": membership.label or "Member",
                    "start_date": membership.start_date.isoformat(),
                    "end_date": membership.end_date.isoformat() if membership.end_date else None,
                }
                for membership in authorized_memberships
            ],
        }

    return router
