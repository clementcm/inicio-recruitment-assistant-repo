# Release Notes

## v1.0.1
- **Deployment Fix**: Updated `deploy.sh` to correctly pass environment variables for database seeding.
- **Environment**: Upgraded base image to **Python 3.11** for better library compatibility and performance.
- **Bug Fix**: Fixed environment variable parsing logic to ignore commented-out lines in `.env`.

## v1.0.0
- **Data Persistence**: Migrated from ephemeral SQLite to persistent Google Cloud SQL (PostgreSQL).
- **Security & Config**: Moved API keys (Gemini, Unipile) and configuration from environment variables to a secure database-backed system.
- **Admin Dashboard**: New system configuration interface for managing API keys and settings without redeployment.
- **Improved Stability**: Fixed Cloud Run deployment timeouts and implemented robust database connection handling.
- **Branding**: Updated visual identity to "Inicio Recruiter Assistant".

## v0.0.1
- Initial release with version tracking.
- Added version display in Settings menu.
