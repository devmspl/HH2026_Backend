from sqlalchemy.orm import Session
from app.models.user import User, ChatGroup, UserRole, Region, Camp, Province, District

ELIGIBLE_REGION_ROLES = ["REGION", "Region", "region", "CAMP", "Camp", "camp", "AGENT", "Agent", "agent"]

def sync_user_groups(db: Session, user: User):
    """
    Automatically assigns a user to relevant system groups based on their role and location.
    """
    if not user or user.is_deleted:
        return

    # 1. National Group
    is_national_eligible = str(user.role).upper() in ["SUPER_ADMIN", "ADMINISTRATOR", "EXECUTIVE", "NATIONAL", "NATIONAL USER"]
    if is_national_eligible:
        national_group = db.query(ChatGroup).filter(ChatGroup.group_type == "NATIONAL").first()
        if not national_group:
            # Create it if it doesn't exist yet
            national_group = ChatGroup(name="National HQ Group", manager_id=user.id, group_type="NATIONAL")
            db.add(national_group)
            db.flush()
        
        if user not in national_group.members:
            national_group.members.append(user)
    else:
        # If no longer eligible, remove
        national_group = db.query(ChatGroup).filter(ChatGroup.group_type == "NATIONAL").first()
        if national_group and user in national_group.members:
            national_group.members.remove(user)

    # 2. Provincial Group
    if user.province_id:
        province = db.query(Province).filter(Province.id == user.province_id).first()
        if province:
            prov_group = db.query(ChatGroup).filter(ChatGroup.group_type == "PROVINCE", ChatGroup.name.like(f"%{province.name}%")).first()
            if not prov_group:
                # Create it if it doesn't exist
                prov_group = ChatGroup(name=f"{province.name} Provincial Group", manager_id=user.id, group_type="PROVINCE")
                db.add(prov_group)
                db.flush()
            
            if user not in prov_group.members:
                prov_group.members.append(user)

    # 3. District Group
    if user.district_id:
        district = db.query(District).filter(District.id == user.district_id).first()
        if district:
            dist_group = db.query(ChatGroup).filter(ChatGroup.group_type == "DISTRICT", ChatGroup.name.like(f"%{district.name}%")).first()
            if dist_group and user not in dist_group.members:
                dist_group.members.append(user)

    # 4. Regional Group
    if user.region_id:
        reg_group = db.query(ChatGroup).filter(ChatGroup.group_type == "REGION", ChatGroup.region_id == user.region_id).first()
        if reg_group:
            is_reg_eligible = str(user.role).upper() in ["REGION", "CAMP", "AGENT"]
            if is_reg_eligible and user not in reg_group.members:
                reg_group.members.append(user)
            elif not is_reg_eligible and user in reg_group.members:
                if user in reg_group.members:
                    reg_group.members.remove(user)

    # 5. Camp Group
    if user.camp_id:
        camp = db.query(Camp).filter(Camp.id == user.camp_id).first()
        if camp:
            camp_group = db.query(ChatGroup).filter(ChatGroup.group_type == "CAMP", ChatGroup.name.like(f"%{camp.name}%")).first()
            if camp_group and user not in camp_group.members:
                camp_group.members.append(user)

    db.commit()

def sync_all_groups(db: Session):
    """
    Global sync for all groups and all users. 
    Ensures pre-created groups exist and memberships are up-to-date.
    """
    created_count = 0
    updated_count = 0
    
    # --- National Group ---
    national_group = db.query(ChatGroup).filter(ChatGroup.group_type == "NATIONAL").first()
    national_members = db.query(User).filter(
        User.role.in_([UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR, UserRole.EXECUTIVE, UserRole.NATIONAL, "National", "EXECUTIVE", "National User"]),
        User.is_deleted == False
    ).all()
    if national_members:
        if not national_group:
            manager = next((u for u in national_members if u.is_superuser), national_members[0])
            national_group = ChatGroup(name="National HQ Group", manager_id=manager.id, group_type="NATIONAL")
            national_group.members = national_members
            db.add(national_group)
            created_count += 1
        else:
            national_group.members = national_members
            updated_count += 1

    # --- Provincial Groups ---
    from app.models.user import Province
    all_provinces = db.query(Province).all()
    for prov in all_provinces:
        prov_group = db.query(ChatGroup).filter(ChatGroup.group_type == "PROVINCE", ChatGroup.name.like(f"%{prov.name}%")).first()
        prov_members = db.query(User).filter(User.province_id == prov.id, User.is_deleted == False).all()
        if prov_members:
            if not prov_group:
                prov_group = ChatGroup(name=f"{prov.name} Provincial Group", manager_id=prov_members[0].id, group_type="PROVINCE")
                prov_group.members = prov_members
                db.add(prov_group)
                created_count += 1
            else:
                prov_group.members = prov_members
                updated_count += 1

    # --- District Groups ---
    all_districts = db.query(District).all()
    for dist in all_districts:
        dist_group = db.query(ChatGroup).filter(ChatGroup.group_type == "DISTRICT", ChatGroup.name.like(f"%{dist.name}%")).first()
        dist_members = db.query(User).filter(User.district_id == dist.id, User.is_deleted == False).all()
        if dist_members:
            if not dist_group:
                dist_group = ChatGroup(name=f"{dist.name} District Group", manager_id=dist_members[0].id, group_type="DISTRICT")
                dist_group.members = dist_members
                db.add(dist_group)
                created_count += 1
            else:
                dist_group.members = dist_members
                updated_count += 1

    # --- Regional Groups ---
    from app.models.user import Region
    all_regions = db.query(Region).all()
    for reg in all_regions:
        reg_group = db.query(ChatGroup).filter(ChatGroup.group_type == "REGION", ChatGroup.region_id == reg.id).first()
        reg_members = db.query(User).filter(User.region_id == reg.id, User.role.in_(ELIGIBLE_REGION_ROLES), User.is_deleted == False).all()
        if reg_members:
            if not reg_group:
                manager = next((u for u in reg_members if str(u.role).upper() == "REGION"), reg_members[0])
                reg_group = ChatGroup(name=f"{reg.name} Region Group", manager_id=manager.id, group_type="REGION", region_id=reg.id)
                reg_group.members = reg_members
                db.add(reg_group)
                created_count += 1
            else:
                reg_group.members = reg_members
                updated_count += 1

    # --- Camp Groups ---
    all_camps = db.query(Camp).all()
    for camp in all_camps:
        camp_group = db.query(ChatGroup).filter(ChatGroup.group_type == "CAMP", ChatGroup.name.like(f"%{camp.name}%")).first()
        camp_members = db.query(User).filter(User.camp_id == camp.id, User.is_deleted == False).all()
        if camp_members:
            if not camp_group:
                camp_group = ChatGroup(name=f"{camp.name} Camp Group", manager_id=camp_members[0].id, group_type="CAMP")
                camp_group.members = camp_members
                db.add(camp_group)
                created_count += 1
            else:
                camp_group.members = camp_members
                updated_count += 1

    db.commit()
    return created_count, updated_count
