from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import exists, func, select

from sentinelforge.api.identity import Analyst, Session, write_capability
from sentinelforge.api.problems import Problem
from sentinelforge.api.queries import (
    alert_outputs,
    case_output,
    case_outputs,
    require_case,
    search_text,
    severity_order,
)
from sentinelforge.api.schemas import (
    AddEvidence,
    AddNote,
    AlertDetail,
    AlertImport,
    AlertLink,
    AlertPage,
    Assignment,
    CaseMutation,
    CaseOut,
    CasePage,
    CasePatch,
    CreateCase,
    Dashboard,
    EditNote,
    EventOut,
    EventPage,
    EvidenceOut,
    EvidencePage,
    LinkedAlertOut,
    LinkedAlertPage,
    LocalSession,
    NoteOut,
    NotePage,
    SyntheticAlert,
    TransitionCommand,
    Unlink,
    UserOut,
)
from sentinelforge.db.models import Alert, Case, CaseAlert, CaseEvent, CaseNote, Evidence, User
from sentinelforge.domains.cases.schemas import (
    AlertInput,
    CaseDetails,
    EvidenceInput,
    LinkInput,
    NoteInput,
    Transition,
)
from sentinelforge.domains.cases.service import CaseService
from sentinelforge.domains.errors import NotFound
from sentinelforge.domains.types import ActorKind, CaseStatus, Severity

router = APIRouter(
    prefix="/api/v1",
    responses={
        status: {"model": Problem, "description": "Problem details"}
        for status in (400, 403, 404, 409, 413, 422, 503)
    },
)
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100000)]
Search = Annotated[str, Query(max_length=200)]


def service(request: Request, session: Session, analyst: Analyst) -> CaseService:
    return CaseService(session, analyst.id, UUID(request.state.correlation_id))


@router.get("/session", response_model=LocalSession)
async def current_session(request: Request, analyst: Analyst) -> LocalSession:
    return LocalSession(
        actor=UserOut.model_validate(analyst), csrf_token=request.app.state.csrf_token
    )


@router.get("/users", response_model=list[UserOut])
async def users(session: Session, analyst: Analyst) -> list[UserOut]:
    rows = await session.scalars(
        select(User)
        .where(User.is_active.is_(True), User.kind == ActorKind.HUMAN)
        .order_by(User.handle)
        .limit(100)
    )
    return [UserOut.model_validate(row) for row in rows]


@router.get("/dashboard", response_model=Dashboard)
async def dashboard(session: Session, analyst: Analyst) -> Dashboard:
    status_rows = (
        await session.execute(select(Case.status, func.count()).group_by(Case.status))
    ).all()
    statuses = {status: count for status, count in status_rows}
    open_filter = Case.status.not_in([CaseStatus.RESOLVED, CaseStatus.CLOSED])
    severity_rows = (
        await session.execute(
            select(Case.severity, func.count()).where(open_filter).group_by(Case.severity)
        )
    ).all()
    severities = {severity: count for severity, count in severity_rows}
    unassigned = await session.scalar(
        select(func.count()).select_from(Case).where(open_filter, Case.assigned_to.is_(None))
    )
    unlinked = await session.scalar(
        select(func.count())
        .select_from(Alert)
        .where(~exists(select(CaseAlert.id).where(CaseAlert.alert_id == Alert.id)))
    )
    recent = list(
        await session.scalars(select(Case).order_by(Case.updated_at.desc(), Case.id).limit(6))
    )
    return Dashboard(
        open_cases=sum(severities.values()),
        total_cases=sum(statuses.values()),
        unassigned_open_cases=unassigned or 0,
        unlinked_alerts=unlinked or 0,
        severity_counts={key: severities.get(key, 0) for key in Severity},
        status_counts={key: statuses.get(key, 0) for key in CaseStatus},
        recent_cases=await case_outputs(session, recent),
    )


@router.get("/cases", response_model=CasePage)
async def list_cases(
    session: Session,
    analyst: Analyst,
    limit: Limit = 25,
    offset: Offset = 0,
    q: Search = "",
    status: CaseStatus | None = None,
    severity: Severity | None = None,
    owner: UUID | None = None,
    unassigned: bool = False,
    provider: Annotated[str | None, Query(max_length=256)] = None,
    sort: Literal["updated_at", "created_at", "severity"] = "updated_at",
    order: Literal["asc", "desc"] = "desc",
) -> CasePage:
    statement = select(Case)
    if q.strip():
        statement = statement.where(search_text(q, Case.title, Case.display_id, Case.summary))
    if status is not None:
        statement = statement.where(Case.status == status)
    if severity is not None:
        statement = statement.where(Case.severity == severity)
    if owner is not None:
        statement = statement.where(Case.assigned_to == owner)
    if unassigned:
        statement = statement.where(Case.assigned_to.is_(None))
    if provider is not None:
        statement = statement.where(
            exists(
                select(CaseAlert.id)
                .join(Alert, Alert.id == CaseAlert.alert_id)
                .where(CaseAlert.case_id == Case.id, Alert.provider == provider)
            )
        )
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    column = severity_order(Case.severity) if sort == "severity" else getattr(Case, sort)
    rows = list(
        await session.scalars(
            statement.order_by(column.desc() if order == "desc" else column.asc(), Case.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return CasePage(
        items=await case_outputs(session, rows), total=total or 0, limit=limit, offset=offset
    )


@router.post(
    "/cases", response_model=CaseOut, status_code=201, dependencies=[Depends(write_capability)]
)
async def create_case(
    body: CreateCase, request: Request, session: Session, analyst: Analyst
) -> CaseOut:
    commands = service(request, session, analyst)
    case = await commands.create_case(
        CaseDetails.model_validate(body.model_dump(exclude={"alert_id"}))
    )
    if body.alert_id is not None:
        await commands.link_alert(
            case.id, 1, body.alert_id, LinkInput(reason="Case created from selected alert")
        )
    return await case_output(session, case.id)


@router.get("/cases/{case_id}", response_model=CaseOut)
async def get_case(case_id: UUID, session: Session, analyst: Analyst) -> CaseOut:
    return await case_output(session, case_id)


@router.patch("/cases/{case_id}", response_model=CaseOut, dependencies=[Depends(write_capability)])
async def patch_case(
    case_id: UUID, body: CasePatch, request: Request, session: Session, analyst: Analyst
) -> CaseOut:
    current = await require_case(session, case_id)
    details = CaseDetails(
        title=body.title if body.title is not None else current.title,
        summary=body.summary if body.summary is not None else current.summary,
        severity=body.severity if body.severity is not None else current.severity,
    )
    await service(request, session, analyst).update_details(
        case_id, body.expected_version, details, body.reason
    )
    return await case_output(session, case_id)


@router.post(
    "/cases/{case_id}/assignment", response_model=CaseOut, dependencies=[Depends(write_capability)]
)
async def assign_case(
    case_id: UUID, body: Assignment, request: Request, session: Session, analyst: Analyst
) -> CaseOut:
    await service(request, session, analyst).assign(
        case_id, body.expected_version, body.assignee_id, body.reason
    )
    return await case_output(session, case_id)


@router.post(
    "/cases/{case_id}/transitions", response_model=CaseOut, dependencies=[Depends(write_capability)]
)
async def transition_case(
    case_id: UUID, body: TransitionCommand, request: Request, session: Session, analyst: Analyst
) -> CaseOut:
    await service(request, session, analyst).transition(
        case_id,
        body.expected_version,
        Transition.model_validate(body.model_dump(exclude={"expected_version"})),
    )
    return await case_output(session, case_id)


@router.get("/alerts", response_model=AlertPage)
async def list_alerts(
    session: Session,
    analyst: Analyst,
    limit: Limit = 25,
    offset: Offset = 0,
    q: Search = "",
    severity: Severity | None = None,
    provider: Annotated[str | None, Query(max_length=256)] = None,
    linked: bool | None = None,
    sort: Literal["observed_at", "imported_at", "severity"] = "observed_at",
    order: Literal["asc", "desc"] = "desc",
) -> AlertPage:
    statement = select(Alert)
    if q.strip():
        statement = statement.where(
            search_text(q, Alert.title, Alert.external_alert_id, Alert.host, Alert.user_name)
        )
    if severity is not None:
        statement = statement.where(Alert.severity == severity)
    if provider is not None:
        statement = statement.where(Alert.provider == provider)
    if linked is not None:
        link_exists = exists(select(CaseAlert.id).where(CaseAlert.alert_id == Alert.id))
        statement = statement.where(link_exists if linked else ~link_exists)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    column = severity_order(Alert.severity) if sort == "severity" else getattr(Alert, sort)
    rows = list(
        await session.scalars(
            statement.order_by(column.desc() if order == "desc" else column.asc(), Alert.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return AlertPage(
        items=await alert_outputs(session, rows), total=total or 0, limit=limit, offset=offset
    )


@router.post(
    "/alerts",
    response_model=AlertImport,
    responses={201: {"model": AlertImport}},
    dependencies=[Depends(write_capability)],
)
async def import_alert(
    body: SyntheticAlert, response: Response, request: Request, session: Session, analyst: Analyst
) -> AlertImport:
    imported = await service(request, session, analyst).import_alert(
        AlertInput.model_validate(body.model_dump())
    )
    response.status_code = 201 if imported.created else 200
    return AlertImport(
        alert=(await alert_outputs(session, [imported.alert]))[0], created=imported.created
    )


@router.get("/alerts/{alert_id}", response_model=AlertDetail)
async def get_alert(alert_id: UUID, session: Session, analyst: Analyst) -> AlertDetail:
    row = await session.get(Alert, alert_id)
    if row is None:
        raise NotFound("Alert not found")
    output = (await alert_outputs(session, [row]))[0]
    related = list(
        await session.scalars(
            select(Case)
            .join(CaseAlert, CaseAlert.case_id == Case.id)
            .where(CaseAlert.alert_id == alert_id)
            .order_by(Case.updated_at.desc(), Case.id)
            .limit(25)
        )
    )
    return AlertDetail(**output.model_dump(), cases=await case_outputs(session, related))


@router.get("/cases/{case_id}/alerts", response_model=LinkedAlertPage)
async def case_alerts(
    case_id: UUID, session: Session, analyst: Analyst, limit: Limit = 25, offset: Offset = 0
) -> LinkedAlertPage:
    await require_case(session, case_id)
    total = await session.scalar(
        select(func.count()).select_from(CaseAlert).where(CaseAlert.case_id == case_id)
    )
    rows = list(
        (
            await session.execute(
                select(Alert, CaseAlert)
                .join(CaseAlert, CaseAlert.alert_id == Alert.id)
                .where(CaseAlert.case_id == case_id)
                .order_by(CaseAlert.linked_at.desc(), CaseAlert.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    outputs = await alert_outputs(session, [row[0] for row in rows])
    return LinkedAlertPage(
        items=[
            LinkedAlertOut(
                **output.model_dump(),
                link_id=link.id,
                linked_at=link.linked_at,
                linked_by=link.linked_by,
                reason=link.reason,
                method=link.method,
            )
            for output, (_, link) in zip(outputs, rows, strict=True)
        ],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/cases/{case_id}/alerts",
    response_model=CaseMutation,
    status_code=201,
    dependencies=[Depends(write_capability)],
)
async def link_alert(
    case_id: UUID, body: AlertLink, request: Request, session: Session, analyst: Analyst
) -> CaseMutation:
    row = await service(request, session, analyst).link_alert(
        case_id, body.expected_version, body.alert_id, LinkInput(reason=body.reason)
    )
    return CaseMutation(case=await case_output(session, case_id), subject_id=row.id)


@router.delete(
    "/cases/{case_id}/alerts/{alert_id}",
    response_model=CaseMutation,
    dependencies=[Depends(write_capability)],
)
async def unlink_alert(
    case_id: UUID,
    alert_id: UUID,
    body: Unlink,
    request: Request,
    session: Session,
    analyst: Analyst,
) -> CaseMutation:
    await service(request, session, analyst).unlink_alert(
        case_id, body.expected_version, alert_id, body.reason
    )
    return CaseMutation(case=await case_output(session, case_id), subject_id=alert_id)


@router.get("/cases/{case_id}/notes", response_model=NotePage)
async def case_notes(
    case_id: UUID, session: Session, analyst: Analyst, limit: Limit = 25, offset: Offset = 0
) -> NotePage:
    await require_case(session, case_id)
    total = await session.scalar(
        select(func.count()).select_from(CaseNote).where(CaseNote.case_id == case_id)
    )
    rows = await session.execute(
        select(CaseNote, User.handle)
        .join(User, User.id == CaseNote.author_id)
        .where(CaseNote.case_id == case_id)
        .order_by(CaseNote.created_at.desc(), CaseNote.id)
        .limit(limit)
        .offset(offset)
    )
    return NotePage(
        items=[
            NoteOut(
                **{column.name: getattr(row, column.name) for column in CaseNote.__table__.columns},
                author_handle=handle,
            )
            for row, handle in rows
        ],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/cases/{case_id}/notes",
    response_model=CaseMutation,
    status_code=201,
    dependencies=[Depends(write_capability)],
)
async def add_note(
    case_id: UUID, body: AddNote, request: Request, session: Session, analyst: Analyst
) -> CaseMutation:
    row = await service(request, session, analyst).add_note(
        case_id, body.expected_version, NoteInput(body=body.body)
    )
    return CaseMutation(case=await case_output(session, case_id), subject_id=row.id)


@router.patch(
    "/cases/{case_id}/notes/{note_id}",
    response_model=CaseMutation,
    dependencies=[Depends(write_capability)],
)
async def edit_note(
    case_id: UUID,
    note_id: UUID,
    body: EditNote,
    request: Request,
    session: Session,
    analyst: Analyst,
) -> CaseMutation:
    row = await service(request, session, analyst).edit_note(
        case_id, body.expected_version, note_id, NoteInput(body=body.body), body.reason
    )
    return CaseMutation(case=await case_output(session, case_id), subject_id=row.id)


@router.get("/cases/{case_id}/evidence", response_model=EvidencePage)
async def case_evidence(
    case_id: UUID, session: Session, analyst: Analyst, limit: Limit = 25, offset: Offset = 0
) -> EvidencePage:
    await require_case(session, case_id)
    total = await session.scalar(
        select(func.count()).select_from(Evidence).where(Evidence.case_id == case_id)
    )
    rows = await session.execute(
        select(Evidence, User.handle)
        .join(User, User.id == Evidence.acquired_by)
        .where(Evidence.case_id == case_id)
        .order_by(Evidence.acquired_at.desc(), Evidence.id)
        .limit(limit)
        .offset(offset)
    )
    return EvidencePage(
        items=[
            EvidenceOut.model_validate(row).model_copy(update={"acquired_by_handle": handle})
            for row, handle in rows
        ],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/cases/{case_id}/evidence",
    response_model=CaseMutation,
    status_code=201,
    dependencies=[Depends(write_capability)],
)
async def add_evidence(
    case_id: UUID, body: AddEvidence, request: Request, session: Session, analyst: Analyst
) -> CaseMutation:
    row = await service(request, session, analyst).add_evidence(
        case_id,
        body.expected_version,
        EvidenceInput.model_validate(body.model_dump(exclude={"expected_version", "reason"})),
        body.reason,
    )
    return CaseMutation(case=await case_output(session, case_id), subject_id=row.id)


@router.delete(
    "/cases/{case_id}/evidence/{evidence_id}",
    response_model=CaseMutation,
    dependencies=[Depends(write_capability)],
)
async def unlink_evidence(
    case_id: UUID,
    evidence_id: UUID,
    body: Unlink,
    request: Request,
    session: Session,
    analyst: Analyst,
) -> CaseMutation:
    await service(request, session, analyst).unlink_evidence(
        case_id, body.expected_version, evidence_id, body.reason
    )
    return CaseMutation(case=await case_output(session, case_id), subject_id=evidence_id)


@router.get("/cases/{case_id}/timeline", response_model=EventPage)
async def case_timeline(
    case_id: UUID,
    session: Session,
    analyst: Analyst,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Offset = 0,
) -> EventPage:
    await require_case(session, case_id)
    total = await session.scalar(
        select(func.count()).select_from(CaseEvent).where(CaseEvent.case_id == case_id)
    )
    rows = await session.scalars(
        select(CaseEvent)
        .where(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.case_version.desc())
        .limit(limit)
        .offset(offset)
    )
    return EventPage(
        items=[EventOut.model_validate(row) for row in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )
