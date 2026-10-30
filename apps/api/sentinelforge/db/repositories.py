from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import extract, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelforge.db.models import Alert, Case, CaseNumberCounter
from sentinelforge.domains.cases.schemas import AlertInput
from sentinelforge.domains.errors import DomainError, NotFound, VersionConflict


@dataclass(frozen=True)
class ImportedAlert:
    alert: Alert
    created: bool


class Repository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def allocate_display_id(self) -> str:
        year_value = await self.session.scalar(
            select(extract("year", func.timezone("UTC", func.now())))
        )
        assert year_value is not None
        year = int(year_value)
        statement = insert(CaseNumberCounter).values(year=year, last_value=1)
        number = await self.session.scalar(
            statement.on_conflict_do_update(
                index_elements=[CaseNumberCounter.year],
                set_={"last_value": CaseNumberCounter.last_value + 1},
            ).returning(CaseNumberCounter.last_value)
        )
        assert number is not None
        return f"SF-{year:04d}-{number:06d}"

    async def claim_case(self, case_id: UUID, expected_version: int) -> Case:
        if isinstance(expected_version, bool) or expected_version < 1:
            raise DomainError("Expected version must be positive")
        case = await self.session.scalar(
            update(Case)
            .where(Case.id == case_id, Case.version == expected_version)
            .values(version=Case.version + 1, updated_at=func.now())
            .returning(Case)
            .execution_options(populate_existing=True)
        )
        if case is None:
            if await self.session.scalar(select(Case.id).where(Case.id == case_id)) is None:
                raise NotFound("Case not found")
            raise VersionConflict("Case changed; reload before retrying")
        return case

    async def import_alert(self, data: AlertInput, actor_id: UUID) -> ImportedAlert:
        alert = await self.session.scalar(
            insert(Alert)
            .values(**data.model_dump(), imported_by=actor_id)
            .on_conflict_do_nothing(constraint="uq_alert_source")
            .returning(Alert)
        )
        if alert is not None:
            return ImportedAlert(alert, True)
        existing = await self.session.scalar(
            select(Alert).where(
                Alert.provider == data.provider,
                Alert.provider_scope == data.provider_scope,
                Alert.external_alert_id == data.external_alert_id,
            )
        )
        assert existing is not None
        return ImportedAlert(existing, False)
