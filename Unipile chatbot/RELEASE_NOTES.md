# Release Notes

## [1.0.3] - 2026-02-06
### Changed
- Reverted sidebar toggle icon to the original rectangle style per user preference.
- Maintained v1.0.2 improvements (visibility fixes and mobile responsiveness).

## [1.0.2] - 2026-02-06
### Fixed
- Sidebar toggle icon updated to minimalist "two-line" style.
- Fixed sidebar toggle disappearing when collapsed on some screen sizes.
- Improved chat interface responsiveness for mobile (400px width).
- Corrected CSS syntax error in media queries.

## [1.0.1] - 2026-02-06
**Deployment Fix**: Updated `deploy.sh` to correctly pass environment variables for database seeding.
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
