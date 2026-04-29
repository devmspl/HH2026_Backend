import pandas as pd
from app.db.session import SessionLocal
from app.models.user import User, UserRole, AccountStatus, Province, District, Region, Camp
from app.core.security import get_password_hash

def create_users():
    db = SessionLocal()
    try:
        # Paths
        districts_file = "Districts.xlsx"
        regions_file = "Regions.xlsx"
        camps_file = "Camps.xlsx"

        password_hash = get_password_hash("Capa@123")

        print("Reading Excel files...")
        df_districts = pd.read_excel(districts_file)
        df_regions = pd.read_excel(regions_file)
        df_camps = pd.read_excel(camps_file)

        # Basic cleaning
        for df in [df_districts, df_regions, df_camps]:
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.strip()

        province_map = {}
        district_map = {}
        region_map = {}
        processed_emails = set()

        # 1. Provinces
        print("Importing Provinces...")
        unique_provinces = sorted(list(set(df_districts['Province'])))
        for p_name in unique_provinces:
            prov = Province(name=p_name)
            db.add(prov); db.commit(); db.refresh(prov)
            province_map[p_name] = prov.id

        # 2. Districts
        print("Importing Districts...")
        for _, row in df_districts.iterrows():
            p, d = row['Province'], row['District']
            dist = District(name=d, province_id=province_map[p])
            db.add(dist); db.commit(); db.refresh(dist)
            district_map[d] = dist.id
            
            email = f"district_{d.lower().replace(' ', '_')}@example.com"
            if email not in processed_emails:
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
                db.add(user)
                processed_emails.add(email)
        db.commit()

        # 3. Regions
        print("Importing Regions...")
        for _, row in df_regions.iterrows():
            p, d, r = row['Province'], row['District'], row['Constituency']
            reg = Region(name=r, district_id=district_map.get(d), province_id=province_map.get(p))
            db.add(reg); db.commit(); db.refresh(reg)
            region_map[r] = reg.id
            
            email = f"region_{r.lower().replace(' ', '_')}@example.com"
            if email not in processed_emails:
                user = User(
                    email=email,
                    hashed_password=password_hash,
                    full_name=f"Region Manager - {r}",
                    role=UserRole.REGION,
                    is_active=True,
                    account_status=AccountStatus.ACTIVE,
                    province_id=province_map.get(p),
                    district_id=district_map.get(d),
                    region_id=reg.id
                )
                db.add(user)
                processed_emails.add(email)
        db.commit()

        # 4. Camps & Agents
        print("Importing Camps and Agents...")
        camps_created = 0
        for _, row in df_camps.iterrows():
            p, d, r, c_id, c_name = row['Province'], row['District'], row['Region'], row['Camp ID'], row['Camp']
            
            camp = Camp(name=c_name, region_id=region_map.get(r), district_id=district_map.get(d), province_id=province_map.get(p))
            db.add(camp); db.flush()
            camps_created += 1

            # Camp User
            c_email = f"camp_{c_id}@example.com"
            if c_email not in processed_emails:
                u = User(
                    email=c_email, hashed_password=password_hash, full_name=f"Camp Manager - {c_name}",
                    role=UserRole.CAMP, is_active=True, account_status=AccountStatus.ACTIVE,
                    province_id=province_map.get(p), district_id=district_map.get(d),
                    region_id=region_map.get(r), camp_id=camp.id
                )
                db.add(u); db.flush()
                processed_emails.add(c_email)
                
                # Agent User
                a_email = f"agent_{c_id}@example.com"
                if a_email not in processed_emails:
                    a = User(
                        email=a_email, hashed_password=password_hash, full_name=f"Agent - {c_name}",
                        role=UserRole.AGENT, is_active=True, account_status=AccountStatus.ACTIVE,
                        parent_id=u.id, province_id=province_map.get(p), district_id=district_map.get(d),
                        region_id=region_map.get(r), camp_id=camp.id
                    )
                    db.add(a)
                    processed_emails.add(a_email)

            if camps_created % 1000 == 0:
                print(f"Progress: {camps_created} camps imported...")
                db.commit()
        
        db.commit()
        print(f"Final Counts - Provinces: {len(province_map)}, Districts: {len(district_map)}, Regions: {len(region_map)}, Camps: {camps_created}")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_users()
