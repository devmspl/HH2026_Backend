from sqlalchemy.orm import Session
from app.models.user import User, ChatGroup, UserRole, Region, Camp, Province, District
from sqlalchemy import or_, text

def sync_user_groups(db: Session, user: User):
    """
    Automatically assigns a user to relevant system groups based on their role and location.
    """
    if not user or user.is_deleted:
        return

    user_role = str(user.role).upper()

    # 1. National Group
    is_national_eligible = user_role in ["SUPER_ADMIN", "ADMINISTRATOR", "EXECUTIVE", "NATIONAL"] or user.is_superuser
    if is_national_eligible:
        national_group = db.query(ChatGroup).filter(ChatGroup.group_type == "NATIONAL").first()
        if not national_group:
            national_group = ChatGroup(name="National HQ Group", manager_id=user.id, group_type="NATIONAL")
            db.add(national_group)
            db.flush()
        
        if user not in national_group.members:
            national_group.members.append(user)
    
    # 2. Sync Region Group (for Region, Camp, and Agent users)
    if user.region_id:
        region_group = db.query(ChatGroup).filter(ChatGroup.group_type == "REGION", ChatGroup.region_id == user.region_id).first()
        if not region_group:
            region = db.query(Region).filter(Region.id == user.region_id).first()
            region_name = region.name if region else f"Region-{user.region_id}"
            region_group = ChatGroup(name=f"{region_name} Group", manager_id=user.id, group_type="REGION", region_id=user.region_id)
            db.add(region_group)
            db.flush()
        
        if user_role in ["AGENT", "CAMP", "REGION"]:
            if user not in region_group.members:
                region_group.members.append(user)
    
    db.commit()

def sync_all_groups(db: Session):
    """
    Optimized Global sync. 
    Processes small hierarchical groups first, then heavy team groups.
    """
    print("[DEBUG SERVICE] sync_all_groups started - Priority: Hierarchy First")
    created_count = 0
    updated_count = 0

    # PRIORITY 1: National Group (1 row)
    national_members = db.query(User).filter(
        or_(User.role.in_(["SUPER_ADMIN", "ADMINISTRATOR", "EXECUTIVE", "NATIONAL"]), User.is_superuser == True),
        User.is_deleted == False
    ).all()
    if national_members:
        national_group = db.query(ChatGroup).filter(ChatGroup.group_type == "NATIONAL").first()
        if not national_group:
            manager = next((u for u in national_members if u.is_superuser), national_members[0])
            national_group = ChatGroup(name="National HQ Group", manager_id=manager.id, group_type="NATIONAL")
            db.add(national_group)
            db.flush()
            created_count += 1
        national_group.members = national_members
        db.commit() # Commit small steps to ensure progress

    # PRIORITY 2: Provincial Groups (10 rows)
    provinces = db.query(Province).all()
    print(f"[DEBUG SERVICE] Syncing {len(provinces)} Provinces")
    for prov in provinces:
        group = db.query(ChatGroup).filter(ChatGroup.group_type == "PROVINCIAL", ChatGroup.province_id == prov.id).first()
        if not group:
            admin = db.query(User).filter(User.is_superuser == True).first()
            group = ChatGroup(name=f"{prov.name} Provincial Group", group_type="PROVINCIAL", province_id=prov.id, manager_id=admin.id if admin else 1)
            db.add(group)
            db.flush()
            created_count += 1
        members = db.query(User).filter(User.province_id == prov.id, User.role.in_(["PROVINCIAL", "DISTRICT"])).all()
        group.members = members
    db.commit()

    # PRIORITY 3: District Groups (116 rows)
    districts = db.query(District).all()
    print(f"[DEBUG SERVICE] Syncing {len(districts)} Districts")
    for dist in districts:
        group = db.query(ChatGroup).filter(ChatGroup.group_type == "DISTRICT", ChatGroup.district_id == dist.id).first()
        if not group:
            admin = db.query(User).filter(User.is_superuser == True).first()
            group = ChatGroup(name=f"{dist.name} District Group", group_type="DISTRICT", district_id=dist.id, manager_id=admin.id if admin else 1)
            db.add(group)
            db.flush()
            created_count += 1
        members = db.query(User).filter(User.district_id == dist.id, User.role.in_(["DISTRICT", "REGION"])).all()
        group.members = members
    db.commit()

    # PRIORITY 4: Region Groups (Combined for Region, Camp, and Agent)
    regions = db.query(Region).all()
    print(f"[DEBUG SERVICE] Syncing {len(regions)} Regions (includes Region/Camp/Agent users)")
    for reg in regions:
        group = db.query(ChatGroup).filter(ChatGroup.group_type == "REGION", ChatGroup.region_id == reg.id).first()
        if not group:
            admin = db.query(User).filter(User.is_superuser == True).first()
            group = ChatGroup(name=f"{reg.name} Group", group_type="REGION", region_id=reg.id, manager_id=admin.id if admin else 1)
            db.add(group)
            db.flush()
            created_count += 1
        # Include all users in the region regardless of camp
        members = db.query(User).filter(
            User.region_id == reg.id, 
            User.role.in_(["REGION", "CAMP", "AGENT"]),
            User.is_deleted == False
        ).all()
        group.members = members
    db.commit()

    # PRIORITY 5: Team Groups (Manager + Subordinates)
    print("[DEBUG SERVICE] Syncing Team Groups")
    managers = db.query(User).filter(User.subordinates.any()).all()
    for manager in managers:
        group_name = f"{manager.full_name}'s Team"
        group = db.query(ChatGroup).filter(ChatGroup.manager_id == manager.id, ChatGroup.group_type == 'TEAM').first()
        if not group:
            group = ChatGroup(name=group_name, manager_id=manager.id, group_type='TEAM')
            db.add(group)
            created_count += 1
        group.members = [manager] + manager.subordinates
    db.commit()

    # Note: CAMP groups are intentionally REMOVED per client requirement.
    # Agents and Camp Users now join their parent Region group instead.

    print(f"[DEBUG SERVICE] Full Sync Complete: {created_count} created")
    return created_count, updated_count
