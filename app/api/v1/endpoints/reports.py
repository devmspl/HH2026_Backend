from typing import Any, List, Optional, Dict, Tuple
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.auth import get_current_user, RoleChecker
from app.db.session import get_db
from app.models.user import User, UserRole, Report, ReportMedia, ReportEditHistory, Province, District, Region, Survey
from app.schemas import general as general_schema
from app.core.audit import log_action
import uuid
import json

router = APIRouter()


def apply_hierarchy_filter(query, current_user: User):
    """Applies scoping filters to queries based on the logged-in user's role and hierarchy assignment."""
    if current_user.is_superuser or current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR, UserRole.EXECUTIVE, UserRole.NATIONAL]:
        return query
    
    if current_user.role == UserRole.PROVINCIAL:
        return query.filter(Report.province_id == current_user.province_id)
    elif current_user.role == UserRole.DISTRICT:
        return query.filter(Report.district_id == current_user.district_id)
    elif current_user.role == UserRole.REGION:
        return query.filter(Report.region_id == current_user.region_id)
    elif current_user.role in [UserRole.CAMP, UserRole.AGENT]:
        return query.filter(Report.agent_id == current_user.id)
    
    return query


def _aggregate_national_crop_reports(
    reports: List[Report], 
    crop_id_map: Optional[Dict[str, str]] = None,
    total_system_farmers: Optional[int] = None
) -> Tuple[int, int, int, List[general_schema.NationalCropRow], List[general_schema.NationalCropFamilyPie]]:
    """Aggregate report survey_data (national format) into rows and families. Reused for national/provincial/district/region."""
    total_report_farmers = 0
    participating_farmers = 0
    spoiled_responses = 0
    crop_agg: Dict[Tuple[str, str, Optional[str]], Dict[str, float]] = {}

    def safe_int(val):
        try:
            if val is None: return 0
            if isinstance(val, (int, float)): return int(val)
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    # Track unique reports per family to avoid double-counting spoiled responses
    family_spoiled_registry: Dict[str, set] = {}

    for report in reports:
        if not report.survey_data:
            continue
        try:
            if isinstance(report.survey_data, str):
                data = json.loads(report.survey_data)
            elif isinstance(report.survey_data, dict):
                data = report.survey_data
            else:
                continue
        except Exception:
            continue
            
        total_report_farmers += safe_int(data.get("total_farmers"))
        p_count = safe_int(data.get("participating_farmers"))
        s_count = safe_int(data.get("spoiled_responses"))
        
        participating_farmers += p_count
        spoiled_responses += s_count

        
        # Robust handling of 'crops' list
        crops = data.get("crops")
        if not isinstance(crops, list):
            continue
            
        for crop in crops:
            if not isinstance(crop, dict):
                continue
            crop_id = crop.get("crop_id") or crop.get("id")
            crop_name = str(crop.get("crop_name") or "").strip()
            family_name = str(crop.get("family_name") or "").strip()
            if not crop_name or not family_name:
                continue
            try:
                yield_tonnes = float(crop.get("yield_tonnes", 0) or 0)
            except (ValueError, TypeError):
                yield_tonnes = 0.0
            
            # Use string ID consistently
            final_crop_id = str(crop_id) if crop_id is not None else None
            if not final_crop_id and crop_name and crop_id_map:
                final_crop_id = crop_id_map.get(crop_name)

            key = (crop_name, family_name, final_crop_id)
            if key not in crop_agg:
                crop_agg[key] = {"yield_tonnes": 0.0, "s_responses": 0}
            
            crop_agg[key]["yield_tonnes"] += yield_tonnes
            
            # Sum spoiled responses once per family per report
            family_spoiled_registry.setdefault(family_name, set())
            if report.id not in family_spoiled_registry[family_name]:
                # We attribute the report's spoiled count to all families present in it
                # but only once per family across multiple crops of that family
                families_in_this_report = set()
                for c in crops:
                    fn = str(c.get("family_name") or "").strip()
                    if fn: families_in_this_report.add(fn)
                
                # Update map
                for fn in families_in_this_report:
                    family_spoiled_registry.setdefault(fn, set())
                    family_spoiled_registry[fn].add(report.id)
                
                # This logic is a bit complex for a single loop. 
                # Let's simplify: crop_agg stores per-crop data. 
                # spoiled_responses is report-level.
                pass 

    # Simplified re-calculation for families to fix the bug
    families_map: Dict[str, Dict[str, float]] = {}
    for report in reports:
        if not report.survey_data: continue
        try:
            data = json.loads(report.survey_data) if isinstance(report.survey_data, str) else report.survey_data
            s_count = safe_int(data.get("spoiled_responses"))
            crops = data.get("crops", [])
            families_in_report = set()
            for c in crops:
                fn = str(c.get("family_name") or "").strip()
                if fn:
                    families_in_report.add(fn)
                    f_entry = families_map.setdefault(fn, {"total_yield_tonnes": 0.0, "total_spoiled_responses": 0.0})
                    # Yield is per crop
                    f_entry["total_yield_tonnes"] += float(c.get("yield_tonnes", 0) or 0)
            
            # Add spoiled responses ONCE per family per report
            for fn in families_in_report:
                families_map[fn]["total_spoiled_responses"] += s_count
        except: continue

    active_customers_total = total_system_farmers if total_system_farmers else total_report_farmers
    participating_customers_total = participating_farmers
    
    rows: List[general_schema.NationalCropRow] = []
    for (crop_name, family_name, crop_id), metrics in crop_agg.items():
        yield_tonnes = metrics["yield_tonnes"]
        
        # Client requested formula: Yield / (Total Participating - Spoiled) * 100
        valid_participants = participating_customers_total - spoiled_responses
        pct_of_p = (yield_tonnes / valid_participants * 100.0) if valid_participants > 0 else 0.0
        
        pct_of_a = (participating_customers_total / active_customers_total * 100.0) if active_customers_total > 0 else 0
        rows.append(general_schema.NationalCropRow(
            crop_id=crop_id, crop_name=crop_name, family_name=family_name, 
            yield_tonnes=yield_tonnes, active_customers=active_customers_total, 
            participating_customers=participating_customers_total,
            percent_of_pcustomers=pct_of_p, percent_of_acustomers=pct_of_a
        ))

    families: List[general_schema.NationalCropFamilyPie] = []
    for family_name, metrics in families_map.items():
        pct_of_p = 100.0 # Placeholder logic for pie
        pct_of_a = (participating_customers_total / active_customers_total * 100.0) if active_customers_total > 0 else 0
        families.append(general_schema.NationalCropFamilyPie(
            family_name=family_name, 
            total_yield_tonnes=metrics["total_yield_tonnes"],
            total_spoiled_responses=int(metrics["total_spoiled_responses"]),
            active_customers=active_customers_total,
            participating_customers=participating_customers_total,
            percent_of_pcustomers=pct_of_p, percent_of_acustomers=pct_of_a
        ))

    return active_customers_total, participating_farmers, spoiled_responses, rows, families



@router.get("/", response_model=general_schema.PaginatedReports)
def read_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    agent_id: Optional[int] = None,
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Any:
    """
    List reports with pagination and filters.
    Retrieve reports with search and filter capabilities.
    """
    skip = (page - 1) * limit
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

    # Hierarchy scoping
    query = apply_hierarchy_filter(query, current_user)

    total = query.count()
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

        if report.survey_data:
            try:
                report.survey_responses = json.loads(report.survey_data)
            except:
                report.survey_responses = {}

        for edit in report.edits:
            edit_user = db.query(User).filter(User.id == edit.user_id).first()
            if edit_user:
                edit.user_name = edit_user.full_name

    return {
        "items": reports,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


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

    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(
            (Survey.form_type == "National Crops Survey") | (Survey.form_type == "Regional Crops Survey"),
            Report.status == "approved"
        )
    )
    query = apply_hierarchy_filter(query, current_user)
    reports = query.all()

    # Pre-fetch crops for ID mapping
    from app.models.user import NationalCrop
    crops_info = db.query(NationalCrop.crop_name, NationalCrop.id).all()
    id_map = {c.crop_name: str(c.id) for c in crops_info}

    # Hierarchy-scoped total system farmers
    from app.models.user import Customer, Province, District, Region
    
    if current_user.is_superuser or current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR, UserRole.EXECUTIVE, UserRole.NATIONAL]:
        total_system_farmers = db.query(func.sum(Province.total_customers)).scalar() or 0
        if not total_system_farmers:
            total_system_farmers = db.query(Customer).count()
    elif current_user.role == UserRole.PROVINCIAL:
        total_system_farmers = db.query(Province.total_customers).filter(Province.id == current_user.province_id).scalar() or 0
    elif current_user.role == UserRole.DISTRICT:
        total_system_farmers = db.query(District.total_customers).filter(District.id == current_user.district_id).scalar() or 0
    elif current_user.role == UserRole.REGION:
        total_system_farmers = db.query(Region.total_customers).filter(Region.id == current_user.region_id).scalar() or 0
    else:
        total_system_farmers = 0

    total_farmers, participating_farmers, spoiled_responses, rows, families = _aggregate_national_crop_reports(
        reports, id_map, total_system_farmers=total_system_farmers
    )
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
    from app.models.user import Survey, Province, NationalCrop
    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(Survey.form_type == "National Crops Survey", Report.province_id == province_id)
    )
    query = apply_hierarchy_filter(query, current_user)
    reports = query.all()

    crops_info = db.query(NationalCrop.crop_name, NationalCrop.id).all()
    id_map = {c.crop_name: str(c.id) for c in crops_info}

    # Provincial system total farmers
    total_system_farmers = db.query(Province.total_customers).filter(Province.id == province_id).scalar() or 0

    total_farmers, participating_farmers, spoiled_responses, rows, families = _aggregate_national_crop_reports(
        reports, id_map, total_system_farmers=total_system_farmers
    )
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
    from app.models.user import Survey, District, NationalCrop
    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(Survey.form_type == "National Crops Survey", Report.district_id == district_id)
    )
    query = apply_hierarchy_filter(query, current_user)
    reports = query.all()

    crops_info = db.query(NationalCrop.crop_name, NationalCrop.id).all()
    id_map = {c.crop_name: str(c.id) for c in crops_info}

    # District system total farmers
    total_system_farmers = db.query(District.total_customers).filter(District.id == district_id).scalar() or 0

    total_farmers, participating_farmers, spoiled_responses, rows, families = _aggregate_national_crop_reports(
        reports, id_map, total_system_farmers=total_system_farmers
    )
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
    from app.models.user import Survey, Region, NationalCrop
    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(Survey.form_type == "National Crops Survey", Report.region_id == region_id)
    )
    query = apply_hierarchy_filter(query, current_user)
    reports = query.all()

    crops_info = db.query(NationalCrop.crop_name, NationalCrop.id).all()
    id_map = {c.crop_name: str(c.id) for c in crops_info}

    # Region system total farmers
    total_system_farmers = db.query(Region.total_customers).filter(Region.id == region_id).scalar() or 0

    total_farmers, participating_farmers, spoiled_responses, rows, families = _aggregate_national_crop_reports(
        reports, id_map, total_system_farmers=total_system_farmers
    )
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
    
    cur_role = str(current_user.role).upper()
    is_admin = current_user.is_superuser or cur_role in ["SUPER_ADMIN", "ADMINISTRATOR"]
    
    # Requirement 1: Scope based on provided filters OR current user's location
    eff_region_id = region_id
    eff_district_id = district_id
    eff_province_id = province_id
    
    # STRICT SCoping for non-admins: They cannot override their own geography
    if not is_admin:
        if current_user.region_id:
            eff_region_id = current_user.region_id
            # Ignore higher level filters if we are anchored to a region
            eff_district_id = None
            eff_province_id = None
        elif current_user.district_id:
            # If district user, they can filter by region within their district, but eff_district_id MUST be theirs
            eff_district_id = current_user.district_id
            eff_province_id = None
        elif current_user.province_id:
            eff_province_id = current_user.province_id
    
    # If no filters provided after scoping, fallback to whatever we have
    if not (eff_region_id or eff_district_id or eff_province_id):
        if current_user.region_id: eff_region_id = current_user.region_id
        elif current_user.district_id: eff_district_id = current_user.district_id
        elif current_user.province_id: eff_province_id = current_user.province_id

    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(
            (Survey.form_type == "National Crops Survey") | (Survey.form_type == "Regional Crops Survey")
        )
    )
    
    if eff_region_id is not None:
        query = query.filter(Report.region_id == eff_region_id)
    if eff_district_id is not None:
        query = query.filter(Report.district_id == eff_district_id)
    if eff_province_id is not None:
        query = query.filter(Report.province_id == eff_province_id)
    
    if str(current_user.role).upper() == "CAMP" and current_user.camp_id:
        query = query.filter(Report.camp_id == current_user.camp_id)
    
    reports = query.all()

    # Calculate system totals based on filtered scope
    total_system_farmers = 0
    if eff_region_id:
        total_system_farmers = db.query(Region.total_customers).filter(Region.id == eff_region_id).scalar() or 0
    elif eff_district_id:
        total_system_farmers = db.query(District.total_customers).filter(District.id == eff_district_id).scalar() or 0
    elif eff_province_id:
        total_system_farmers = db.query(Province.total_customers).filter(Province.id == eff_province_id).scalar() or 0
    else:
        total_system_farmers = db.query(func.sum(Province.total_customers)).scalar() or 0

    if not total_system_farmers:
        from app.models.user import Customer
        c_query = db.query(Customer)
        if eff_region_id: c_query = c_query.filter(Customer.region_id == eff_region_id)
        elif eff_district_id: c_query = c_query.filter(Customer.district_id == eff_district_id)
        elif eff_province_id: c_query = c_query.filter(Customer.province_id == eff_province_id)
        total_system_farmers = c_query.count()

    # 1. Total Camps Count
    from app.models.user import Camp
    if eff_region_id:
        total_camps = db.query(Camp).filter(Camp.region_id == eff_region_id).count()
    elif eff_district_id:
        total_camps = db.query(Camp).filter(Camp.district_id == eff_district_id).count()
    elif eff_province_id:
        total_camps = db.query(Camp).filter(Camp.province_id == eff_province_id).count()
    else:
        total_camps = db.query(Camp).count()

    total_report_farmers = 0
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

    total_yield = 0.0

    def safe_int(val):
        try:
            if val is None: return 0
            if isinstance(val, (int, float)): return int(val)
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    for report in reports:
        if not report.survey_data:
            continue
        try:
            if isinstance(report.survey_data, str):
                data = json.loads(report.survey_data)
            elif isinstance(report.survey_data, dict):
                data = report.survey_data
            else:
                continue
        except Exception:
            continue
        total_report_farmers += safe_int(data.get("total_farmers"))
        participating_farmers += safe_int(data.get("participating_farmers"))
        spoiled_responses += safe_int(data.get("spoiled_responses"))


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

        for crop in (data.get("crops") or []):
            if not isinstance(crop, dict):
                continue
            crop_id = crop.get("rcrop_id") or crop.get("id")
            crop_name = str(crop.get("crop_name") or "").strip()
            family_name = str(crop.get("family_name") or "").strip()
            if not crop_name or not family_name:
                continue
            
            try:
                yield_tonnes = float(crop.get("yield_tonnes", 0) or 0)
            except (ValueError, TypeError):
                yield_tonnes = 0.0
            total_yield += yield_tonnes
            
            # Use ID from report or fallback to DB lookup
            final_id = str(crop_id) if crop_id is not None else None
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


    active_customers_total = int(total_system_farmers) if total_system_farmers else int(total_report_farmers)
    participating_customers_total = int(participating_farmers)
    
    # Percentage against system total (Fallback if needed)
    percent_participation = (participating_customers_total / active_customers_total * 100.0) if active_customers_total > 0 else 0.0

    valid_participants = participating_customers_total - spoiled_responses

    rows: List[general_schema.RegionalCropTallyRow] = []
    for (rid, crop_name, family_name, crop_id), metrics in agg.items():
        # Each row shows the same totals for the filtered area
        rows.append(
            general_schema.RegionalCropTallyRow(
                rcrop_id=crop_id,
                regional_crop_name=crop_name,
                family_name=family_name,
                region_name=metrics.get("region_name"),
                district_name=metrics.get("district_name"),
                province_name=metrics.get("province_name"),
                yield_tonnes=metrics["yield_tonnes"],
                active_customers=active_customers_total if active_customers_total > 0 else 0,
                participating_customers=participating_customers_total if participating_customers_total > 0 else 0,
                percent_of_pcustomers=(metrics["yield_tonnes"] / valid_participants * 100.0) if valid_participants > 0 else 0.0,
                percent_of_acustomers=percent_participation,
            )
        )

    return general_schema.RegionalCropTallyReport(
        active_customers=active_customers_total,
        participating_customers=participating_customers_total,
        spoiled_responses=spoiled_responses,
        total_camps=total_camps,
        total_yield=total_yield,
        total_reports=len(reports),
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

    query = (
        db.query(Report)
        .join(Survey, Report.survey_id == Survey.id)
        .filter(
            (Survey.form_type == "National Crops Survey") | (Survey.form_type == "Regional Crops Survey"),
            Report.status == "approved"
        )
    )
    query = apply_hierarchy_filter(query, current_user)
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
        crops = data.get("crops")
        if not isinstance(crops, list):
            continue
        for crop in crops:
            if not isinstance(crop, dict):
                continue
            family_name = str(crop.get("family_name") or "").strip()
            if not family_name:
                continue
            try:
                yield_tonnes = float(crop.get("yield_tonnes", 0) or 0)
            except (ValueError, TypeError):
                yield_tonnes = 0.0
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
        .filter(
            Survey.form_type == "National Crops Survey",
            Report.status == "approved"
        )
    )
    query = apply_hierarchy_filter(query, current_user)
    reports = query.all()
    province_family_yield: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for report in reports:
        if not report.survey_data or not report.province_id:
            continue
        try:
            data = json.loads(report.survey_data)
        except Exception:
            continue
        crops = data.get("crops")
        if not isinstance(crops, list):
            continue
        for crop in crops:
            if not isinstance(crop, dict):
                continue
            family_name = str(crop.get("family_name") or "").strip()
            if not family_name:
                continue
            try:
                yield_tonnes = float(crop.get("yield_tonnes", 0) or 0)
            except (ValueError, TypeError):
                yield_tonnes = 0.0
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
    # All roles can submit their own reports. 
    # Admins/Super Admins can create reports on behalf of any agent.
    # We remove the restrictive role check here to allow CAMP, REGION, etc. to submit.
    
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
    camp_id = getattr(report_in, "camp_id", None)

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


    # OVERWRITE LOGIC: Same agent + Same survey -> Overwrite previous
    # This ensures "withinPeriod" effectively means "per survey campaign"
    existing_report = db.query(Report).filter(
        Report.agent_id == report_in.agent_id,
        Report.survey_id == report_in.survey_id
    ).first()

    if existing_report:
        existing_report.title = report_in.title
        existing_report.description = report_in.description
        existing_report.gps_lat = report_in.gps_lat
        existing_report.gps_lng = report_in.gps_lng
        existing_report.survey_data = json.dumps(report_in.survey_responses) if report_in.survey_responses else None
        existing_report.status = report_in.status or "pending"
        existing_report.province_id = province_id
        existing_report.district_id = district_id
        existing_report.region_id = region_id
        existing_report.camp_id = camp_id
        # Update timestamp to now for fresh tracking
        existing_report.created_at = datetime.utcnow()
        db.add(existing_report)
        db.commit()
        db.refresh(existing_report)
        return existing_report

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
    
    region_name = "N/A"
    if region_id:
        from app.models.user import Region
        region = db.query(Region).filter(Region.id == region_id).first()
        if region:
            region_name = region.name

    sms_text = convert_report_to_sms(
        report_in.survey_responses, 
        report_in.title, 
        agent_name,
        region_name
    )
    try:
        send_survey_sms(sms_text, db)
    except Exception as e:
        print(f"DEBUG: SMS notification failed (non-blocking): {e}")

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

    # Populate details for the response
    db_obj.agent_name = agent.full_name if agent else "Unknown Agent"
    db_obj.agent_role = agent.role if agent else None
    db_obj.agent_email = agent.email if agent else None
    db_obj.agent_phone = agent.phone if agent else None
    db_obj.agent_avatar = agent.avatar_url if agent else None
    
    if survey:
        db_obj.survey_name = survey.name

    if db_obj.survey_data:
        try:
            db_obj.survey_responses = json.loads(db_obj.survey_data)
        except:
            db_obj.survey_responses = {}

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
    if current_user.role != UserRole.SUPER_ADMIN:
         raise HTTPException(status_code=403, detail="Only Super Admins can delete reports")

    conf_no = report.confirmation_no
    db.delete(report)
    db.commit()
    
    log_action(db, current_user.id, "DELETE_REPORT", f"Deleted report {conf_no}")
    
    
    return {"message": "Report deleted successfully"}



@router.get("/crop-domination/provinces")
def get_crop_domination_provinces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.user import Province
    provinces = db.query(Province).all()
    
    color_map = {
        "Maize": "#F87171",      # Red
        "Wheat": "#60A5FA",      # Blue
        "Rice": "#4ADE80",       # Green
        "Soybeans": "#FBBF24",   # Yellow/Orange
        "Cassava": "#C084FC",    # Purple
        "Sorghum": "#A78BFA",    # Indigo
        "Millet": "#FACC15",     # Yellow
        "Groundnuts": "#D97706", # Brown/Amber
        "Cotton": "#93C5FD",     # Light Blue
        "Tobacco": "#34D399",    # Emerald
        "Sunflower": "#FDE047",  # Yellow
        "Cereals": "#2ecc71",    # Green
        "Legumes": "#3498db",    # Blue
        "Tubers": "#9b59b6",     # Purple
        "Vegetables": "#e74c3c", # Red
        "Fruits": "#f39c12",     # Orange
        "Other": "#95a5a6"       # Gray
    }
    default_color = "rgba(156, 163, 175, 0.4)"    # Transparent Gray for No Data
    
    result = []
    query = db.query(Report).filter(Report.status == "approved")
    query = apply_hierarchy_filter(query, current_user)
    all_approved_reports = query.all()
    
    # Group reports by province
    from collections import defaultdict
    prov_reports = defaultdict(list)
    for r in all_approved_reports:
        if r.province_id:
            prov_reports[r.province_id].append(r)

    result = []
    for prov in provinces:
        reports = prov_reports.get(prov.id, [])
        if not reports: continue
        
        family_yields = {}
        for report in reports:
            if not report.survey_data: continue
            try:
                data = json.loads(report.survey_data)
                for crop in data.get("crops", []):
                    f_name = crop.get("family_name") or "Other"
                    f_yield = float(crop.get("yield_tonnes") or 0)
                    family_yields[f_name] = family_yields.get(f_name, 0) + f_yield
            except: continue
        
        if family_yields:
            top_f = max(family_yields.items(), key=lambda x: x[1])
            dom_fam = top_f[0]
            # Match coloring dynamically based on some common ones or fallback
            color = color_map.get(dom_fam, default_color)
            
            result.append({
                "province_name": prov.name,
                "dominant_crop_family": dom_fam,
                "total_yield": top_f[1],
                "color": color
            })
            
    return result
