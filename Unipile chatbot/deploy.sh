#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting deployment setup for Inicio Recruiter Assistant...${NC}"

# 1. Custom Path & Gcloud Check
if [ -d "/Users/clement/GCP/google-cloud-sdk/bin" ]; then
    export PATH="/Users/clement/GCP/google-cloud-sdk/bin:$PATH"
fi

if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud is not installed or not in your PATH."
    echo "Please install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# 2. Check Authentication
echo "Checking authentication status..."
ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null)
if [ -z "$ACCOUNT" ]; then
    echo -e "${YELLOW}⚠️  You are not logged in to Google Cloud.${NC}"
    echo "Launching login..."
    gcloud auth login
else
    echo -e "Authenticated as: ${GREEN}$ACCOUNT${NC}"
fi

# 3. Get/Set Project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -n "$PROJECT_ID" ] && [ "$PROJECT_ID" != "(unset)" ]; then
    echo -e "Current configured project: ${GREEN}$PROJECT_ID${NC}"
    read -p "Is this correct? (Y/n): " CONFIRM
    if [[ "$CONFIRM" =~ ^[Nn] ]]; then
        PROJECT_ID="" # Clear to force re-entry
    fi
fi

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" == "(unset)" ]; then
    echo -e "${YELLOW}Fetching available projects...${NC}"
    gcloud projects list
    echo ""
    read -p "Enter Google Cloud Project ID from list above: " PROJECT_ID
    if [ -z "$PROJECT_ID" ]; then
        echo "Error: Project ID required."
        exit 1
    fi
    echo "Setting project to $PROJECT_ID..."
    gcloud config set project "$PROJECT_ID"
fi

# 3. Deployment Configuration
SERVICE_NAME="inicio-recruiter-assistant"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# 4. Enable Services (idempotent)
echo "Enabling necessary APIs (Cloud Build, Cloud Run)..."
gcloud services enable cloudbuild.googleapis.com run.googleapis.com

# Auto-detect API Key from .env
if [ -f .env ]; then
    echo "Reading GEMINI_API_KEY from .env..."
    ENV_KEY=$(grep GEMINI_API_KEY .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")
    if [ -n "$ENV_KEY" ]; then
        export GEMINI_API_KEY=$ENV_KEY
    fi
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${YELLOW}Warning: GEMINI_API_KEY not found.${NC}"
    read -p "Enter your valid Gemini API Key: " GEMINI_API_KEY
fi

# 5. Build Container
echo -e "${YELLOW}Building container image... (This may take a few minutes)${NC}"
gcloud builds submit --tag "$IMAGE_NAME" .

# 6. Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_NAME" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars="JWT_SECRET_KEY=$(openssl rand -hex 32)" \
    --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY"

echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "Your service URL is displayed above."
echo -e "${YELLOW}NOTE: The app is using an ephemeral SQLite database inside the container.${NC}"
echo -e "      - Data will reset if the container restarts."
echo -e "      - Default Admin: admin@example.com / admin123"
