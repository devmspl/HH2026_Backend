# Backend Environment Variables

Copy `.env.example` to `.env` and set values. Required for run:

- **Database:** `POSTGRES_*` or `DATABASE_URL`
- **Auth:** `SECRET_KEY`, `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`
- **CORS:** `BACKEND_CORS_ORIGINS` (comma-separated origins)

Optional:

- **Cloudinary:** `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` (for media upload)
- **Twilio (SMS):** `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`. If not set, SMS on survey submit is logged only.
- **Fallback SMS number:** `DEFAULT_ADMIN_SMS` (used when no `sms_settings.survey_number` in system config)

Full list and examples: see [../docs/ENVIRONMENT.md](../docs/ENVIRONMENT.md).
