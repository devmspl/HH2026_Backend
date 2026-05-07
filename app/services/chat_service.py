from sqlalchemy.orm import Session
from app.models.user import User, ChatGroup, UserRole, Region, Camp, Province, District

from sqlalchemy import or_

def sync_user_groups(db: Session, user: User):
    """
    Automatically assigns a user to relevant system groups based on their role and location.
    """
    print(f"[DEBUG SERVICE] sync_user_groups for user {user.id} ({user.role})")
    if not user or user.is_deleted:
        print("[DEBUG SERVICE] User is null or deleted, skipping")
        return

    user_role = str(user.role).upper()

    # 1. National Group
    is_national_eligible = user_role in ["SUPER_ADMIN", "ADMINISTRATOR", "EXECUTIVE", "NATIONAL", "NATIONAL USER"] or user.is_superuser
    if is_national_eligible:
        print("[DEBUG SERVICE] User is eligible for National HQ Group")
        national_group = db.query(ChatGroup).filter(ChatGroup.group_type == "NATIONAL").first()
        if not national_group:
            print("[DEBUG SERVICE] Creating National HQ Group")
            national_group = ChatGroup(name="National HQ Group", manager_id=user.id, group_type="NATIONAL")
            db.add(national_group)
            db.flush()
        
        if user not in national_group.members:
            print(f"[DEBUG SERVICE] Adding user {user.id} to National HQ Group")
            national_group.members.append(user)
    
    # 2. Sync CAMP Group
    if user.camp_id:
        print(f"[DEBUG SERVICE] Syncing Camp Group for camp_id: {user.camp_id}")
        camp_group = db.query(ChatGroup).filter(ChatGroup.group_type == "CAMP", ChatGroup.camp_id == user.camp_id).first()
        
        if not camp_group:
            camp = db.query(Camp).filter(Camp.id == user.camp_id).first()
            camp_name = camp.name if camp else f"ID-{user.camp_id}"
            print(f"[DEBUG SERVICE] Creating Camp Group: {camp_name}")
            camp_group = ChatGroup(
                name=f"{camp_name} Camp Group",
                manager_id=user.id,
                group_type="CAMP",
                camp_id=user.camp_id
            )
            db.add(camp_group)
            db.flush()
        
        if user_role in ["AGENT", "CAMP"]:
            if user not in camp_group.members:
                print(f"[DEBUG SERVICE] Adding user {user.id} to Camp Group {camp_group.id}")
                camp_group.members.append(user)
    
    # 3. Sync REGION Group
    if user.region_id:
        print(f"[DEBUG SERVICE] Syncing Region Group for region_id: {user.region_id}")
        region_group = db.query(ChatGroup).filter(ChatGroup.group_type == "REGION", ChatGroup.region_id == user.region_id).first()
        
        if not region_group:
            region = db.query(Region).filter(Region.id == user.region_id).first()
            region_name = region.name if region else f"ID-{user.region_id}"
            print(f"[DEBUG SERVICE] Creating Region Group: {region_name}")
            region_group = ChatGroup(
                name=f"{region_name} Region Group",
                manager_id=user.id,
                group_type="REGION",
                region_id=user.region_id
            )
            db.add(region_group)
            db.flush()
        
        if user_role in ["REGION", "CAMP"]:
            if user not in region_group.members:
                print(f"[DEBUG SERVICE] Adding user {user.id} to Region Group {region_group.id}")
                region_group.members.append(user)

    db.commit()
    print("[DEBUG SERVICE] sync_user_groups completed")

def sync_all_groups(db: Session):
    """
    Global sync for all groups and all users across the entire hierarchy.
    Ensures pre-created groups exist and memberships are up-to-date.
    """
    print("[DEBUG SERVICE] sync_all_groups started for all hierarchy levels")
    created_count = 0
    updated_count = 0

    # 0. Team Groups (Manager + Subordinates)
    managers = db.query(User).filter(User.subordinates.any()).all()
    print(f"[DEBUG SERVICE] Found {len(managers)} managers for team sync")
    for manager in managers:
        group_name = f"{manager.full_name}'s Team"
        existing_group = db.query(ChatGroup).filter(
            ChatGroup.manager_id == manager.id,
            ChatGroup.name == group_name
        ).first()
        
        current_members = [manager] + manager.subordinates
        if not existing_group:
            new_group = ChatGroup(name=group_name, manager_id=manager.id)
            new_group.members = current_members
            db.add(new_group)
            created_count += 1
        else:
            existing_group.members = current_members
            updated_count += 1
    
    db.flush() # Ensure team groups are created before proceeding

    # 1. National Group
    national_members = db.query(User).filter(
        or_(
            User.role.in_([UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR, UserRole.EXECUTIVE, UserRole.NATIONAL, "National", "EXECUTIVE", "National User"]),
            User.is_superuser == True
        ),
        User.is_deleted == False
    ).all()
    if national_members:
        national_group = db.query(ChatGroup).filter(ChatGroup.group_type == "NATIONAL").first()
        if not national_group:
            print("[DEBUG SERVICE] Creating National HQ Group")
            manager = next((u for u in national_members if u.is_superuser), national_members[0])
            national_group = ChatGroup(name="National HQ Group", manager_id=manager.id, group_type="NATIONAL")
            db.add(national_group)
            db.flush()
            created_count += 1
        else:
            updated_count += 1
        national_group.members = national_members

    # 2. Provincial Groups
    provinces = db.query(Province).all()
    for prov in provinces:
        group = db.query(ChatGroup).filter(ChatGroup.group_type == "PROVINCIAL", ChatGroup.province_id == prov.id).first()
        if not group:
            print(f"[DEBUG SERVICE] Creating Provincial Group for {prov.name}")
            admin = db.query(User).filter(User.is_superuser == True).first()
            group = ChatGroup(name=f"{prov.name} Provincial Group", group_type="PROVINCIAL", province_id=prov.id, manager_id=admin.id if admin else 1)
            db.add(group)
            db.flush()
            created_count += 1
        else:
            updated_count += 1
        # Members: Provincial and District users in this province
        members = db.query(User).filter(User.province_id == prov.id, User.role.in_(["PROVINCIAL", "DISTRICT", "Provincial", "District"])).all()
        group.members = members

    # 3. District Groups
    districts = db.query(District).all()
    for dist in districts:
        group = db.query(ChatGroup).filter(ChatGroup.group_type == "DISTRICT", ChatGroup.district_id == dist.id).first()
        if not group:
            print(f"[DEBUG SERVICE] Creating District Group for {dist.name}")
            admin = db.query(User).filter(User.is_superuser == True).first()
            group = ChatGroup(name=f"{dist.name} District Group", group_type="DISTRICT", district_id=dist.id, manager_id=admin.id if admin else 1)
            db.add(group)
            db.flush()
            created_count += 1
        else:
            updated_count += 1
        # Members: District and Region users in this district
        members = db.query(User).filter(User.district_id == dist.id, User.role.in_(["DISTRICT", "REGION", "District", "Region"])).all()
        group.members = members

    # 4. Region Groups
    regions = db.query(Region).all()
    for reg in regions:
        group = db.query(ChatGroup).filter(ChatGroup.group_type == "REGION", ChatGroup.region_id == reg.id).first()
        if not group:
            print(f"[DEBUG SERVICE] Creating Region Group for {reg.name}")
            admin = db.query(User).filter(User.is_superuser == True).first()
            group = ChatGroup(
                name=f"{reg.name} Region Group", 
                group_type="REGION", 
                region_id=reg.id, 
                district_id=reg.district_id,
                province_id=reg.province_id,
                manager_id=admin.id if admin else 1
            )
            db.add(group)
            db.flush()
            created_count += 1
        else:
            updated_count += 1
        # Members: Region and Camp users in this region
        members = db.query(User).filter(User.region_id == reg.id, User.role.in_(["REGION", "CAMP", "Region", "Camp"])).all()
        group.members = members

    # 5. Camp Groups
    camps = db.query(Camp).all()
    for camp in camps:
        group = db.query(ChatGroup).filter(ChatGroup.group_type == "CAMP", ChatGroup.camp_id == camp.id).first()
        if not group:
            print(f"[DEBUG SERVICE] Creating Camp Group for {camp.name}")
            admin = db.query(User).filter(User.is_superuser == True).first()
            group = ChatGroup(
                name=f"{camp.name} Camp Group", 
                group_type="CAMP", 
                camp_id=camp.id, 
                region_id=camp.region_id,
                district_id=camp.district_id,
                province_id=camp.province_id,
                manager_id=admin.id if admin else 1
            )
            db.add(group)
            db.flush()
            created_count += 1
        else:
            updated_count += 1
        # Members: Camp Users and Agents in this camp
        members = db.query(User).filter(User.camp_id == camp.id, User.role.in_(["AGENT", "CAMP", "Agent", "Camp"])).all()
        group.members = members

    db.commit()
    print(f"[DEBUG SERVICE] sync_all_groups completed: {created_count} created, {updated_count} updated")
    return created_count, updated_count
