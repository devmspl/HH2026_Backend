from typing import List
from app.models.user import UserRole

# Define role hierarchy (higher number = higher privilege)
ROLE_HIERARCHY = {
    UserRole.SUPER_ADMIN: 8,
    UserRole.ADMINISTRATOR: 7,
    UserRole.EXECUTIVE: 6,
    UserRole.NATIONAL: 5,
    UserRole.PROVINCIAL: 4,
    UserRole.DISTRICT: 3,
    UserRole.REGION: 2,
    UserRole.CAMP: 1,
    UserRole.AGENT: 0,
}

# Define which roles can create which other roles
ROLE_CREATION_PERMISSIONS = {
    UserRole.SUPER_ADMIN: [
        UserRole.SUPER_ADMIN,
        UserRole.ADMINISTRATOR,
        UserRole.EXECUTIVE,
        UserRole.NATIONAL,
        UserRole.PROVINCIAL,
        UserRole.DISTRICT,
        UserRole.REGION,
        UserRole.CAMP,
        UserRole.AGENT,
    ],
    UserRole.ADMINISTRATOR: [
        UserRole.ADMINISTRATOR,
        UserRole.EXECUTIVE,
        UserRole.NATIONAL,
        UserRole.PROVINCIAL,
        UserRole.DISTRICT,
        UserRole.REGION,
        UserRole.CAMP,
        UserRole.AGENT,
    ],
    UserRole.EXECUTIVE: [
        UserRole.EXECUTIVE,
        UserRole.NATIONAL,
        UserRole.PROVINCIAL,
        UserRole.DISTRICT,
        UserRole.REGION,
        UserRole.CAMP,
        UserRole.AGENT,
    ],
    UserRole.NATIONAL: [
        UserRole.NATIONAL,
        UserRole.PROVINCIAL,
        UserRole.DISTRICT,
        UserRole.REGION,
        UserRole.CAMP,
        UserRole.AGENT,
    ],
    UserRole.PROVINCIAL: [
        UserRole.PROVINCIAL,
        UserRole.DISTRICT,
        UserRole.REGION,
        UserRole.CAMP,
        UserRole.AGENT,
    ],
    UserRole.DISTRICT: [
        UserRole.DISTRICT,
        UserRole.REGION,
        UserRole.CAMP,
        UserRole.AGENT,
    ],
    UserRole.REGION: [
        UserRole.REGION,
        UserRole.CAMP,
        UserRole.AGENT,
    ],
    UserRole.CAMP: [
        UserRole.CAMP,
        UserRole.AGENT,
    ],
    UserRole.AGENT: [
        UserRole.AGENT,
    ],
}

def can_create_role(creator_role: UserRole, target_role: UserRole) -> bool:
    """Check if a user with creator_role can create a user with target_role"""
    return target_role in ROLE_CREATION_PERMISSIONS.get(creator_role, [])

def get_creatable_roles(user_role: UserRole) -> List[UserRole]:
    """Get list of roles that a user with user_role can create"""
    return ROLE_CREATION_PERMISSIONS.get(user_role, [])

def get_role_hierarchy_level(role: UserRole) -> int:
    """Get hierarchy level for a role"""
    return ROLE_HIERARCHY.get(role, 0)
