from sqlalchemy.orm import Session
from app.models.user import User, ChatGroup, UserRole, Region, Camp, Province, District

def sync_user_groups(db: Session, user: User):
    """
    Automatically assigns a user to relevant system groups based on their role and location.
    Strict Hierarchical Rules:
    - AGENT: Only Camp Group
    - CAMP USER: Camp Group + Region Group
    - REGION USER: Only Region Group
    """
    if not user or user.is_deleted:
        return

    user_role = str(user.role).upper()

    # 1. National Group (For non-restricted roles)
    is_national_eligible = user_role in ["SUPER_ADMIN", "ADMINISTRATOR", "EXECUTIVE", "NATIONAL", "NATIONAL USER"]
    if is_national_eligible:
        national_group = db.query(ChatGroup).filter(ChatGroup.group_type == "NATIONAL").first()
        if not national_group:
            national_group = ChatGroup(name="National HQ Group", manager_id=user.id, group_type="NATIONAL")
            db.add(national_group)
            db.flush()
        
        if user not in national_group.members:
            national_group.members.append(user)
    else:
        national_group = db.query(ChatGroup).filter(ChatGroup.group_type == "NATIONAL").first()
        if national_group and user in national_group.members:
            national_group.members.remove(user)

    # 2. Sync CAMP Group
    if user.camp_id:
        camp_group = db.query(ChatGroup).filter(ChatGroup.group_type == "CAMP", ChatGroup.camp_id == user.camp_id).first()
        
        if not camp_group:
            camp = db.query(Camp).filter(Camp.id == user.camp_id).first()
            camp_name = camp.name if camp else f"ID-{user.camp_id}"
            camp_group = ChatGroup(
                name=f"{camp_name} Camp Group",
                manager_id=user.id,
                group_type="CAMP",
                camp_id=user.camp_id
            )
            db.add(camp_group)
            db.flush()
        
        # ELIGIBILITY: Agent and Camp User
        if user_role in ["AGENT", "CAMP"]:
            # ADD ALL RELATABLE CAMP MEMBERS (Agents and Camp Managers)
            camp_members = db.query(User).filter(User.camp_id == user.camp_id, User.role.in_(["AGENT", "CAMP"])).all()
            for member in camp_members:
                if member not in camp_group.members:
                    camp_group.members.append(member)
        else:
            if user in camp_group.members:
                camp_group.members.remove(user)

    # 3. Sync REGION Group
    if user.region_id:
        region_group = db.query(ChatGroup).filter(ChatGroup.group_type == "REGION", ChatGroup.region_id == user.region_id).first()
        
        if not region_group:
            region = db.query(Region).filter(Region.id == user.region_id).first()
            region_name = region.name if region else f"ID-{user.region_id}"
            region_group = ChatGroup(
                name=f"{region_name} Region Group",
                manager_id=user.id,
                group_type="REGION",
                region_id=user.region_id
            )
            db.add(region_group)
            db.flush()
        
        # ELIGIBILITY: Region User and Camp User
        if user_role in ["REGION", "CAMP"]:
            # ADD ALL RELATABLE REGION MEMBERS (Region Managers and Camp Managers)
            region_members = db.query(User).filter(User.region_id == user.region_id, User.role.in_(["REGION", "CAMP"])).all()
            for member in region_members:
                if member not in region_group.members:
                    region_group.members.append(member)
        else:
            if user in region_group.members:
                region_group.members.remove(user)

    db.commit()

def sync_all_groups(db: Session):
    """
    Global sync for all groups and all users. 
    Ensures pre-created groups exist and memberships are up-to-date.
    """
    # Create National Group
    national_group = db.query(ChatGroup).filter(ChatGroup.group_type == "NATIONAL").first()
    national_members = db.query(User).filter(
        User.role.in_([UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR, UserRole.EXECUTIVE, UserRole.NATIONAL, "National", "EXECUTIVE", "National User"]),
        User.is_deleted == False
    ).all()
    if national_members:
        if not national_group:
            manager = next((u for u in national_members if u.is_superuser), national_members[0])
            national_group = ChatGroup(name="National HQ Group", manager_id=manager.id, group_type="NATIONAL")
            db.add(national_group)
            db.flush()
        national_group.members = national_members

    # Create Region Groups
    regions = db.query(Region).all()
    for reg in regions:
        group = db.query(ChatGroup).filter(ChatGroup.group_type == "REGION", ChatGroup.region_id == reg.id).first()
        if not group:
            group = ChatGroup(name=f"{reg.name} Region Group", group_type="REGION", region_id=reg.id, manager_id=1)
            db.add(group)
            db.flush()
        members = db.query(User).filter(User.region_id == reg.id, User.role.in_(["REGION", "CAMP"])).all()
        group.members = members

    # Create Camp Groups
    camps = db.query(Camp).all()
    for camp in camps:
        group = db.query(ChatGroup).filter(ChatGroup.group_type == "CAMP", ChatGroup.camp_id == camp.id).first()
        if not group:
            group = ChatGroup(name=f"{camp.name} Camp Group", group_type="CAMP", camp_id=camp.id, manager_id=1)
            db.add(group)
            db.flush()
        members = db.query(User).filter(User.camp_id == camp.id, User.role.in_(["AGENT", "CAMP"])).all()
        group.members = members

    db.commit()
    return True
