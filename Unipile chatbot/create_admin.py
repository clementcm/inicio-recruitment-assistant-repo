from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
from backend import models, auth
import sys

def create_admin(email, password):
    db = SessionLocal()
    try:
        # Check if user exists
        existing_user = db.query(models.User).filter(models.User.email == email).first()
        if existing_user:
            print(f"User {email} already exists.")
            # Promote to admin/approved if exists
            existing_user.is_admin = True
            existing_user.is_approved = True
            db.commit()
            print(f"Promoted {email} to Admin.")
            return

        hashed_pwd = auth.get_password_hash(password)
        new_user = models.User(
            email=email, 
            hashed_password=hashed_pwd,
            is_admin=True,
            is_approved=True
        )
        db.add(new_user)
        db.commit()
        print(f"Admin user {email} created successfully.")
    except Exception as e:
        print(f"Error creating admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python create_admin.py <email> <password>")
        sys.exit(1)
    
    create_admin(sys.argv[1], sys.argv[2])
