"""Locations API: provinces, districts, regions for dropdowns and maps."""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole, Province, District, Region, Camp, RegionalCrop, CropFamily, NationalCrop

router = APIRouter()


@router.get("/provinces", response_model=List[Any])
def list_provinces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List all provinces (id, name) for dropdowns."""
    rows = db.query(Province).order_by(Province.name).all()
    return [{"id": p.id, "name": p.name} for p in rows]


@router.get("/districts", response_model=List[Any])
def list_districts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    province_id: Optional[int] = None,
) -> Any:
    """List districts; optional filter by province_id."""
    query = db.query(District).order_by(District.name)
    if province_id is not None:
        query = query.filter(District.province_id == province_id)
    rows = query.all()
    return [{"id": d.id, "name": d.name, "province_id": d.province_id} for d in rows]


@router.get("/regions", response_model=List[Any])
def list_regions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    province_id: Optional[int] = None,
    district_id: Optional[int] = None,
) -> Any:
    """List regions; optional filter by province_id and/or district_id."""
    query = db.query(Region).order_by(Region.name)
    if province_id is not None:
        query = query.filter(Region.province_id == province_id)
    if district_id is not None:
        query = query.filter(Region.district_id == district_id)
    rows = query.all()
    return [
        {"id": r.id, "name": r.name, "district_id": r.district_id, "province_id": r.province_id}
        for r in rows
    ]


@router.get("/camps", response_model=List[Any])
def list_camps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    region_id: Optional[int] = None,
) -> Any:
    """List camps; optional filter by region_id."""
    query = db.query(Camp).order_by(Camp.name)
    if region_id is not None:
        query = query.filter(Camp.region_id == region_id)
    rows = query.all()
    return [{"id": c.id, "name": c.name, "region_id": c.region_id} for c in rows]


@router.get("/national-crops", response_model=List[Any])
def list_national_crops(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List national crops (id, crop_name, family_name) for survey/report forms."""
    rows = (
        db.query(NationalCrop)
        .options(joinedload(NationalCrop.family))
        .order_by(NationalCrop.crop_name)
        .all()
    )
    return [
        {
            "id": r.id,
            "crop_name": r.crop_name,
            "family_id": r.family_id,
            "family_name": r.family.family_name if r.family else None,
        }
        for r in rows
    ]


@router.get("/regional-crops", response_model=List[Any])
def list_regional_crops(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    region_id: Optional[int] = Query(None),
) -> Any:
    """
    List regional crops, optionally for a specific region.

    IMPORTANT - Agent restriction (spec: "Agent sees only crops for their region"):
    - When current_user is AGENT: region_id is IGNORED; only crops from agent's assigned
      region (current_user.region_id) are returned. If agent has no region_id, returns 403.
    - When current_user is not AGENT: region_id query param is used as filter (optional).
    """
    effective_region_id = region_id

    if current_user.role == UserRole.AGENT:
        if not current_user.region_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent has no region assigned. Contact admin to assign a region.",
            )
        effective_region_id = current_user.region_id

    query = db.query(RegionalCrop).order_by(RegionalCrop.crop_name)
    if effective_region_id is not None:
        query = query.filter(RegionalCrop.region_id == effective_region_id)
    rows = query.all()
    return [
        {
            "id": r.id,
            "crop_name": r.crop_name,
            "family_id": r.family_id,
            "region_id": r.region_id,
            "family_name": r.family.family_name if r.family else None,
        }
        for r in rows
    ]


@router.get("/camp-users", response_model=List[Any])
def list_camp_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    region_id: Optional[int] = Query(None),
) -> Any:
    """
    CampUserTable (spec): list of camp users with CampID, RegionID, ProvinceID, DistrictID, CampName.
    Data from users (role=CAMP) joined with camps. Optionally filter by region_id.
    """
    query = (
        db.query(User, Camp)
        .join(Camp, User.camp_id == Camp.id)
        .filter(User.role == UserRole.CAMP)
        .filter(User.is_deleted == False)
    )
    if region_id is not None:
        query = query.filter(Camp.region_id == region_id)
    rows = query.all()
    return [
        {
            "camp_user_id": u.id,
            "camp_id": c.id,
            "region_id": c.region_id,
            "province_id": c.province_id,
            "district_id": c.district_id,
            "camp_name": c.name,
            "camp_user_name": u.full_name,
        }
        for u, c in rows
    ]
