"""Locations API: provinces, districts, regions for dropdowns and maps."""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole, Province, District, Region, Camp, RegionalCrop, CropFamily, NationalCrop, Customer, Report

router = APIRouter()


# ==================== Pydantic Schemas ====================

class CropFamilyCreate(BaseModel):
    family_name: str
    label: Optional[str] = None
    picture: Optional[str] = None

class CropFamilyUpdate(BaseModel):
    family_name: Optional[str] = None
    label: Optional[str] = None
    picture: Optional[str] = None

class NationalCropCreate(BaseModel):
    crop_name: str
    family_id: Optional[int] = None
    picture: Optional[str] = None
    crop_id: Optional[str] = None

class NationalCropUpdate(BaseModel):
    crop_name: Optional[str] = None
    family_id: Optional[int] = None
    picture: Optional[str] = None
    crop_id: Optional[str] = None

class RegionalCropCreate(BaseModel):
    crop_name: str
    region_id: int
    family_id: Optional[int] = None
    picture: Optional[str] = None
    rcrop_id: Optional[str] = None

class RegionalCropUpdate(BaseModel):
    crop_name: Optional[str] = None
    region_id: Optional[int] = None
    family_id: Optional[int] = None
    picture: Optional[str] = None
    rcrop_id: Optional[str] = None


# Province schemas
class ProvinceCreate(BaseModel):
    name: str
    main_crop_family_id: Optional[int] = None

class ProvinceUpdate(BaseModel):
    name: Optional[str] = None
    main_crop_family_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

# District schemas
class DistrictCreate(BaseModel):
    name: str
    province_id: int
    district_type: Optional[str] = None
    main_crop_family_id: Optional[int] = None

class DistrictUpdate(BaseModel):
    name: Optional[str] = None
    province_id: Optional[int] = None
    district_type: Optional[str] = None
    main_crop_family_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

# Region schemas
class RegionCreate(BaseModel):
    name: str
    district_id: int
    province_id: Optional[int] = None
    region_type: Optional[str] = None
    main_crop_family_id: Optional[int] = None

class RegionUpdate(BaseModel):
    name: Optional[str] = None
    district_id: Optional[int] = None
    province_id: Optional[int] = None
    region_type: Optional[str] = None
    main_crop_family_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

# Camp schemas
class CampCreate(BaseModel):
    name: str
    region_id: int
    district_id: Optional[int] = None
    province_id: Optional[int] = None
    camp_type: Optional[str] = None

class CampUpdate(BaseModel):
    name: Optional[str] = None
    region_id: Optional[int] = None
    district_id: Optional[int] = None
    province_id: Optional[int] = None
    camp_type: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

class CampOut(BaseModel):
    id: int
    name: str
    region_id: int
    district_id: Optional[int] = None
    province_id: Optional[int] = None
    camp_type: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    total_customers: int
    model_config = ConfigDict(from_attributes=True)

class PaginatedCamps(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: List[CampOut]
    total: int
    page: int
    limit: int
    pages: int


# ==================== Crop Families CRUD ====================

@router.get("/crop-families", response_model=List[Any])
def list_crop_families(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List all crop families."""
    rows = db.query(CropFamily).order_by(CropFamily.family_name).all()
    return [{"id": f.id, "family_name": f.family_name, "label": f.label, "picture": f.picture} for f in rows]

@router.post("/crop-families", response_model=Any)
def create_crop_family(
    payload: CropFamilyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new crop family. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can create crop families")
    family = CropFamily(
        family_name=payload.family_name,
        label=payload.label,
        picture=payload.picture,
    )
    db.add(family)
    db.commit()
    db.refresh(family)
    return {"id": family.id, "family_name": family.family_name, "label": family.label, "picture": family.picture}

@router.put("/crop-families/{family_id}", response_model=Any)
def update_crop_family(
    family_id: int,
    payload: CropFamilyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update a crop family. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can update crop families")
    family = db.query(CropFamily).filter(CropFamily.id == family_id).first()
    if not family:
        raise HTTPException(status_code=404, detail="Crop family not found")
    if payload.family_name is not None:
        family.family_name = payload.family_name
    if payload.label is not None:
        family.label = payload.label
    if payload.picture is not None:
        family.picture = payload.picture
    db.commit()
    db.refresh(family)
    return {"id": family.id, "family_name": family.family_name, "label": family.label, "picture": family.picture}

@router.delete("/crop-families/{family_id}")
def delete_crop_family(
    family_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Delete a crop family. Admin only."""
    from sqlalchemy.exc import IntegrityError
    
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can delete crop families")
    family = db.query(CropFamily).filter(CropFamily.id == family_id).first()
    if not family:
        raise HTTPException(status_code=404, detail="Crop family not found")
    
    # Check if any national crops are linked to this family
    linked_national = db.query(NationalCrop).filter(NationalCrop.family_id == family_id).count()
    linked_regional = db.query(RegionalCrop).filter(RegionalCrop.family_id == family_id).count()
    linked_provinces = db.query(Province).filter(Province.main_crop_family_id == family_id).count()
    linked_districts = db.query(District).filter(District.main_crop_family_id == family_id).count()
    linked_regions = db.query(Region).filter(Region.main_crop_family_id == family_id).count()
    
    total_linked = linked_national + linked_regional + linked_provinces + linked_districts + linked_regions
    
    if total_linked > 0:
        details = []
        if linked_national > 0:
            details.append(f"{linked_national} national crop(s)")
        if linked_regional > 0:
            details.append(f"{linked_regional} regional crop(s)")
        if linked_provinces > 0:
            details.append(f"{linked_provinces} province(s)")
        if linked_districts > 0:
            details.append(f"{linked_districts} district(s)")
        if linked_regions > 0:
            details.append(f"{linked_regions} region(s)")
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete '{family.family_name}' - linked to: {', '.join(details)}. Remove links first."
        )
    
    try:
        db.delete(family)
        db.commit()
        return {"message": "Crop family deleted"}
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Cannot delete - still has references in database")


# ==================== National Crops CRUD ====================

@router.post("/national-crops", response_model=Any)
def create_national_crop(
    payload: NationalCropCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new national crop. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can create national crops")
    crop = NationalCrop(
        crop_name=payload.crop_name,
        family_id=payload.family_id,
        picture=payload.picture,
        crop_id=payload.crop_id,
    )
    db.add(crop)
    db.commit()
    db.refresh(crop)
    family_name = None
    if crop.family_id:
        family = db.query(CropFamily).filter(CropFamily.id == crop.family_id).first()
        family_name = family.family_name if family else None
    return {"id": crop.id, "crop_name": crop.crop_name, "family_id": crop.family_id, "family_name": family_name, "picture": crop.picture, "crop_id": crop.crop_id}

@router.put("/national-crops/{crop_id}", response_model=Any)
def update_national_crop(
    crop_id: int,
    payload: NationalCropUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update a national crop. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can update national crops")
    crop = db.query(NationalCrop).filter(NationalCrop.id == crop_id).first()
    if not crop:
        raise HTTPException(status_code=404, detail="National crop not found")
    if payload.crop_name is not None:
        crop.crop_name = payload.crop_name
    if payload.family_id is not None:
        crop.family_id = payload.family_id
    if payload.picture is not None:
        crop.picture = payload.picture
    if payload.crop_id is not None:
        crop.crop_id = payload.crop_id
    db.commit()
    db.refresh(crop)
    family_name = None
    if crop.family_id:
        family = db.query(CropFamily).filter(CropFamily.id == crop.family_id).first()
        family_name = family.family_name if family else None
    return {"id": crop.id, "crop_name": crop.crop_name, "family_id": crop.family_id, "family_name": family_name, "picture": crop.picture, "crop_id": crop.crop_id}

@router.delete("/national-crops/{crop_id}")
def delete_national_crop(
    crop_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Delete a national crop. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can delete national crops")
    crop = db.query(NationalCrop).filter(NationalCrop.id == crop_id).first()
    if not crop:
        raise HTTPException(status_code=404, detail="National crop not found")
    db.delete(crop)
    db.commit()
    return {"message": "National crop deleted"}


@router.get("/provinces", response_model=List[Any])
def list_provinces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
) -> Any:
    """List all provinces (id, name, total_customers, main_crop_family_name) for dropdowns and management."""
    cur_role = str(current_user.role).upper()
    is_admin = current_user.is_superuser or cur_role in ["SUPER_ADMIN", "ADMINISTRATOR", "EXECUTIVE", "NATIONAL", "SUPERADMIN"]
    query = db.query(Province).options(joinedload(Province.main_crop_family))
    
    if not is_admin:
        if current_user.province_id:
            query = query.filter(Province.id == current_user.province_id)
            
    # Sorting
    if sort_by == "ProvinceID":
        query = query.order_by(Province.id.desc() if sort_order == "desc" else Province.id.asc())
    elif sort_by == "Province":
        query = query.order_by(Province.name.desc() if sort_order == "desc" else Province.name.asc())
    elif sort_by == "maincropFamily":
        from app.models.user import CropFamily
        query = query.outerjoin(Province.main_crop_family)
        query = query.order_by(CropFamily.family_name.desc() if sort_order == "desc" else CropFamily.family_name.asc())
    elif sort_by == "Customers":
        customer_count_subquery = db.query(
            Customer.province_id,
            func.count(Customer.id).label("c_count")
        ).group_by(Customer.province_id).subquery()
        query = query.outerjoin(customer_count_subquery, Province.id == customer_count_subquery.c.province_id)
        query = query.order_by(customer_count_subquery.c.c_count.desc() if sort_order == "desc" else customer_count_subquery.c.c_count.asc())
    else:
        query = query.order_by(Province.name)

    rows = query.all()
    result = []
    for p in rows:
        count = db.query(Customer).filter(Customer.province_id == p.id).count()
        result.append({
            "id": p.id, 
            "name": p.name, 
            "total_customers": count,
            "main_crop_family_id": p.main_crop_family_id,
            "main_crop_family_name": p.main_crop_family.family_name if p.main_crop_family else None
        })
    return result


@router.get("/districts", response_model=List[Any])
def list_districts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    province_id: Optional[int] = None,
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
) -> Any:
    """List districts; optional filter by province_id. Returns customer counts and main crop family."""
    cur_role = str(current_user.role).upper()
    is_admin = current_user.is_superuser or cur_role in ["SUPER_ADMIN", "ADMINISTRATOR", "EXECUTIVE", "NATIONAL", "SUPERADMIN"]
    query = db.query(District).options(joinedload(District.main_crop_family))
    if province_id is not None:
        query = query.filter(District.province_id == province_id)
    
    if not is_admin:
        if current_user.district_id:
            query = query.filter(District.id == current_user.district_id)
        elif current_user.province_id:
            query = query.filter(District.province_id == current_user.province_id)

    # Sorting
    if sort_by == "DistrictID":
        query = query.order_by(District.id.desc() if sort_order == "desc" else District.id.asc())
    elif sort_by == "District":
        query = query.order_by(District.name.desc() if sort_order == "desc" else District.name.asc())
    elif sort_by == "ProvinceID":
        query = query.order_by(District.province_id.desc() if sort_order == "desc" else District.province_id.asc())
    elif sort_by == "Type":
        query = query.order_by(District.district_type.desc() if sort_order == "desc" else District.district_type.asc())
    elif sort_by == "maincropFamily":
        from app.models.user import CropFamily
        query = query.outerjoin(District.main_crop_family)
        query = query.order_by(CropFamily.family_name.desc() if sort_order == "desc" else CropFamily.family_name.asc())
    elif sort_by == "Customers":
        customer_count_subquery = db.query(
            Customer.district_id,
            func.count(Customer.id).label("c_count")
        ).group_by(Customer.district_id).subquery()
        query = query.outerjoin(customer_count_subquery, District.id == customer_count_subquery.c.district_id)
        query = query.order_by(customer_count_subquery.c.c_count.desc() if sort_order == "desc" else customer_count_subquery.c.c_count.asc())
    else:
        query = query.order_by(District.name)

    rows = query.all()
    
    # Optimize customer count query
    counts = db.query(Customer.district_id, func.count(Customer.id)).group_by(Customer.district_id).all()
    counts_dict = {district_id: count for district_id, count in counts if district_id}
    
    result = []
    for d in rows:
        count = counts_dict.get(d.id, 0)
        result.append({
            "id": d.id, 
            "name": d.name, 
            "province_id": d.province_id,
            "total_customers": count,
            "district_type": d.district_type,
            "main_crop_family_id": d.main_crop_family_id,
            "main_crop_family_name": d.main_crop_family.family_name if d.main_crop_family else None
        })
    return result


@router.get("/regions", response_model=List[Any])
def list_regions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    province_id: Optional[int] = None,
    district_id: Optional[int] = None,
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
) -> Any:
    """List regions; optional filter by province_id and/or district_id."""
    cur_role = str(current_user.role).upper()
    query = db.query(Region).options(joinedload(Region.main_crop_family))
    if province_id is not None:
        query = query.filter(Region.province_id == province_id)
    if district_id is not None:
        query = query.filter(Region.district_id == district_id)

    if cur_role not in ["SUPER_ADMIN", "ADMINISTRATOR", "EXECUTIVE", "NATIONAL"]:
        if current_user.region_id:
            query = query.filter(Region.id == current_user.region_id)
        elif current_user.district_id:
            query = query.filter(Region.district_id == current_user.district_id)

    # Sorting
    if sort_by == "regionID":
        query = query.order_by(Region.id.desc() if sort_order == "desc" else Region.id.asc())
    elif sort_by == "Region":
        query = query.order_by(Region.name.desc() if sort_order == "desc" else Region.name.asc())
    elif sort_by == "DistrictID":
        query = query.order_by(Region.district_id.desc() if sort_order == "desc" else Region.district_id.asc())
    elif sort_by == "ProvinceID":
        query = query.order_by(Region.province_id.desc() if sort_order == "desc" else Region.province_id.asc())
    elif sort_by == "Type":
        query = query.order_by(Region.region_type.desc() if sort_order == "desc" else Region.region_type.asc())
    elif sort_by == "maincropFamily":
        from app.models.user import CropFamily
        query = query.outerjoin(Region.main_crop_family)
        query = query.order_by(CropFamily.family_name.desc() if sort_order == "desc" else CropFamily.family_name.asc())
    elif sort_by == "Customers":
        customer_count_subquery = db.query(
            Customer.region_id,
            func.count(Customer.id).label("c_count")
        ).group_by(Customer.region_id).subquery()
        query = query.outerjoin(customer_count_subquery, Region.id == customer_count_subquery.c.region_id)
        query = query.order_by(customer_count_subquery.c.c_count.desc() if sort_order == "desc" else customer_count_subquery.c.c_count.asc())
    else:
        query = query.order_by(Region.name)

    rows = query.all()
    
    # Optimize customer count query
    counts = db.query(Customer.region_id, func.count(Customer.id)).group_by(Customer.region_id).all()
    counts_dict = {region_id: count for region_id, count in counts if region_id}
    
    result = []
    for r in rows:
        count = counts_dict.get(r.id, 0)
        result.append({
            "id": r.id, 
            "name": r.name, 
            "district_id": r.district_id, 
            "province_id": r.province_id,
            "total_customers": count,
            "region_type": r.region_type,
            "main_crop_family_id": r.main_crop_family_id,
            "main_crop_family_name": r.main_crop_family.family_name if r.main_crop_family else None
        })
    return result


@router.get("/camps", response_model=PaginatedCamps)
def list_camps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    region_id: Optional[int] = None,
    district_id: Optional[int] = None,
    province_id: Optional[int] = None,
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=10000),
) -> Any:
    """List camps; optional filter by region_id, district_id, province_id with pagination and sorting."""
    skip = (page - 1) * limit
    cur_role = str(current_user.role).upper()
    query = db.query(Camp)
    if region_id is not None:
        query = query.filter(Camp.region_id == region_id)
    if district_id is not None:
        query = query.filter(Camp.district_id == district_id)
    if province_id is not None:
        query = query.filter(Camp.province_id == province_id)

    if cur_role not in ["SUPER_ADMIN", "ADMINISTRATOR", "EXECUTIVE", "NATIONAL"]:
        if current_user.camp_id:
            query = query.filter(Camp.id == current_user.camp_id)
        elif current_user.region_id:
            query = query.filter(Camp.region_id == current_user.region_id)

    # Sorting
    if sort_by == "CampID":
        query = query.order_by(Camp.id.desc() if sort_order == "desc" else Camp.id.asc())
    elif sort_by == "CampName":
        query = query.order_by(Camp.name.desc() if sort_order == "desc" else Camp.name.asc())
    elif sort_by == "RegionID":
        query = query.order_by(Camp.region_id.desc() if sort_order == "desc" else Camp.region_id.asc())
    elif sort_by == "ProvinceID":
        query = query.order_by(Camp.province_id.desc() if sort_order == "desc" else Camp.province_id.asc())
    elif sort_by == "DistrictID":
        query = query.order_by(Camp.district_id.desc() if sort_order == "desc" else Camp.district_id.asc())
    elif sort_by == "CampLType":
        query = query.order_by(Camp.camp_type.desc() if sort_order == "desc" else Camp.camp_type.asc())
    elif sort_by == "Customers":
        customer_count_subquery = db.query(
            Customer.camp_id,
            func.count(Customer.id).label("c_count")
        ).group_by(Customer.camp_id).subquery()
        query = query.outerjoin(customer_count_subquery, Camp.id == customer_count_subquery.c.camp_id)
        query = query.order_by(customer_count_subquery.c.c_count.desc() if sort_order == "desc" else customer_count_subquery.c.c_count.asc())
    else:
        query = query.order_by(Camp.name)

    total = query.count()
    rows = query.offset(skip).limit(limit).all()
    # Optimize customer count query
    counts = db.query(Customer.camp_id, func.count(Customer.id)).group_by(Customer.camp_id).all()
    counts_dict = {camp_id: count for camp_id, count in counts if camp_id}
    
    result = []
    for c in rows:
        count = counts_dict.get(c.id, 0)
        result.append({
            "id": c.id, 
            "name": c.name, 
            "region_id": c.region_id,
            "province_id": c.province_id,
            "district_id": c.district_id,
            "total_customers": count,
            "camp_type": c.camp_type
        })
    return {
        "items": result,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.get("/national-crops", response_model=List[Any])
def list_national_crops(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
    family_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
) -> Any:
    """List national crops with sorting and filtering."""
    query = db.query(NationalCrop).options(joinedload(NationalCrop.family))
    
    if family_id is not None:
        query = query.filter(NationalCrop.family_id == family_id)
    if status:
        query = query.filter(func.lower(NationalCrop.status) == status.lower())
        
    rows = query.all()
    
    # Serialize
    result = [
        {
            "id": r.id,
            "crop_name": r.crop_name,
            "crop_id": r.crop_id,
            "family_id": r.family_id,
            "family_name": r.family.family_name if r.family else None,
            "picture": r.picture,
            "status": r.status or "active",
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    
    # Sort in memory
    if sort_by:
        reverse = (sort_order == "desc")
        if sort_by == "CropID":
            result.sort(key=lambda x: x["id"], reverse=reverse)
        elif sort_by == "CropName":
            result.sort(key=lambda x: (x["crop_name"] or "").lower(), reverse=reverse)
        elif sort_by == "Family":
            result.sort(key=lambda x: (x["family_name"] or "").lower(), reverse=reverse)
        elif sort_by == "Status":
            result.sort(key=lambda x: (x["status"] or "").lower(), reverse=reverse)
        elif sort_by == "CreatedAt":
            result.sort(key=lambda x: x["created_at"] or "", reverse=reverse)
        elif sort_by == "UpdatedAt":
            result.sort(key=lambda x: x["updated_at"] or "", reverse=reverse)
    else:
        # Default order
        result.sort(key=lambda x: (x["crop_name"] or "").lower())
        
    return result


@router.get("/regional-crops", response_model=List[Any])
def list_regional_crops(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    region_id: Optional[int] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
    family_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
) -> Any:
    """
    List regional crops, optionally for a specific region.
    """
    effective_region_id = region_id

    if current_user.role == UserRole.AGENT:
        if not current_user.region_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent has no region assigned. Contact admin to assign a region.",
            )
        effective_region_id = current_user.region_id

    query = db.query(RegionalCrop).options(joinedload(RegionalCrop.family))
    if effective_region_id is not None:
        query = query.filter(RegionalCrop.region_id == effective_region_id)
    if family_id is not None:
        query = query.filter(RegionalCrop.family_id == family_id)
    if status:
        query = query.filter(func.lower(RegionalCrop.status) == status.lower())
        
    rows = query.all()
    
    # Serialize
    result = [
        {
            "id": r.id,
            "crop_name": r.crop_name,
            "family_id": r.family_id,
            "region_id": r.region_id,
            "family_name": r.family.family_name if r.family else None,
            "picture": r.picture,
            "rcrop_id": r.rcrop_id,
            "status": r.status or "active",
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    
    # Sort in memory
    if sort_by:
        reverse = (sort_order == "desc")
        if sort_by == "CropID":
            result.sort(key=lambda x: x["id"], reverse=reverse)
        elif sort_by == "CropName":
            result.sort(key=lambda x: (x["crop_name"] or "").lower(), reverse=reverse)
        elif sort_by == "Family":
            result.sort(key=lambda x: (x["family_name"] or "").lower(), reverse=reverse)
        elif sort_by == "Status":
            result.sort(key=lambda x: (x["status"] or "").lower(), reverse=reverse)
        elif sort_by == "CreatedAt":
            result.sort(key=lambda x: x["created_at"] or "", reverse=reverse)
        elif sort_by == "UpdatedAt":
            result.sort(key=lambda x: x["updated_at"] or "", reverse=reverse)
    else:
        # Default order
        result.sort(key=lambda x: (x["crop_name"] or "").lower())
        
    return result

@router.post("/regional-crops", response_model=Any)
def create_regional_crop(
    payload: RegionalCropCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new regional crop. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can create regional crops")
    crop = RegionalCrop(
        crop_name=payload.crop_name,
        region_id=payload.region_id,
        family_id=payload.family_id,
        picture=payload.picture,
        rcrop_id=payload.rcrop_id,
    )
    db.add(crop)
    db.commit()
    db.refresh(crop)
    return {
        "id": crop.id, 
        "crop_name": crop.crop_name, 
        "region_id": crop.region_id, 
        "family_id": crop.family_id,
        "family_name": crop.family.family_name if crop.family else None,
        "picture": crop.picture
    }

@router.put("/regional-crops/{crop_id}", response_model=Any)
def update_regional_crop(
    crop_id: int,
    payload: RegionalCropUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update a regional crop. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can update regional crops")
    crop = db.query(RegionalCrop).filter(RegionalCrop.id == crop_id).first()
    if not crop:
        raise HTTPException(status_code=404, detail="Regional crop not found")
    if payload.crop_name is not None:
        crop.crop_name = payload.crop_name
    if payload.region_id is not None:
        crop.region_id = payload.region_id
    if payload.family_id is not None:
        crop.family_id = payload.family_id
    if payload.picture is not None:
        crop.picture = payload.picture
    if payload.rcrop_id is not None:
        crop.rcrop_id = payload.rcrop_id
    db.commit()
    db.refresh(crop)
    return {
        "id": crop.id, 
        "crop_name": crop.crop_name, 
        "region_id": crop.region_id, 
        "family_id": crop.family_id,
        "family_name": crop.family.family_name if crop.family else None,
        "picture": crop.picture
    }

@router.delete("/regional-crops/{crop_id}")
def delete_regional_crop(
    crop_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Delete a regional crop. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can delete regional crops")
    crop = db.query(RegionalCrop).filter(RegionalCrop.id == crop_id).first()
    if not crop:
        raise HTTPException(status_code=404, detail="Regional crop not found")
    db.delete(crop)
    db.commit()
    return {"message": "Regional crop deleted"}


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
    cur_role = str(current_user.role).upper()
    query = (
        db.query(User, Camp)
        .join(Camp, User.camp_id == Camp.id)
        .filter(User.role == UserRole.CAMP)
        .filter(User.is_deleted == False)
    )
    
    # Apply Scoping
    if cur_role not in ["SUPER_ADMIN", "ADMINISTRATOR", "EXECUTIVE", "NATIONAL"]:
        if current_user.region_id:
            query = query.filter(Camp.region_id == current_user.region_id)
        elif current_user.district_id:
            query = query.filter(Camp.district_id == current_user.district_id)
        elif current_user.province_id:
            query = query.filter(Camp.province_id == current_user.province_id)
    
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


# ==================== Province CRUD ====================

@router.post("/provinces", response_model=Any)
def create_province(
    payload: ProvinceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new province. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can create provinces")
    province = Province(
        name=payload.name,
        main_crop_family_id=payload.main_crop_family_id,
    )
    db.add(province)
    db.commit()
    db.refresh(province)
    return {"id": province.id, "name": province.name, "main_crop_family_id": province.main_crop_family_id}

@router.put("/provinces/{province_id}", response_model=Any)
def update_province(
    province_id: int,
    payload: ProvinceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update a province. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can update provinces")
    province = db.query(Province).filter(Province.id == province_id).first()
    if not province:
        raise HTTPException(status_code=404, detail="Province not found")
    if payload.name is not None:
        province.name = payload.name
    if payload.main_crop_family_id is not None:
        province.main_crop_family_id = payload.main_crop_family_id
    if payload.lat is not None:
        province.lat = payload.lat
    if payload.lng is not None:
        province.lng = payload.lng
    db.commit()
    db.refresh(province)
    return {"id": province.id, "name": province.name, "main_crop_family_id": province.main_crop_family_id}

@router.delete("/provinces/{province_id}")
def delete_province(
    province_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Delete a province. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can delete provinces")
    province = db.query(Province).filter(Province.id == province_id).first()
    if not province:
        raise HTTPException(status_code=404, detail="Province not found")
    # Check linked districts
    linked = db.query(District).filter(District.province_id == province_id).count()
    if linked > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete - {linked} district(s) linked to this province")
    db.delete(province)
    db.commit()
    return {"message": "Province deleted"}


# ==================== District CRUD ====================

@router.post("/districts", response_model=Any)
def create_district(
    payload: DistrictCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new district. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can create districts")
    district = District(
        name=payload.name,
        province_id=payload.province_id,
        district_type=payload.district_type,
        main_crop_family_id=payload.main_crop_family_id,
    )
    db.add(district)
    db.commit()
    db.refresh(district)
    return {"id": district.id, "name": district.name, "province_id": district.province_id, "district_type": district.district_type, "main_crop_family_id": district.main_crop_family_id}

@router.put("/districts/{district_id}", response_model=Any)
def update_district(
    district_id: int,
    payload: DistrictUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update a district. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can update districts")
    district = db.query(District).filter(District.id == district_id).first()
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    if payload.name is not None:
        district.name = payload.name
    if payload.province_id is not None:
        district.province_id = payload.province_id
    if payload.district_type is not None:
        district.district_type = payload.district_type
    if payload.main_crop_family_id is not None:
        district.main_crop_family_id = payload.main_crop_family_id
    if payload.lat is not None:
        district.lat = payload.lat
    if payload.lng is not None:
        district.lng = payload.lng
    db.commit()
    db.refresh(district)
    return {"id": district.id, "name": district.name, "province_id": district.province_id, "district_type": district.district_type, "main_crop_family_id": district.main_crop_family_id}

@router.delete("/districts/{district_id}")
def delete_district(
    district_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Delete a district. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can delete districts")
    district = db.query(District).filter(District.id == district_id).first()
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    # Check linked regions
    linked = db.query(Region).filter(Region.district_id == district_id).count()
    if linked > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete - {linked} region(s) linked to this district")
    db.delete(district)
    db.commit()
    return {"message": "District deleted"}


# ==================== Region CRUD ====================

@router.post("/regions", response_model=Any)
def create_region(
    payload: RegionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new region. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can create regions")
    # Get province_id from district if not provided
    province_id = payload.province_id
    if not province_id:
        district = db.query(District).filter(District.id == payload.district_id).first()
        if district:
            province_id = district.province_id
    region = Region(
        name=payload.name,
        district_id=payload.district_id,
        province_id=province_id,
        region_type=payload.region_type,
        main_crop_family_id=payload.main_crop_family_id,
    )
    db.add(region)
    db.commit()
    db.refresh(region)
    return {"id": region.id, "name": region.name, "district_id": region.district_id, "province_id": region.province_id, "region_type": region.region_type, "main_crop_family_id": region.main_crop_family_id}

@router.put("/regions/{region_id}", response_model=Any)
def update_region(
    region_id: int,
    payload: RegionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update a region. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can update regions")
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    if payload.name is not None:
        region.name = payload.name
    if payload.district_id is not None:
        region.district_id = payload.district_id
    if payload.province_id is not None:
        region.province_id = payload.province_id
    if payload.region_type is not None:
        region.region_type = payload.region_type
    if payload.main_crop_family_id is not None:
        region.main_crop_family_id = payload.main_crop_family_id
    if payload.lat is not None:
        region.lat = payload.lat
    if payload.lng is not None:
        region.lng = payload.lng
    db.commit()
    db.refresh(region)
    return {"id": region.id, "name": region.name, "district_id": region.district_id, "province_id": region.province_id, "region_type": region.region_type, "main_crop_family_id": region.main_crop_family_id}

@router.delete("/regions/{region_id}")
def delete_region(
    region_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Delete a region. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can delete regions")
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    # Check linked camps
    linked = db.query(Camp).filter(Camp.region_id == region_id).count()
    if linked > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete - {linked} camp(s) linked to this region")
    db.delete(region)
    db.commit()
    return {"message": "Region deleted"}

@router.post("/regions/{region_id}/approve")
def approve_region(
    region_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Approve a region. Provincial or above only."""
    user_role_upper = str(current_user.role).upper()
    is_provincial = "PROVINCIAL" in user_role_upper
    is_higher_admin = any(r in user_role_upper for r in ["NATIONAL", "SUPER_ADMIN", "ADMINISTRATOR"])
    
    if not (is_provincial or is_higher_admin):
        raise HTTPException(
            status_code=403, 
            detail="Only Provincial or higher roles can approve regions"
        )
    
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
        
    # Provincial users can only approve regions in their own province
    if is_provincial:
        district = db.query(District).filter(District.id == region.district_id).first()
        if not district or district.province_id != current_user.province_id:
            raise HTTPException(
                status_code=403, 
                detail="You can only approve regions in your province"
            )
    
    region.is_approved = True
    db.commit()
    return {"message": f"Region '{region.name}' approved successfully", "is_approved": True}


# ==================== Camp CRUD ====================

@router.post("/camps", response_model=Any)
def create_camp(
    payload: CampCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new camp. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can create camps")
    # Get district_id and province_id from region if not provided
    district_id = payload.district_id
    province_id = payload.province_id
    if not district_id or not province_id:
        region = db.query(Region).filter(Region.id == payload.region_id).first()
        if region:
            district_id = district_id or region.district_id
            province_id = province_id or region.province_id
    camp = Camp(
        name=payload.name,
        region_id=payload.region_id,
        district_id=district_id,
        province_id=province_id,
        camp_type=payload.camp_type,
    )
    db.add(camp)
    db.commit()
    db.refresh(camp)
    return {"id": camp.id, "name": camp.name, "region_id": camp.region_id, "district_id": camp.district_id, "province_id": camp.province_id, "camp_type": camp.camp_type}

@router.put("/camps/{camp_id}", response_model=Any)
def update_camp(
    camp_id: int,
    payload: CampUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update a camp. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can update camps")
    camp = db.query(Camp).filter(Camp.id == camp_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Camp not found")
    if payload.name is not None:
        camp.name = payload.name
    if payload.region_id is not None:
        camp.region_id = payload.region_id
    if payload.district_id is not None:
        camp.district_id = payload.district_id
    if payload.province_id is not None:
        camp.province_id = payload.province_id
    if payload.camp_type is not None:
        camp.camp_type = payload.camp_type
    if payload.lat is not None:
        camp.lat = payload.lat
    if payload.lng is not None:
        camp.lng = payload.lng
    db.commit()
    db.refresh(camp)
    return {"id": camp.id, "name": camp.name, "region_id": camp.region_id, "district_id": camp.district_id, "province_id": camp.province_id, "camp_type": camp.camp_type}

@router.delete("/camps/{camp_id}")
def delete_camp(
    camp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Delete a camp. Admin only."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can delete camps")
    camp = db.query(Camp).filter(Camp.id == camp_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Camp not found")
    # Check linked users
    linked = db.query(User).filter(User.camp_id == camp_id).count()
    if linked > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete - {linked} user(s) assigned to this camp")
    db.delete(camp)
    db.commit()
    return {"message": "Camp deleted"}


# ==================== Bulk Upload Endpoints ====================

@router.post("/national-crops/bulk-upload")
async def bulk_upload_national_crops(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Bulk upload national crops from CSV (crop_name, family_name)."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can bulk upload crops")
    
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    import csv
    import io

    content = await file.read()
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        decoded = content.decode('latin-1')
    
    f = io.StringIO(decoded)
    reader = csv.DictReader(f)
    
    # Header Validation
    expected_headers = ['crop_name', 'family_name']
    if not all(h in reader.fieldnames for h in expected_headers):
        raise HTTPException(status_code=400, detail=f"Invalid CSV headers. Expected columns: {', '.join(expected_headers)}")
    
    count = 0
    for row in reader:
        crop_name = row.get('crop_name', '').strip()
        family_name = row.get('family_name', '').strip()
        
        if not crop_name:
            continue
            
        # Find family_id if family_name provided
        family_id = None
        if family_name:
            family = db.query(CropFamily).filter(CropFamily.family_name == family_name).first()
            if family:
                family_id = family.id
            else:
                # Optionally create family if not exists? For now, just skip or leave None
                pass
        
        # Check if crop already exists
        existing = db.query(NationalCrop).filter(NationalCrop.crop_name == crop_name).first()
        if existing:
            if family_id:
                existing.family_id = family_id
            continue
            
        crop = NationalCrop(crop_name=crop_name, family_id=family_id)
        db.add(crop)
        count += 1
        
    db.commit()
    return {"message": f"Successfully imported {count} national crops"}

@router.post("/crop-families/bulk-upload")
async def bulk_upload_crop_families(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Bulk upload crop families from CSV (family_name)."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can bulk upload crop families")
    
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    import csv
    import io

    content = await file.read()
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        decoded = content.decode('latin-1')
    
    f = io.StringIO(decoded)
    reader = csv.DictReader(f)
    
    # Header Validation
    expected_headers = ['family_name']
    if not all(h in (reader.fieldnames or []) for h in expected_headers):
        raise HTTPException(status_code=400, detail=f"Invalid CSV headers. Expected columns: {', '.join(expected_headers)}")
    
    count = 0
    for row in reader:
        name = row.get('family_name', '').strip()
        if not name:
            continue
        
        existing = db.query(CropFamily).filter(CropFamily.family_name == name).first()
        if not existing:
            db.add(CropFamily(family_name=name))
            count += 1
            
    db.commit()
    return {"message": f"Successfully imported {count} crop families"}

@router.post("/regional-crops/bulk-upload")
async def bulk_upload_regional_crops(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Bulk upload regional crops from CSV (crop_name, region_name, family_name)."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can bulk upload crops")
    
    if not file.filename.lower().endswith('.csv'):
         raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    import csv
    import io

    content = await file.read()
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        decoded = content.decode('latin-1')
    
    f = io.StringIO(decoded)
    reader = csv.DictReader(f)
    
    # Header Validation
    expected_headers = ['crop_name', 'region_name']
    if not all(h in (reader.fieldnames or []) for h in expected_headers):
        raise HTTPException(status_code=400, detail=f"Invalid CSV headers. Expected columns: {', '.join(expected_headers)}")
    
    count = 0
    for row in reader:
        crop_name = row.get('crop_name', '').strip()
        region_name = row.get('region_name', '').strip()
        family_name = row.get('family_name', '').strip()
        
        if not crop_name or not region_name:
            continue
            
        # Find region_id
        region = db.query(Region).filter(Region.name == region_name).first()
        if not region:
            continue
            
        # Find family_id if family_name provided
        family_id = None
        if family_name:
            family = db.query(CropFamily).filter(CropFamily.family_name == family_name).first()
            if family:
                family_id = family.id
        
        # Check if crop already exists in THIS region
        existing = db.query(RegionalCrop).filter(
            RegionalCrop.crop_name == crop_name, 
            RegionalCrop.region_id == region.id
        ).first()
        
        if existing:
            if family_id:
                existing.family_id = family_id
            continue
            
        crop = RegionalCrop(crop_name=crop_name, region_id=region.id, family_id=family_id)
        db.add(crop)
        count += 1
        
    db.commit()
    return {"message": f"Successfully imported {count} regional crops"}

@router.post("/provinces/bulk-upload")
async def bulk_upload_provinces(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Bulk upload provinces from CSV (province_name)."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can bulk upload provinces")
    
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    import csv
    import io

    content = await file.read()
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        decoded = content.decode('latin-1')
    
    f = io.StringIO(decoded)
    reader = csv.DictReader(f)
    
    # Header Validation
    expected_headers = ['province_name']
    if not all(h in reader.fieldnames for h in expected_headers):
        raise HTTPException(status_code=400, detail=f"Invalid CSV headers. Expected columns: {', '.join(expected_headers)}")
    
    count = 0
    for row in reader:
        name = row.get('province_name', '').strip()
        if not name:
            continue
        
        existing = db.query(Province).filter(Province.name == name).first()
        if not existing:
            db.add(Province(name=name))
            count += 1
            
    db.commit()
    return {"message": f"Successfully imported {count} provinces"}

@router.post("/districts/bulk-upload")
async def bulk_upload_districts(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Bulk upload districts from CSV (district_name, province_name)."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can bulk upload districts")
    
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    import csv
    import io

    content = await file.read()
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        decoded = content.decode('latin-1')
    
    f = io.StringIO(decoded)
    reader = csv.DictReader(f)
    
    # Header Validation
    expected_headers = ['district_name', 'province_name']
    if not all(h in reader.fieldnames for h in expected_headers):
        raise HTTPException(status_code=400, detail=f"Invalid CSV headers. Expected columns: {', '.join(expected_headers)}")
    
    count = 0
    for row in reader:
        d_name = row.get('district_name', '').strip()
        p_name = row.get('province_name', '').strip()
        if not d_name or not p_name:
            continue
        
        province = db.query(Province).filter(Province.name == p_name).first()
        if not province:
            continue
            
        existing = db.query(District).filter(District.name == d_name, District.province_id == province.id).first()
        if not existing:
            db.add(District(name=d_name, province_id=province.id))
            count += 1
            
    db.commit()
    return {"message": f"Successfully imported {count} districts"}

@router.post("/regions/bulk-upload")
async def bulk_upload_regions(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Bulk upload regions from CSV (region_name, district_name)."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can bulk upload regions")
    
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    import csv
    import io

    content = await file.read()
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        decoded = content.decode('latin-1')
    
    f = io.StringIO(decoded)
    reader = csv.DictReader(f)
    
    # Header Validation
    expected_headers = ['region_name', 'district_name']
    if not all(h in reader.fieldnames for h in expected_headers):
        raise HTTPException(status_code=400, detail=f"Invalid CSV headers. Expected columns: {', '.join(expected_headers)}")
    
    count = 0
    for row in reader:
        r_name = row.get('region_name', '').strip()
        d_name = row.get('district_name', '').strip()
        if not r_name or not d_name:
            continue
        
        district = db.query(District).filter(District.name == d_name).first()
        if not district:
            continue
            
        existing = db.query(Region).filter(Region.name == r_name, Region.district_id == district.id).first()
        if not existing:
            db.add(Region(name=r_name, district_id=district.id, province_id=district.province_id))
            count += 1
            
    db.commit()
    return {"message": f"Successfully imported {count} regions"}

@router.post("/camps/bulk-upload")
async def bulk_upload_camps(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Bulk upload camps from CSV (camp_name, region_name)."""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only admins can bulk upload camps")
    
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    import csv
    import io

    content = await file.read()
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        decoded = content.decode('latin-1')
    
    f = io.StringIO(decoded)
    reader = csv.DictReader(f)
    
    # Header Validation
    expected_headers = ['camp_name', 'region_name']
    if not all(h in reader.fieldnames for h in expected_headers):
        raise HTTPException(status_code=400, detail=f"Invalid CSV headers. Expected columns: {', '.join(expected_headers)}")
    
    count = 0
    for row in reader:
        c_name = row.get('camp_name', '').strip()
        r_name = row.get('region_name', '').strip()
        if not c_name or not r_name:
            continue
        
        region = db.query(Region).filter(Region.name == r_name).first()
        if not region:
            continue
            
        existing = db.query(Camp).filter(Camp.name == c_name, Camp.region_id == region.id).first()
        if not existing:
            db.add(Camp(name=c_name, region_id=region.id, district_id=region.district_id, province_id=region.province_id))
            count += 1
            
    db.commit()
    return {"message": f"Successfully imported {count} camps"}
