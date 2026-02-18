from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole, Customer
from app.core.audit import log_action
import csv
import io
import json

router = APIRouter()

CAMP_USER_MAX_CUSTOMERS = 100


class CustomerCreate(BaseModel):
    full_name: str
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
    household: Optional[str] = None
    education_level: Optional[str] = None
    emp_status: Optional[str] = None

@router.get("/", response_model=List[Any])
def get_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    """
    Retrieve customers.
    Camp users see only customers assigned to them (assigned_camp_user_id = current_user.id).
    """
    query = db.query(Customer)
    if current_user.role == UserRole.CAMP:
        query = query.filter(Customer.assigned_camp_user_id == current_user.id)
    customers = query.offset(skip).limit(limit).all()
    return customers

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

    if current_user.role == UserRole.CAMP:
        current_count = db.query(Customer).filter(
            Customer.assigned_camp_user_id == current_user.id
        ).count()
        if current_count >= CAMP_USER_MAX_CUSTOMERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Camp users can have at most {CAMP_USER_MAX_CUSTOMERS} customers. You have {current_count}.",
            )
        data["assigned_camp_user_id"] = current_user.id

    if payload.cnic:
        existing = db.query(Customer).filter(Customer.cnic == payload.cnic).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer with this CNIC already exists.",
            )

    customer = Customer(**data)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    log_action(db, current_user.id, "CREATE_CUSTOMER", f"Created customer {customer.full_name}")
    return customer


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

    if current_user.role == UserRole.CAMP:
        if customer.assigned_camp_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit customers assigned to you.",
            )

    data = payload.model_dump(exclude_unset=True)
    if current_user.role == UserRole.CAMP:
        data.pop("assigned_camp_user_id", None)  # Camp user cannot reassign

    for k, v in data.items():
        setattr(customer, k, v)
    db.commit()
    db.refresh(customer)
    log_action(db, current_user.id, "UPDATE_CUSTOMER", f"Updated customer {customer.full_name}")
    return customer


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
    if current_user.role == UserRole.CAMP and customer.assigned_camp_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

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
    content = await file.read()
    try:
        try:
            decoded = content.decode('utf-8')
        except UnicodeDecodeError:
            decoded = content.decode('latin-1')

        # Normalize line endings to avoid _csv.Error: new-line character seen in unquoted field
        normalized_content = decoded.replace('\r\n', '\n').replace('\r', '\n')
        f = io.StringIO(normalized_content)
        reader = csv.DictReader(f)
        
        customers_count = 0
        # Camp user cap: max 100 customers per Camp user
        if current_user.role == UserRole.CAMP:
            current_count = db.query(Customer).filter(
                Customer.assigned_camp_user_id == current_user.id
            ).count()

        for row in reader:
            # Skip empty rows
            if not any(row.values()):
                continue

            # Camp user: enforce max 100
            if current_user.role == UserRole.CAMP:
                if current_count + customers_count >= CAMP_USER_MAX_CUSTOMERS:
                    break  # Stop adding; we've hit the cap

            # Check if customer already exists by CNIC
            cnic = row.get('cnic', '').strip()
            if cnic:
                existing = db.query(Customer).filter(Customer.cnic == cnic).first()
                if existing:
                    continue

            customer = Customer(
                full_name=row.get('full_name', 'Unnamed').strip(),
                phone=row.get('phone', '').strip(),
                email=row.get('email', '').strip(),
                address=row.get('address', '').strip(),
                cnic=cnic,
                category=category
            )
            if current_user.role == UserRole.CAMP:
                customer.assigned_camp_user_id = current_user.id
            db.add(customer)
            customers_count += 1
        
        db.commit()
        
        log_action(db, current_user.id, "BULK_IMPORT_CUSTOMERS", f"Imported {customers_count} customers from {file.filename} (Category: {category})")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")
    
    return {"message": f"Successfully imported {customers_count} customers.", "filename": file.filename}

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
    if current_user.role == UserRole.CAMP and customer.assigned_camp_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete customers assigned to you.")
    
    customer_name = customer.full_name
    db.delete(customer)
    db.commit()
    
    log_action(db, current_user.id, "DELETE_CUSTOMER", f"Deleted customer {customer_name} (ID: {customer_id})")
    
    return {"message": "Customer deleted successfully"}
