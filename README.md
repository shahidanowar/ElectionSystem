# College Election Web Application

A secure Flask-based web application for managing college elections. This application allows students to register, log in, and vote in elections while administrators can create and manage elections.

## Features

- User Authentication (Student Registration and Login)
- Admin Dashboard for Election Management
- Secure Voting System
- Real-time Election Results
- Prepared for Future Blockchain Integration

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd college-election-app
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Initialize the database and create an admin user:
```bash
python app.py  # This will create the database
python create_admin.py  # Follow the prompts to create an admin user
```

## Usage

1. Start the application:
```bash
python app.py
```

2. Access the application at `http://localhost:5000`

3. Log in as an admin to:
   - Create new elections
   - Add candidates
   - Manage active elections

4. Students can:
   - Register for an account
   - Log in
   - View active elections
   - Cast votes
   - View election results

## Security Features

- Password hashing using Werkzeug
- CSRF protection with Flask-WTF
- Secure session management with Flask-Login
- One vote per user per election enforcement
- Admin-only access to management features

## Future Enhancements

The application is designed to be integrated with blockchain technology. Key integration points are marked in the code with TODO comments, including:

- Election creation verification
- Candidate verification
- Vote transaction recording
- Vote integrity verification

## Directory Structure

```
college-election-app/
├── app.py              # Main application file
├── create_admin.py     # Admin user creation script
├── requirements.txt    # Project dependencies
├── templates/          # HTML templates
│   ├── admin/         # Admin dashboard templates
│   ├── election/      # Election-related templates
│   └── base.html      # Base template
└── election.db        # SQLite database