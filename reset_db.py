from app import app, db, User, ElectionYear, ElectionPost, Election, Candidate, Vote
from werkzeug.security import generate_password_hash

with app.app_context():
    # Drop all tables
    db.drop_all()

    # Create all tables
    db.create_all()

    # Create admin user with a default Ethereum address
    # Note: This is a placeholder address. Replace it with your actual admin Ethereum address
    admin = User(
        username='admin',
        email='exkrogroup@gmail.com',
        is_admin=True,
        is_verified=True,  # Admin is automatically verified
        eth_address='0x742d35Cc6634C0532925a3b844Bc454e4438f44e'  # Default admin address
    )
    admin.set_password('admin')  # Using set_password method for proper hashing
    db.session.add(admin)

    # Commit changes
    db.session.commit()

    print("Database has been reset successfully!")
    print("Default admin credentials:")
    print("Username: admin")
    print("Password: admin")
    print("Email: exkrogroup@gmail.com")
    print("ETH Address: 0x742d35Cc6634C0532925a3b844Bc454e4438f44e")
