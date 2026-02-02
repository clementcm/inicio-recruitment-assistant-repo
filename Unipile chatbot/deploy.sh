#!/bin/bash

# Configuration - Update these with your GCP details
PROJECT_ID="your-project-id"
REGION="us-central1"
SERVICE_NAME="inicio-recruiter-assistant"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Starting deployment to Google Cloud Run..."

# 1. Build the container image using Cloud Build
echo "Building image..."
gcloud builds submit --tag $IMAGE_NAME .

# 2. Deploy to Cloud Run
# Note: This command assumes you have set up your DB and Secrets in GCP
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars="JWT_SECRET_KEY=change-this-in-prod-or-use-secrets"

echo "✅ Done! Your service should be live soon."
echo "Check the GCP Console for your Service URL."
