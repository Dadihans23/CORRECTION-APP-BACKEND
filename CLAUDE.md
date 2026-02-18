# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

"Corrige Moi" (Correct Me) - A French educational AI correction platform. Django REST backend that processes images of school exercises, provides AI-powered corrections using Google Gemini, and manages user subscriptions with quota-based billing.

## Development Commands

```bash
# Run development server
python manage.py runserver

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser (uses phone_number as USERNAME_FIELD)
python manage.py createsuperuser

# Run tests
python manage.py test
python manage.py test treatment  # Single app

# Production (Render deployment)
gunicorn backend_project.wsgi:application --log-file -
```

## Architecture

### Django Apps

- **authentification** - User registration, JWT auth, OTP phone verification (custom user model with phone as username)
- **treatment** - Image processing, AI corrections, chat sessions (main business logic)
- **subscriptions** - Subscription packs, billing, quota management
- **custom_admin** - Admin dashboard with stats, reports, user/pack management (separate from Django admin)

### Key External Integrations

- **Google Gemini API** - AI corrections and chat (`GEMINI_API_KEY` in `.env`)
- **Pytesseract** - OCR text extraction from images
- **Firebase** - Push notifications for orders/status changes
- **ReportLab/OpenPyXL** - PDF and Excel report generation

### API Endpoints

```
/api/auth/
  POST signup/request/       → Start signup, sends OTP
  POST verify-otp/           → Verify OTP, complete signup
  POST login/                → Get JWT tokens
  POST token/refresh/        → Refresh JWT
  GET/PUT profile/           → User profile

/api/treatment/
  POST process-image/        → Main correction endpoint
  GET history/               → User's correction history
  POST chat/sessions/        → Create chat session
  POST chat/message/         → Send message in chat
  GET site-settings/         → App configuration

/api/subscription/
  POST subscribe/            → Subscribe to pack
  GET my-subscription/       → Current subscription status
  GET transactions/          → Payment history

/custom-admin/               → Dashboard for admin users
  GET /                      → Dashboard stats
  GET /users/                → User management
  GET /packs/                → Pack management
  GET /reports/              → Generate reports
```

### Authentication

- JWT tokens via SimpleJWT (7-day lifetime for both access and refresh)
- Phone number as username (E.164 format, e.g., +2250701234567)
- OTP-based signup and password reset (dev mode: OTP is always "123456")
- Header format: `Authorization: Bearer <token>`

### Database Models

**Core entities:**
- `CustomUser` - Phone-based auth, profile fields (country, school_level, institution)
- `Pack` - Subscription tiers with `image_corrections_limit` and `chat_questions_limit`
- `Subscription` - Links user to pack, tracks remaining quotas (`image_corrections_remaining`, `chat_questions_remaining`)
- `CorrectionHistory` - Stores each correction with extracted text, AI solution (JSON), detected content type
- `ChatSession`/`ChatMessage` - Conversation history with UUID-based sessions
- `UsageLog` - Tracks quota consumption per action
- `SiteSettings` - Singleton model for app-wide configuration

**Quota flow:**
1. User subscribes → `Subscription` created with limits from `Pack`
2. Each correction → `subscription.deduct_image_correction()` called
3. Each chat message → `subscription.deduct_chat_question()` called

### Image Correction Workflow

1. User uploads image with context (domain, level, exercise type, expectation)
2. OCR extracts text from image
3. Gemini detects if content is scientific or literary
4. Domain-specific prompt sent to Gemini API
5. Response includes result + step-by-step solution (supports LaTeX)
6. Quota deducted from user's subscription

## Configuration

- **Database**: SQLite (`db.sqlite3`) for development; PostgreSQL via `dj-database-url` for production
- **Static files**: `/static/` served via WhiteNoise in production
- **Media uploads**: `/media/` directory (corrections stored in `corrections/%Y/%m/%d/`)
- **Environment**: Uses `python-dotenv`, requires `.env` with `GEMINI_API_KEY`
- **CORS**: Configured in settings, `corsheaders` middleware must be first

## Key Files

- `backend_project/settings.py` - Main settings (commented production config at bottom)
- `treatment/views.py` - Core image processing logic (~1700 lines)
- `custom_admin/views.py` - Admin dashboard endpoints
- `authentification/models.py` - CustomUser, OTPCode, PendingUser
- `subscriptions/models.py` - Pack, Subscription, UsageLog, Transaction
