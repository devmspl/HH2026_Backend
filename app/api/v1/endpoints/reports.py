from typing import Any, List, Optional, Dict, Tuple
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, RoleChecker
from app.db.session import get_db
from app.models.user import User, UserRole, Report, ReportMedia, ReportEditHistory
from app.schemas import general as general_schema
from app.core.audit import log_action
import uuid
import json

router = APIRouter()


def _aggregate_national_crop_reports(
    reports: List[Report], 
    crop_id_map: Optional[Dict[str, str]] = None
) -> Tuple[int, int, int, List[general_schema.NationalCropRow], List[general_schema.NationalCropFamilyPie]]:
    """Aggregate report survey_data (national format) into rows and families. Reused for national/provincial/district/region."""
    total_farmers = 0
    participating_farmers = 0
    spoiled_responses = 0
    crop_agg: Dict[Tuple[str, str], Dict[str, float]] = {}

    for report in reports:
        if not report.survey_data:
            continue
        try:
            data = json.loads(report.survey_data)
        except Exception:
            continue
        total_farmers += int(data.get("total_farmers", 0) or 0)
        participating_farmers += int(data.get("participating_farmers", 0) or 0)
        spoiled_responses += int(data.get("spoiled_responses", 0) or 0)
        for crop in data.get("crops", []):
            crop_id = crop.get("crop_id") or crop.get("id")
            crop_name = str(crop.get("crop_name") or "").strip()
            family_name = str(crop.get("family_name") or "").strip()
            if not crop_name or not family_name:
                continue
            yield_tonnes = float(crop.get("yield_tonnes", 0) or 0)
            
            # If crop_id is missing in JSON, try to look it up in the provided map
            final_crop_id = crop_id
            if not final_crop_id and crop_name and crop_id_map:
                final_crop_id = crop_id_map.get(crop_name)

            key = (crop_name, family_name, final_crop_id)
            if key not in crop_agg:
                crop_agg[key] = {"yield_tonnes": 0.0}
            crop_agg[key]["yield_tonnes"] += yield_tonnes

    active_customers_total = total_farmers
    participating_customers_total = participating_farmers
    rows: List[general_schema.NationalCropRow] = []
    families_map: Dict[str, Dict[str, float]] = {}

    for (crop_name, family_name, crop_id), metrics in crop_agg.items():
        yield_tonnes = metrics["yield_tonnes"]
        percent_participation = (participating_customers_total / active_customers_total * 100.0) if active_customers_total > 0 else None
        percent_active = (active_customers_total / active_customers_total * 100.0) if active_customers_total > 0 else None
        rows.append(
            general_schema.NationalCropRow(
                crop_id=crop_id,
                crop_name=crop_name,
                family_name=family_name,
                yield_tonnes=yield_tonnes,
                active_customers=active_customers_total if active_customers_total > 0 else None,
                participating_customers=participating_customers_total if participating_customers_total > 0 else None,
                percent_participation=percent_participation,
                percent_active=percent_active,
            )
        )
        fam = families_map.setdefault(family_name, {"total_yield_tonnes": 0.0, "total_spoiled_responses": 0.0})
        fam["total_yield_tonnes"] += yield_tonnes
        fam["total_spoiled_responses"] += spoiled_responses

    families: List[general_schema.NationalCropFamilyPie] = []
    for family_name, metrics in families_map.items():
        percent_participation = (participating_customers_total / active_customers_total * 100.0) if active_customers_total > 0 else None
        percent_active = (active_customers_total / active_customers_total * 100.0) if active_customers_total > 0 else None
        families.append(
            general_schema.NationalCropFamilyPie(
                family_name=family_name,
                total_yield_tonnes=metrics["total_yield_tonnes"],
                total_spoiled_responses=int(metrics["total_spoiled_responses"]),
                active_customers=active_customers_total if active_customers_total > 0 else None,
                participating_customers=participating_customers_total if participating_customers_total > 0 else None,
                percent_participation=percent_participation,
                percent_active=percent_active,
            )
        )
    return total_farmers, participating_farmers, spoiled_responses, rows, families


@router.get("/", response_model=List[general_schema.Report])
def read_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    agent_id: Optional[int] = None,
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Any:
    """
    Retrieve reports with search and filter capabilities.
    """
    query = db.query(Report)

    # Search (title, description, confirmation_no)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Report.title.ilike(search_filter)) |
            (Report.description.ilike(search_filter)) |
            (Report.confirmation_no.ilike(search_filter))
        )

    # Filters
    if status and status != "all":
        query = query.filter(Report.status == status)
    
    if agent_id:
        query = query.filter(Report.agent_id == agent_id)

    if start_date:
        query = query.filter(Report.created_at >= start_date)
    if end_date:
        query = query.filter(Report.created_at <= end_date)

    # Visibility constraints
    if current_user.role == UserRole.AGENT:
        query = query.filter(Report.agent_id == current_user.id)
    # For demo, keeping it simple; admins see all matching filters.

    reports = query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()

    # Populate names (manual population because relationship is one-way or to keep it simple)
    # Alternatively, use sqlalchemy joinedload if models had proper relationships defined for names.
    # The models have agent relationship already.
    
    for report in reports:
        if report.agent:
            report.agent_name = report.agent.full_name
            report.agent_role = report.agent.role
            report.agent_email = report.agent.email
            report.agent_phone = report.agent.phone
            report.agent_avatar = report.agent.avatar_url
        
        if report.survey:
            report.survey_name = report.survey.name
        
        for edit in report.edits:
            edit_user = db.query(User).filter(User.id == edit.user_id).first()
            if edit_user:
                edit.user_name = edit_user.full_name

    return reports


@router.get("/crops/national", response_model=general_schema.NationalCropReport)
def get_national_crop_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Aggregate National crop survey data for dashboard tables and charts.

    Expected survey_data format (per Report for NATIONAL surveys):
    {
      "total_farmers": 250,
      "participating_farmers": 200,
      "spoiled_responses": 5,
      "crops": [
        {
          "crop_name": "Maize",
          "family_name": "Cereals",
          "yield_tonnes": 10.5
        },
        ...
      ]
    }
    """
    from app.models.user import Survey

    # Fetch all reports that have survey_data: National + Regional surveys (so admin-created sample reports show in National tab too)
    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(
            (Survey.form_type == "National Crops Survey") | (Survey.form_type == "Regional Crops Survey")
        )
    )
    reports = query.all()

    # Pre-fetch NationalCrop IDs to fill missing ones in JSON
    from app.models.user import NationalCrop
    crops_info = db.query(NationalCrop.crop_name, NationalCrop.id).all()
    id_map = {c.crop_name: str(c.id) for c in crops_info}

    total_farmers, participating_farmers, spoiled_responses, rows, families = _aggregate_national_crop_reports(reports, id_map)
    return general_schema.NationalCropReport(
        total_farmers=total_farmers,
        participating_farmers=participating_farmers,
        spoiled_responses=spoiled_responses,
        rows=rows,
        families=families,
    )


@router.get("/crops/provincial", response_model=general_schema.NationalCropReport)
def get_provincial_crop_report(
    province_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Crop report filtered by Province. Same format as national (Crops | Family | Yield | ACustomers | PCustomers | %)."""
    from app.models.user import Survey
    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(Survey.form_type == "National Crops Survey", Report.province_id == province_id)
    )
    reports = query.all()

    from app.models.user import NationalCrop
    crops_info = db.query(NationalCrop.crop_name, NationalCrop.id).all()
    id_map = {c.crop_name: str(c.id) for c in crops_info}

    total_farmers, participating_farmers, spoiled_responses, rows, families = _aggregate_national_crop_reports(reports, id_map)
    return general_schema.NationalCropReport(
        total_farmers=total_farmers,
        participating_farmers=participating_farmers,
        spoiled_responses=spoiled_responses,
        rows=rows,
        families=families,
    )


@router.get("/crops/district", response_model=general_schema.NationalCropReport)
def get_district_crop_report(
    district_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Crop report filtered by District."""
    from app.models.user import Survey
    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(Survey.form_type == "National Crops Survey", Report.district_id == district_id)
    )
    reports = query.all()

    from app.models.user import NationalCrop
    crops_info = db.query(NationalCrop.crop_name, NationalCrop.id).all()
    id_map = {c.crop_name: str(c.id) for c in crops_info}

    total_farmers, participating_farmers, spoiled_responses, rows, families = _aggregate_national_crop_reports(reports, id_map)
    return general_schema.NationalCropReport(
        total_farmers=total_farmers,
        participating_farmers=participating_farmers,
        spoiled_responses=spoiled_responses,
        rows=rows,
        families=families,
    )


@router.get("/crops/region", response_model=general_schema.NationalCropReport)
def get_region_crop_report(
    region_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Crop report filtered by Region."""
    from app.models.user import Survey
    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(Survey.form_type == "National Crops Survey", Report.region_id == region_id)
    )
    reports = query.all()

    from app.models.user import NationalCrop
    crops_info = db.query(NationalCrop.crop_name, NationalCrop.id).all()
    id_map = {c.crop_name: str(c.id) for c in crops_info}

    total_farmers, participating_farmers, spoiled_responses, rows, families = _aggregate_national_crop_reports(reports, id_map)
    return general_schema.NationalCropReport(
        total_farmers=total_farmers,
        participating_farmers=participating_farmers,
        spoiled_responses=spoiled_responses,
        rows=rows,
        families=families,
    )


@router.get("/crops/regional", response_model=general_schema.RegionalCropTallyReport)
def get_regional_crops_tally(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    region_id: Optional[int] = None,
    district_id: Optional[int] = None,
    province_id: Optional[int] = None,
) -> Any:
    """
    Regional crops tally: RegionalCropName | Family | RegionName | District | Province | Yield | ACustomers | %.
    Uses reports from Regional Crops Survey; optional filter by region_id, district_id, or province_id.
    """
    from app.models.user import Survey, Region, District, Province
    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(Survey.form_type == "Regional Crops Survey")
    )
    if region_id is not None:
        query = query.filter(Report.region_id == region_id)
    if district_id is not None:
        query = query.filter(Report.district_id == district_id)
    if province_id is not None:
        query = query.filter(Report.province_id == province_id)
    reports = query.all()

    total_farmers = 0
    participating_farmers = 0
    spoiled_responses = 0
    # Key: (region_id, crop_name, family_name, crop_id) -> yield + location names
    agg: Dict[Tuple[Optional[int], str, str, Optional[str]], Dict[str, Any]] = {}

    # Pre-fetch RegionalCrop IDs for fallback (Case-insensitive)
    from app.models.user import RegionalCrop, NationalCrop
    id_map = {}
    
    ncrops_info = db.query(NationalCrop.crop_name, NationalCrop.id).all()
    for c in ncrops_info:
        id_map[str(c.crop_name).strip().lower()] = str(c.id)
        
    rcrops_info = db.query(RegionalCrop.crop_name, RegionalCrop.id).all()
    for c in rcrops_info:
        id_map[str(c.crop_name).strip().lower()] = str(c.id)

    for report in reports:
        if not report.survey_data:
            continue
        try:
            data = json.loads(report.survey_data)
        except Exception:
            continue
        total_farmers += int(data.get("total_farmers", 0) or 0)
        participating_farmers += int(data.get("participating_farmers", 0) or 0)
        spoiled_responses += int(data.get("spoiled_responses", 0) or 0)

        region_name = None
        district_name = None
        province_name = None
        if report.region_id:
            r = db.query(Region).filter(Region.id == report.region_id).first()
            if r:
                region_name = r.name
                if r.district_id:
                    d = db.query(District).filter(District.id == r.district_id).first()
                    if d:
                        district_name = d.name
                if r.province_id:
                    p = db.query(Province).filter(Province.id == r.province_id).first()
                    if p:
                        province_name = p.name

        for crop in data.get("crops", []):
            crop_id = crop.get("rcrop_id") or crop.get("id")
            crop_name = str(crop.get("crop_name") or "").strip()
            family_name = str(crop.get("family_name") or "").strip()
            if not crop_name or not family_name:
                continue
            yield_tonnes = float(crop.get("yield_tonnes", 0) or 0)
            
            # Use ID from report or fallback to DB lookup
            final_id = crop_id
            search_name = crop_name.lower()
            if not final_id and search_name in id_map:
                final_id = id_map[search_name]

            key = (report.region_id, crop_name, family_name, final_id)
            if key not in agg:
                agg[key] = {
                    "yield_tonnes": 0.0,
                    "region_name": region_name,
                    "district_name": district_name,
                    "province_name": province_name,
                }
            agg[key]["yield_tonnes"] += yield_tonnes

    active_customers_total = total_farmers
    participating_customers_total = participating_farmers
    percent_participation = (participating_customers_total / active_customers_total * 100.0) if active_customers_total > 0 else None
    percent_active = (active_customers_total / active_customers_total * 100.0) if active_customers_total > 0 else None

    rows: List[general_schema.RegionalCropTallyRow] = []
    for (rid, crop_name, family_name, crop_id), metrics in agg.items():
        rows.append(
            general_schema.RegionalCropTallyRow(
                rcrop_id=crop_id,
                regional_crop_name=crop_name,
                family_name=family_name,
                region_name=metrics.get("region_name"),
                district_name=metrics.get("district_name"),
                province_name=metrics.get("province_name"),
                yield_tonnes=metrics["yield_tonnes"],
                active_customers=active_customers_total if active_customers_total > 0 else None,
                participating_customers=participating_customers_total if participating_customers_total > 0 else None,
                percent_participation=percent_participation,
                percent_active=percent_active,
            )
        )

    return general_schema.RegionalCropTallyReport(
        total_farmers=total_farmers,
        participating_farmers=participating_farmers,
        spoiled_responses=spoiled_responses,
        rows=rows,
    )


@router.get("/crops/dominant-map")
def get_dominant_crop_map(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    For maps: dominant crop family per Province and per Region.
    Returns by_province: [{ province_id, province_name, dominant_family_name }],
    by_region: [{ region_id, region_name, district_name, province_name, dominant_family_name }].
    """
    from app.models.user import Survey, Province, District, Region
    from collections import defaultdict

    # Reports with location + survey_data (National + Regional surveys) for By Province / By Region map
    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(
            (Survey.form_type == "National Crops Survey") | (Survey.form_type == "Regional Crops Survey")
        )
    )
    reports = query.all()

    province_family_yield: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    region_family_yield: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for report in reports:
        if not report.survey_data:
            continue
        try:
            data = json.loads(report.survey_data)
        except Exception:
            continue
        for crop in data.get("crops", []):
            family_name = str(crop.get("family_name") or "").strip()
            if not family_name:
                continue
            yield_tonnes = float(crop.get("yield_tonnes", 0) or 0)
            if report.province_id:
                province_family_yield[report.province_id][family_name] += yield_tonnes
            if report.region_id:
                region_family_yield[report.region_id][family_name] += yield_tonnes

    by_province: List[Dict[str, Any]] = []
    for pid, family_yields in province_family_yield.items():
        if not family_yields:
            continue
        dominant = max(family_yields.items(), key=lambda x: x[1])
        prov = db.query(Province).filter(Province.id == pid).first()
        by_province.append({
            "province_id": pid,
            "province_name": prov.name if prov else f"Province {pid}",
            "dominant_family_name": dominant[0],
            "yield_tonnes": round(dominant[1], 2),
        })
    by_province.sort(key=lambda x: x["province_name"])

    by_region: List[Dict[str, Any]] = []
    for rid, family_yields in region_family_yield.items():
        if not family_yields:
            continue
        dominant = max(family_yields.items(), key=lambda x: x[1])
        reg = db.query(Region).filter(Region.id == rid).first()
        district_name = None
        province_name = None
        if reg:
            if reg.district_id:
                d = db.query(District).filter(District.id == reg.district_id).first()
                if d:
                    district_name = d.name
            if reg.province_id:
                p = db.query(Province).filter(Province.id == reg.province_id).first()
                if p:
                    province_name = p.name
        by_region.append({
            "region_id": rid,
            "region_name": reg.name if reg else f"Region {rid}",
            "district_name": district_name,
            "province_name": province_name,
            "dominant_family_name": dominant[0],
            "yield_tonnes": round(dominant[1], 2),
        })
    by_region.sort(key=lambda x: (x.get("province_name") or "", x.get("region_name") or ""))

    return {"by_province": by_province, "by_region": by_region}


@router.get("/crops/top-family-by-province")
def get_top_family_by_province(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Regional crop graph: Family | number of provinces where it is top rank | Province names.
    Returns list of { family_name, province_count, provinces: [names] }.
    """
    from app.models.user import Survey, Province
    from collections import defaultdict

    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(Survey.form_type == "National Crops Survey")
    )
    reports = query.all()
    province_family_yield: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for report in reports:
        if not report.survey_data or not report.province_id:
            continue
        try:
            data = json.loads(report.survey_data)
        except Exception:
            continue
        for crop in data.get("crops", []):
            family_name = str(crop.get("family_name") or "").strip()
            if not family_name:
                continue
            yield_tonnes = float(crop.get("yield_tonnes", 0) or 0)
            province_family_yield[report.province_id][family_name] += yield_tonnes

    # For each province, find dominant family
    province_dominant: Dict[int, str] = {}
    for pid, family_yields in province_family_yield.items():
        if family_yields:
            province_dominant[pid] = max(family_yields.items(), key=lambda x: x[1])[0]

    # Invert: family_name -> list of provinces where it is dominant
    family_provinces: Dict[str, List[str]] = defaultdict(list)
    for pid, family_name in province_dominant.items():
        prov = db.query(Province).filter(Province.id == pid).first()
        name = prov.name if prov else f"Province {pid}"
        family_provinces[family_name].append(name)

    rows = [
        {"family_name": fam, "province_count": len(provinces), "provinces": sorted(provinces)}
        for fam, provinces in sorted(family_provinces.items(), key=lambda x: -len(x[1]))
    ]
    return {"rows": rows}


@router.post("/", response_model=general_schema.Report)
def create_report(
    *,
    db: Session = Depends(get_db),
    report_in: general_schema.ReportCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create new report (survey submission).

    Business rules:
    - Agents can submit reports only for themselves.
    - Admin/Super Admin can create reports on behalf of any agent (for testing or data entry).
    - If survey targets selected agents, the assigned agent must be in that list.
    """
    from app.models.user import Survey, TargetRespondents
    # Only AGENT role can submit; Admin/Super Admin can create on behalf of any agent
    if current_user.role not in (UserRole.AGENT, UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR, UserRole.EXECUTIVE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agents or admins can create reports",
        )
    survey = db.query(Survey).filter(Survey.id == report_in.survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey.status != "active":
        raise HTTPException(status_code=400, detail="Cannot submit reports for a non-active survey")

    # Agents can only submit for themselves; Admin/Super Admin can set any agent_id
    if current_user.role == UserRole.AGENT and report_in.agent_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agents can only submit reports for themselves",
        )

    # Check survey assignment if TargetRespondents.SELECTED (check the report's agent, not necessarily current_user)
    report_agent_id = report_in.agent_id
    if survey.target_respondents == TargetRespondents.SELECTED.value:
        assigned_user_ids = [u.id for u in survey.target_users]
        if report_agent_id not in assigned_user_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Selected agent is not assigned to this survey",
            )

    # Set report location: from request (admin), else from agent (for Crop Domination Map)
    province_id = getattr(report_in, "province_id", None)
    district_id = getattr(report_in, "district_id", None)
    region_id = getattr(report_in, "region_id", None)
    camp_id = None

    if province_id is None and district_id is None and region_id is None:
        if current_user.role == UserRole.AGENT and current_user.id == report_agent_id:
            province_id = getattr(current_user, "province_id", None)
            district_id = getattr(current_user, "district_id", None)
            region_id = getattr(current_user, "region_id", None)
            camp_id = getattr(current_user, "camp_id", None)
        else:
            agent_user = db.query(User).filter(User.id == report_agent_id).first()
            if agent_user:
                province_id = getattr(agent_user, "province_id", None)
                district_id = getattr(agent_user, "district_id", None)
                region_id = getattr(agent_user, "region_id", None)
                camp_id = getattr(agent_user, "camp_id", None)


    db_obj = Report(
        agent_id=report_in.agent_id,
        survey_id=report_in.survey_id,
        title=report_in.title,
        description=report_in.description,
        gps_lat=report_in.gps_lat,
        gps_lng=report_in.gps_lng,
        confirmation_no=f"CONF-{uuid.uuid4().hex[:8].upper()}",
        status=report_in.status or "pending",
        survey_data=json.dumps(report_in.survey_responses) if report_in.survey_responses else None,
        province_id=province_id,
        district_id=district_id,
        region_id=region_id,
        camp_id=camp_id,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    # Trigger SMS notification for all report submissions
    from app.utils.sms_survey import convert_report_to_sms, send_survey_sms
    
    agent = db.query(User).filter(User.id == report_in.agent_id).first()
    agent_name = agent.full_name if agent else "Unknown Agent"
    
    sms_text = convert_report_to_sms(
        report_in.survey_responses, 
        report_in.title, 
        agent_name
    )
    send_survey_sms(sms_text, db)

    # Process media if provided
    if report_in.media:
        from app.utils.cloudinary import upload_image # Keep name for now or update later
        for media_item in report_in.media:
            file_url = media_item.get("url")
            file_type = media_item.get("type", "image")
            file_name = media_item.get("name")
            
            # If it looks like base64, upload to cloudinary
            if file_url and file_url.startswith("data:"):
                # Pass resource_type auto to handle videos/docs
                uploaded_url = upload_image(file_url) # Cloudinary uploader.upload handles this
                if uploaded_url:
                    file_url = uploaded_url
            
            db_media = ReportMedia(
                report_id=db_obj.id, 
                file_url=file_url,
                file_type=file_type,
                file_name=file_name
            )
            db.add(db_media)
        db.commit()
        db.refresh(db_obj)

    return db_obj

@router.put("/{report_id}", response_model=general_schema.Report)
def update_report(
    *,
    db: Session = Depends(get_db),
    report_id: int,
    report_in: general_schema.ReportUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update a report and track history.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    update_data = report_in.dict(exclude_unset=True)
    
    # Track changes for audit trail
    changes_list = []
    for field, new_value in update_data.items():
        if field == "media":
            continue # Handle media separately
        
        old_value = getattr(report, field)
        if old_value != new_value:
            changes_list.append(f"{field}: {old_value} -> {new_value}")
    
    if changes_list:
        changes_str = "; ".join(changes_list)
        history = ReportEditHistory(
            report_id=report_id,
            user_id=current_user.id,
            changes=changes_str
        )
        db.add(history)
    
    for field in update_data:
        if field == "media" and update_data["media"] is not None:
            # Clear old media and add new one
            from app.models.user import ReportMedia
            db.query(ReportMedia).filter(ReportMedia.report_id == report_id).delete()
            from app.utils.cloudinary import upload_image
            for media_item in update_data["media"]:
                file_url = media_item.get("url")
                file_type = media_item.get("type", "image")
                file_name = media_item.get("name")
                
                if file_url and file_url.startswith("data:"):
                    uploaded_url = upload_image(file_url)
                    if uploaded_url:
                        file_url = uploaded_url
                
                db_media = ReportMedia(
                    report_id=report_id, 
                    file_url=file_url,
                    file_type=file_type,
                    file_name=file_name
                )
                db.add(db_media)
        else:
            setattr(report, field, update_data[field])
    
    db.add(report)
    db.commit()
    db.refresh(report)
    
    log_action(db, current_user.id, "UPDATE_REPORT", f"Updated report {report.confirmation_no}. Changes: {changes_str if 'changes_str' in locals() else 'No data changes'}")
    
    return report

@router.post("/{report_id}/media")
async def upload_report_media(
    *,
    db: Session = Depends(get_db),
    report_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Upload media for a report using Cloudinary.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    from app.utils.cloudinary import upload_file
    
    file_url = upload_file(file.file)
    if not file_url:
        raise HTTPException(status_code=500, detail="Failed to upload file to Cloudinary")
    
    # Detect file type simple
    file_type = "image"
    if file.content_type:
        if "video" in file.content_type: file_type = "video"
        elif "pdf" in file.content_type: file_type = "pdf"
    
    db_media = ReportMedia(
        report_id=report_id, 
        file_url=file_url,
        file_type=file_type,
        file_name=file.filename
    )
    db.add(db_media)
    db.commit()
    db.refresh(db_media)
    
    return {"id": db_media.id, "file_url": db_media.file_url, "file_type": db_media.file_type}

@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a report.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check permissions? Assuming Admin can delete.
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
         raise HTTPException(status_code=403, detail="Not authorized to delete reports")

    conf_no = report.confirmation_no
    db.delete(report)
    db.commit()
    
    log_action(db, current_user.id, "DELETE_REPORT", f"Deleted report {conf_no}")
    
    return {"message": "Report deleted successfully"}
