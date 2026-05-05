from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from sqlalchemy.exc import IntegrityError
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole, Customer
from app.core.audit import log_action
import csv
import io
import json
import string
import random

router = APIRouter()

CAMP_USER_MAX_CUSTOMERS = 100


def _customer_to_dict(c: Customer) -> Dict[str, Any]:
    """Serialize Customer ORM to JSON-safe dict."""
    d: Dict[str, Any] = {}
    for col in c.__table__.columns:
        val = getattr(c, col.name, None)
        if isinstance(val, datetime):
            val = val.isoformat() if val else None
        d[col.name] = val
    return d


class CustomerCreate(BaseModel):
    customer_id: Optional[str] = None
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None  # Male, Female, Other
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    cnic: Optional[str] = None
    farmer_id: Optional[str] = None
    camp_id: Optional[int] = None
    region_id: Optional[int] = None
    district_id: Optional[int] = None
    province_id: Optional[int] = None
    membership_status: Optional[str] = None
    agent_id: Optional[int] = None
    assigned_camp_user_id: Optional[int] = None
    household: Optional[str] = None
    education_level: Optional[str] = None
    emp_status: Optional[str] = None
    photo: Optional[str] = None

@router.get("/", response_model=Dict[str, Any])
def get_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    province_id: Optional[int] = None,
    district_id: Optional[int] = None,
    region_id: Optional[int] = None,
    camp_id: Optional[int] = None,
    category: Optional[str] = None,
    membership_status: Optional[str] = None,
    gender: Optional[str] = None,
):
    """
    Retrieve customers with advanced searching, hierarchical filtering, and gender support.
    """
    query = db.query(Customer)
    
    # 1. Role-Based Access Control (RBAC)
    user_role = str(current_user.role).upper()
    if user_role == "CAMP":
        query = query.filter(Customer.camp_id == current_user.camp_id)
    elif user_role == "REGION_MANAGER":
        query = query.filter(Customer.region_id == current_user.region_id)
    
    # 2. Search Logic
    if search:
        search_filter = or_(
            Customer.full_name.ilike(f"%{search}%"),
            Customer.phone.ilike(f"%{search}%"),
            Customer.email.ilike(f"%{search}%"),
            Customer.cnic.ilike(f"%{search}%"),
            Customer.customer_id.ilike(f"%{search}%"),
            Customer.farmer_id.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    # 3. Hierarchical Location Filters
    if province_id:
        query = query.filter(Customer.province_id == province_id)
    if district_id:
        query = query.filter(Customer.district_id == district_id)
    if region_id:
        query = query.filter(Customer.region_id == region_id)
    if camp_id:
        query = query.filter(Customer.camp_id == camp_id)

    # 4. Status, Category and Gender Filters
    if category:
        query = query.filter(Customer.category == category)
    if membership_status:
        query = query.filter(Customer.membership_status == membership_status)
    if gender:
        query = query.filter(Customer.gender == gender)

    total = query.count()
    customers = query.order_by(Customer.id.desc()).offset(skip).limit(limit).all()
    
    return {
        "items": [_customer_to_dict(c) for c in customers],
        "total": total
    }

@router.post("/", response_model=Any)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a single customer.
    Camp users: customer is assigned to them (assigned_camp_user_id = current_user.id).
    Max 100 customers per Camp user (spec: "add customers to their list maximum 100").
    """
    data = payload.model_dump(exclude_unset=True)
    # Allow multiple customers without CNIC: treat empty/whitespace as None
    if data.get("cnic") is not None and (not data["cnic"] or not str(data["cnic"]).strip()):
        data["cnic"] = None

    if current_user.role == UserRole.CAMP or current_user.role == "CAMP":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Camp users do not have permission to add customers.",
        )


    cnic_val = (payload.cnic and str(payload.cnic).strip()) or None
    if cnic_val:
        existing = db.query(Customer).filter(Customer.cnic == cnic_val).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer with this CNIC already exists.",
            )

    if cnic_val is not None:
        data["cnic"] = cnic_val
    
    # Auto-generate IDs if not provided
    if not data.get("customer_id"):
        # Generate random 5-letter ID
        while True:
            cid = ''.join(random.choices(string.ascii_uppercase, k=5))
            if not db.query(Customer).filter(Customer.customer_id == cid).first():
                data["customer_id"] = cid
                break
                
    if not data.get("farmer_id"):
        # Initial placeholder
        data["farmer_id"] = "F-TEMP"
    
    try:
        customer = Customer(**data)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        
        # Update farmer_id with actual ID
        if customer.farmer_id == "F-TEMP":
            customer.farmer_id = f"F{customer.id:04d}"
            db.commit()
            db.refresh(customer)
        log_action(db, current_user.id, "CREATE_CUSTOMER", f"Created customer {customer.full_name}")
        return _customer_to_dict(customer)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid data (e.g. location or agent ID not found). Check Province, District, Region, Camp and Agent.",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create customer: {str(e)}",
        )


@router.put("/{customer_id}", response_model=Any)
def update_customer(
    customer_id: int,
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a customer.
    Camp users can only edit customers assigned to them.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if current_user.role == UserRole.CAMP or current_user.role == "CAMP":
        if customer.assigned_camp_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit customers assigned to you.",
            )

    data = payload.model_dump(exclude_unset=True)
    if data.get("cnic") is not None and (not data["cnic"] or not str(data["cnic"]).strip()):
        data["cnic"] = None
    if current_user.role == UserRole.CAMP:
        data.pop("assigned_camp_user_id", None)  # Camp user cannot reassign

    for k, v in data.items():
        setattr(customer, k, v)
    try:
        db.commit()
        db.refresh(customer)
        log_action(db, current_user.id, "UPDATE_CUSTOMER", f"Updated customer {customer.full_name}")
        return _customer_to_dict(customer)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid data (e.g. location or agent ID not found).",
        )


@router.get("/{customer_id}", response_model=Any)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get customer by ID.
    Camp users can only view customers assigned to them.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if (current_user.role == UserRole.CAMP or current_user.role == "CAMP") and customer.camp_id != current_user.camp_id:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _customer_to_dict(customer)

@router.post("/bulk-upload")
async def bulk_upload_customers(
    category: str = "Regular",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process CSV upload and create customers.
    CSV Header: full_name, phone, email, address, cnic
    """
    if str(current_user.role).upper() != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only Super Admins can bulk import customers.")

    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    content = await file.read()
    try:
        try:
            decoded = content.decode('utf-8')
        except UnicodeDecodeError:
            decoded = content.decode('latin-1')

        # Normalize line endings
        normalized_content = decoded.replace('\r\n', '\n').replace('\r', '\n')
        f = io.StringIO(normalized_content)
        reader = csv.DictReader(f)
        
        # Header Validation (minimum headers)
        required_headers = ['full_name']
        actual_headers = [h.lower() for h in (reader.fieldnames or [])]
        if not all(h in actual_headers for h in required_headers):
            raise HTTPException(status_code=400, detail=f"Invalid CSV headers. Missing: {', '.join([h for h in required_headers if h not in actual_headers])}")

        customers_count = 0
        
        # Prep sequential IDs
        last_cust = db.query(Customer).order_by(Customer.id.desc()).first()
        next_base_num = (last_cust.id + 1) if last_cust else 1
        processed_count = 0
        
        user_role = str(current_user.role).upper()
        current_user_count = 0
        if user_role == UserRole.CAMP.value:
            current_user_count = db.query(Customer).filter(
                Customer.assigned_camp_user_id == current_user.id
            ).count()

        for row in reader:
            if user_role == UserRole.CAMP.value and (current_user_count + processed_count) >= CAMP_USER_MAX_CUSTOMERS:
                 # Stop importing once limit is reached
                 break
            # Case-insensitive row access
            row = {k.lower(): v for k, v in row.items()}
            # Skip empty rows
            if not any(row.values()):
                continue

            full_name = row.get('full_name', '').strip()
            if not full_name:
                continue

            phone = row.get('phone', row.get('contact', '')).strip()
            cnic = row.get('cnic', '').strip()

            # Check if customer already exists by CNIC or (Name + Phone)
            if cnic:
                existing = db.query(Customer).filter(Customer.cnic == cnic).first()
                if existing:
                    continue
            elif full_name and phone:
                existing = db.query(Customer).filter(Customer.full_name == full_name, Customer.phone == phone).first()
                if existing:
                    continue

            def get_int(val):
                if val is None:
                    return None
                val_str = str(val).strip()
                if not val_str:
                    return None
                try:
                    # Handle floats like "1.0" coming from some CSV exports
                    return int(float(val_str))
                except (ValueError, TypeError):
                    return None

            customer = Customer(
                full_name=full_name,
                first_name=row.get('first_name', row.get('first name', '')).strip(),
                last_name=row.get('last_name', row.get('last name', '')).strip(),
                phone=phone,
                email=row.get('email', '').strip(),
                address=row.get('address', '').strip(),
                cnic=cnic,
                age=get_int(row.get('age')),
                gender=row.get('gender', '').strip(),
                category=category,
                customer_id=row.get('customer_id', row.get('customerid', '')).strip() or None,
                farmer_id=row.get('farmer_id', row.get('farmerid', row.get('farmer id', ''))).strip() or None,
                camp_id=get_int(row.get('camp_id', row.get('campid', row.get('camp id')))),
                region_id=get_int(row.get('region_id', row.get('regionid', row.get('region id')))),
                district_id=get_int(row.get('district_id', row.get('districtid', row.get('district id')))),
                province_id=get_int(row.get('province_id', row.get('provinceid', row.get('province id')))),
                membership_status=row.get('membership_status', row.get('membershipstatus', '')).strip(),
                household=row.get('household', '').strip(),
                education_level=row.get('education_level', row.get('educationlevel', '')).strip(),
                emp_status=row.get('emp_status', row.get('empstatus', '')).strip(),
                photo=row.get('photo', '').strip()
            )
            
            # Apply Camp User assignment
            user_role = str(current_user.role).upper()
            if user_role == UserRole.CAMP.value:
                customer.assigned_camp_user_id = current_user.id
                customer.camp_id = current_user.camp_id
                customer.region_id = current_user.region_id
                customer.district_id = current_user.district_id
                customer.province_id = current_user.province_id
            else:
                # If not CAMP user, maybe allow setting it from CSV
                c_user_id = get_int(row.get('assigned_camp_user_id', row.get('camp_user_id')))
                if c_user_id:
                    customer.assigned_camp_user_id = c_user_id

            if not customer.customer_id:
                # Generate random 5-letter ID
                while True:
                    cid = ''.join(random.choices(string.ascii_uppercase, k=5))
                    if not db.query(Customer).filter(Customer.customer_id == cid).first():
                        customer.customer_id = cid
                        break
            
            if not customer.farmer_id:
                customer.farmer_id = f"F{next_base_num + processed_count:04d}"

            db.add(customer)
            processed_count += 1
            customers_count += 1
        
        db.commit()
        
        log_action(db, current_user.id, "BULK_IMPORT_CUSTOMERS", f"Imported {customers_count} customers from {file.filename} (Category: {category})")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")
    
    return {"message": f"Successfully imported {customers_count} customers.", "filename": file.filename}

@router.post("/{customer_id}/assign-me")
def self_assign_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Allow a Camp User to take ownership of an unassigned customer in their camp.
    """
    user_role = str(current_user.role).upper()
    if user_role == UserRole.CAMP.value or user_role == "CAMP":
        raise HTTPException(status_code=403, detail="Camp users do not have permission to add or assign customers.")


    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # 1. Validation: Must be unassigned
    if customer.assigned_camp_user_id is not None:
        raise HTTPException(status_code=400, detail="Customer is already assigned to another user.")

    # 2. Validation: Must be in the same camp
    if customer.camp_id != current_user.camp_id:
        raise HTTPException(status_code=403, detail="You can only self-assign customers within your own camp.")

    # 3. Validation: 100 customer limit check
    current_count = db.query(Customer).filter(
        Customer.assigned_camp_user_id == current_user.id
    ).count()
    if current_count >= CAMP_USER_MAX_CUSTOMERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You reached your limit of {CAMP_USER_MAX_CUSTOMERS} customers. Cannot assign more.",
        )

    # 4. Perform Assignment
    customer.assigned_camp_user_id = current_user.id
    # Sync other hierarchy fields for consistency
    customer.region_id = current_user.region_id
    customer.district_id = current_user.district_id
    customer.province_id = current_user.province_id

    db.commit()
    db.refresh(customer)
    
    log_action(db, current_user.id, "SELF_ASSIGN_CUSTOMER", f"User {current_user.email} self-assigned customer {customer.full_name}")
    
    return {"message": "Customer successfully assigned to you", "customer": _customer_to_dict(customer)}


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a customer.
    Camp users can only delete customers assigned to them.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if (current_user.role == UserRole.CAMP or current_user.role == "CAMP") and customer.assigned_camp_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete customers assigned to you.")
    
    customer_name = customer.full_name
    db.delete(customer)
    db.commit()
    
    log_action(db, current_user.id, "DELETE_CUSTOMER", f"Deleted customer {customer_name} (ID: {customer_id})")
    
    return {"message": "Customer deleted successfully"}
