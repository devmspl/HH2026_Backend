from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, Customer
from app.core.audit import log_action
import csv
import io
import json

router = APIRouter()

@router.get("/", response_model=List[Any])
def get_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    """
    Retrieve customers.
    """
    customers = db.query(Customer).offset(skip).limit(limit).all()
    return customers

@router.get("/{customer_id}", response_model=Any)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get customer by ID.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
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
        for row in reader:
            # Skip empty rows
            if not any(row.values()):
                continue
                
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
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer_name = customer.full_name
    db.delete(customer)
    db.commit()
    
    log_action(db, current_user.id, "DELETE_CUSTOMER", f"Deleted customer {customer_name} (ID: {customer_id})")
    
    return {"message": "Customer deleted successfully"}
