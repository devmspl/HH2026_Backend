# CCNS Customer 180 - Customer Accounting Planner Backend

A FastAPI-based backend service for customer accounting planning and management.

## Overview

This is the backend API for the CCNS Customer 180 customer accounting planner application. It provides RESTful endpoints for managing customers, agents, surveys, reports, and other business entities with authentication and authorization features.ss

## Tech Stack

- **Framework**: FastAPI 0.110.0
- **Database**: PostgreSQL with SQLAlchemy 2.0.28
- **Authentication**: JWT (JSON Web Tokens) with python-jose
- **Password Hashing**: bcrypt
- **ORM**: SQLAlchemy with Alembic for migrations
- **Validation**: Pydantic 2.6.3
- **File Upload**: Cloudinary integration (optional)
- **Email**: emails library for notifications

## Features

- User authentication and authorization
- Customer management
- Agent management
- Survey creation and management
- Report generation
- Dashboard analytics
- File upload capabilities
- Search functionality
- Notification system
- Chat functionality

## Prerequisites

- Python 3.8+
- PostgreSQL database
- Redis (optional, for caching)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd customer-accounting-planner-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Unix/MacOS
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with database, `SECRET_KEY`, `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`, CORS, and optionally Cloudinary/Twilio. See [ENVIRONMENT.md](ENVIRONMENT.md).

5. **Set up the database**
   ```bash
   # Create database tables
   python create_db.py
   
   # Seed initial data
   python seed_db.py
   python seed_locations.py
   ```

## Configuration

The application uses environment variables for configuration. Key variables include:

- `POSTGRES_SERVER`: Database server hostname
- `POSTGRES_USER`: Database username
- `POSTGRES_PASSWORD`: Database password
- `POSTGRES_DB`: Database name
- `SECRET_KEY`: JWT secret key (change in production)
- `FIRST_SUPERUSER`: Admin user email
- `FIRST_SUPERUSER_PASSWORD`: Admin user password

## Running the Application

1. **Start the development server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc
   - OpenAPI JSON: http://localhost:8000/api/v1/openapi.json

## API Endpoints

All routes are under `/api/v1`. Authentication: `POST /login/access-token`; then use `Authorization: Bearer <token>`.

- **Login:** `/login/access-token` (POST, form: username, password)
- **Agents:** `/agents` (CRUD, approval, reset-password, deleted/recover)
- **Reports:** `/reports` (CRUD, crops/national, provincial, district, region, regional, dominant-map, top-family-by-province)
- **Locations:** `/locations/provinces`, `/districts`, `/regions`, `/camps`, `/regional-crops`
- **Dashboard:** `/dashboard/stats`, `/dashboard/gis-tracking`, `/dashboard/audit-logs`
- **Surveys:** `/surveys` (CRUD; create/edit/delete Super Admin only)
- **Customers:** `/customers` (CRUD, bulk-upload)
- **Notifications:** `/notifications/config/{key}`, `/notifications/config` (POST), templates, logs, send, retry
- **Search:** `/search/confirmation`, `/search/global`
- **Chat:** `/chat/groups`, messages, auto-create-groups
- **Upload:** `/upload/media`

Full reference: [../docs/API_REFERENCE.md](../docs/API_REFERENCE.md).

## Database Management

Several utility scripts are provided for database management:

- `migrate_db.py` - **Run this first:** creates tables and adds missing columns (idempotent). Use after deploy or schema changes.
- `seed_dashboard_data.py` - Seed crop families, national crops, locations, agents, reports, regional crops (optional).
- `create_db.py` - Create database tables (if not using migrate_db).
- `seed_db.py` - Seed initial data (e.g. first user).
- `seed_locations.py` - Seed location data.
- **`reset_keep_superadmin_only.py`** - Sab delete karo, sirf Super Admin (FIRST_SUPERUSER) bache. Phir aap khud agents/customers add karke flow samajh sakte ho.
- Other: `reset_db.py`, `fix_db.py`, etc. as needed.

## Authentication

The API uses JWT (JSON Web Tokens) for authentication:

1. Login with `POST /api/v1/login/access-token` (form: username, password) to get an access token.
2. Include the token in the Authorization header: `Bearer <token>`.
3. Tokens expire after 8 days (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

## CORS Configuration

The application is configured to allow requests from:
- http://localhost:3000
- http://localhost:3001
- http://localhost:3002
- http://localhost:3003
- http://localhost:3004
- http://localhost:3005

## Development

### Project Structure

```
app/
├── api/v1/           # API endpoints
├── core/             # Core functionality (auth, config)
├── db/               # Database configuration
├── models/           # SQLAlchemy models
├── schemas/          # Pydantic schemas
└── utils/            # Utility functions
```

### Adding New Endpoints

1. Create Pydantic schemas in `app/schemas/`
2. Add SQLAlchemy models in `app/models/`
3. Create endpoint files in `app/api/v1/endpoints/`
4. Register routes in `app/api/v1/api.py`

### Database Migrations

Use Alembic for database migrations:
```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

## Production Deployment

### Environment Setup

1. Set production environment variables
2. Use a production database (PostgreSQL)
3. Configure proper secret keys
4. Set up reverse proxy (nginx)
5. Use process manager (systemd, supervisor)

### Security Considerations

- Change default secret keys
- Use HTTPS in production
- Configure proper CORS origins
- Set up database connection pooling
- Implement rate limiting
- Use environment-specific configurations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]

## Support

For support and questions, please contact [your support email/channel].

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Version

Current version: 1.0.0
