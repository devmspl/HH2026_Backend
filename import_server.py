import pandas as pd
from app.db.session import SessionLocal
from app.models.user import User, UserRole, AccountStatus, Province, District, Region, Camp
from app.core.security import get_password_hash

def create_users():
    db = SessionLocal()
    try:
        # Paths to your uploaded excel files on server
        districts_file = "Districts.xlsx"
        regions_file = "Regions.xlsx"
        camps_file = "Camps.xlsx"

        password_hash = get_password_hash("Capa@123")

        print("Reading Excel files...")
        df_districts = pd.read_excel(districts_file)
        df_regions = pd.read_excel(regions_file)
        df_camps = pd.read_excel(camps_file)

        province_map = {}
        district_map = {}
        region_map = {}
        user_map = {}

        # Provinces
        print("Ensuring Provinces exist...")
        for p_name in set(df_districts['Province']):
            prov = db.query(Province).filter(Province.name == p_name).first()
            if not prov:
                prov = Province(name=p_name)
                db.add(prov); db.commit(); db.refresh(prov)
            province_map[p_name] = prov.id

        # Districts
        print("Importing Districts...")
        for _, row in df_districts.iterrows():
            p, d = row['Province'], row['District']
            dist = db.query(District).filter(District.name == d).first()
            if not dist:
                dist = District(name=d, province_id=province_map[p])
                db.add(dist); db.commit(); db.refresh(dist)
            district_map[d] = dist.id
            
            email = f"district_{d.lower().replace(' ', '_')}@example.com"
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    email=email,
                    hashed_password=password_hash,
                    full_name=f"District Manager - {d}",
                    role=UserRole.DISTRICT,
                    is_active=True,
                    account_status=AccountStatus.ACTIVE,
                    province_id=province_map[p],
                    district_id=dist.id
                )
                db.add(user); db.commit(); db.refresh(user)
            user_map[('DISTRICT', d)] = user.id

        # Regions
        print("Importing Regions...")
        for _, row in df_regions.iterrows():
            p, d, r = row['Province'], row['District'], row['Constituency']
            reg = db.query(Region).filter(Region.name == r).first()
            if not reg:
                reg = Region(name=r, district_id=district_map[d], province_id=province_map[p])
                db.add(reg); db.commit(); db.refresh(reg)
            region_map[r] = reg.id
            
            email = f"region_{r.lower().replace(' ', '_')}@example.com"
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    email=email,
                    hashed_password=password_hash,
                    full_name=f"Region Manager - {r}",
                    role=UserRole.REGION,
                    is_active=True,
                    account_status=AccountStatus.ACTIVE,
                    parent_id=user_map.get(('DISTRICT', d)),
                    province_id=province_map[p],
                    district_id=district_map[d],
                    region_id=reg.id
                )
                db.add(user); db.commit(); db.refresh(user)
            user_map[('REGION', r)] = user.id

        # Camps & Agents
        print("Importing Camps and Agents (this may take a while)...")
        for _, row in df_camps.iterrows():
            p, d, r, c_id, c_name = row['Province'], row['District'], row['Region'], row['Camp ID'], row['Camp']
            camp = db.query(Camp).filter(Camp.name == c_name).first()
            if not camp:
                camp = Camp(name=c_name, region_id=region_map[r], district_id=district_map[d], province_id=province_map[p])
                db.add(camp); db.commit(); db.refresh(camp)

            # Camp User
            c_email = f"camp_{c_id}@example.com"
            u = db.query(User).filter(User.email == c_email).first()
            if not u:
                u = User(
                    email=c_email,
                    hashed_password=password_hash,
                    full_name=f"Camp Manager - {c_name}",
                    role=UserRole.CAMP,
                    is_active=True,
                    account_status=AccountStatus.ACTIVE,
                    parent_id=user_map.get(('REGION', r)),
                    province_id=province_map[p],
                    district_id=district_map[d],
                    region_id=region_map[r],
                    camp_id=camp.id
                )
                db.add(u); db.commit(); db.refresh(u)
                
            # Agent User
            a_email = f"agent_{c_id}@example.com"
            if not db.query(User).filter(User.email == a_email).first():
                a = User(
                    email=a_email,
                    hashed_password=password_hash,
                    full_name=f"Agent - {c_name}",
                    role=UserRole.AGENT,
                    is_active=True,
                    account_status=AccountStatus.ACTIVE,
                    parent_id=u.id,
                    province_id=province_map[p],
                    district_id=district_map[d],
                    region_id=region_map[r],
                    camp_id=camp.id
                )
                db.add(a)
        
        db.commit()
        print("Success: All users and locations imported and linked correctly.")
    except Exception as e:
        db.rollback()
        print(f"Error during import: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_users()
