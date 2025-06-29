from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from pytz import timezone as pytz_timezone
from functools import wraps
import os
from werkzeug.utils import secure_filename
from blockchain_config import get_contract, w3
import ntplib
import socket

# Function to get accurate IST time from NTP server
def get_ist_time():
    """Get accurate IST time from NTP server"""
    try:
        # Use Google's NTP server
        ntp_server = 'asia.pool.ntp.org'
        client = ntplib.NTPClient()
        response = client.request(ntp_server, version=3)
        
        # Convert NTP timestamp to datetime with timezone
        ntp_time = datetime.fromtimestamp(response.tx_time, pytz_timezone('Asia/Kolkata'))
        
        return ntp_time
    except (ntplib.NTPException, socket.gaierror, socket.timeout):
        # Fallback to system time with timezone
        return datetime.now(pytz_timezone('Asia/Kolkata'))

# Function to format datetime in IST
def format_datetime(dt):
    """Format datetime in IST with consistent format: dd Month, yyyy hh:mm AM/PM"""
    if dt.tzinfo is None:
        dt = get_ist_time()
    else:
        dt = dt.astimezone(pytz_timezone('Asia/Kolkata'))
    return dt.strftime('%d %B, %Y %I:%M %p')

def calculate_time_remaining(start_date):
    """Calculate time remaining until election starts and return in days, hours, minutes"""
    ist_timezone = pytz_timezone('Asia/Kolkata')
    now = get_ist_time()
    start_date = start_date.astimezone(ist_timezone)
    
    if now >= start_date:
        return None
    
    remaining = start_date - now
    
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return {
        'days': days,
        'hours': hours,
        'minutes': minutes
    }

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///election.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_SECRET_TOKEN'] = 'sha602hid43ano'

# Add configuration for file uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'id_cards')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)  # This will store the roll number
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    id_card_image = db.Column(db.String(200))
    eth_address = db.Column(db.String(42), unique=True, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ElectionYear(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(100), nullable=False)  # e.g., "Student Council Elections 2025"
    description = db.Column(db.Text)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    elections = db.relationship('Election', backref='election_year', lazy='dynamic')

    def __init__(self, year, title, description, start_date, end_date, is_active=True):
        self.year = year
        self.title = title
        self.description = description
        self.is_active = is_active
        
        # Store dates in UTC
        # If dates are naive (no timezone), assume they are UTC
        if start_date.tzinfo is not None:
            self.start_date = start_date.astimezone(pytz_timezone('UTC')).replace(tzinfo=None)
        else:
            self.start_date = start_date
            
        if end_date.tzinfo is not None:
            self.end_date = end_date.astimezone(pytz_timezone('UTC')).replace(tzinfo=None)
        else:
            self.end_date = end_date

    def __repr__(self):
        return f'<ElectionYear {self.year}>'

class ElectionPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)  # e.g., "President", "Secretary"
    description = db.Column(db.Text)
    elections = db.relationship('Election', backref='post', lazy='dynamic')

    def __repr__(self):
        return f'<ElectionPost {self.title}>'

class Election(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    election_year_id = db.Column(db.Integer, db.ForeignKey('election_year.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('election_post.id'), nullable=False)
    description = db.Column(db.Text)
    candidates = db.relationship('Candidate', backref='election', lazy='dynamic')
    votes = db.relationship('Vote', backref='election', lazy='dynamic')

    def __repr__(self):
        return f'<Election {self.post.title} - {self.election_year.year}>'

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    election_id = db.Column(db.Integer, db.ForeignKey('election.id'), nullable=False)
    votes = db.relationship('Vote', backref='candidate', lazy=True)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    voter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey('election.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=False)
    transaction_hash = db.Column(db.String(66), nullable=False)

# Initialize database before first request
def init_db():
    with app.app_context():
        db.create_all()
        # Create initial admin user if needed
        if not User.query.filter_by(is_admin=True).first():
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True,
                is_verified=True,
                eth_address='0x0000000000000000000000000000000000000000'
            )
            db.session.add(admin)
            db.session.commit()

# Run database initialization
init_db()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Basic routes
@app.route('/')
def index():
    ist_time = get_ist_time()
    # Get all active election years first
    election_years = ElectionYear.query.filter(ElectionYear.is_active == True).all()
    
    # Filter active elections using Python datetime comparison with proper timezone handling
    ist_timezone = pytz_timezone('Asia/Kolkata')
    active_election_years = []
    for ey in election_years:
        # Convert stored UTC times to IST for comparison
        start_date_ist = datetime.utcnow().replace(
            year=ey.start_date.year, month=ey.start_date.month, day=ey.start_date.day,
            hour=ey.start_date.hour, minute=ey.start_date.minute, second=ey.start_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        end_date_ist = datetime.utcnow().replace(
            year=ey.end_date.year, month=ey.end_date.month, day=ey.end_date.day,
            hour=ey.end_date.hour, minute=ey.end_date.minute, second=ey.end_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        if start_date_ist <= ist_time <= end_date_ist:
            active_election_years.append(ey)
    
    # Get upcoming elections with proper formatting
    upcoming_elections = []
    for ey in election_years:
        # Convert stored UTC time to IST for comparison
        start_date_ist = datetime.utcnow().replace(
            year=ey.start_date.year, month=ey.start_date.month, day=ey.start_date.day,
            hour=ey.start_date.hour, minute=ey.start_date.minute, second=ey.start_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        end_date_ist = datetime.utcnow().replace(
            year=ey.end_date.year, month=ey.end_date.month, day=ey.end_date.day,
            hour=ey.end_date.hour, minute=ey.end_date.minute, second=ey.end_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        if start_date_ist > ist_time:
            upcoming_elections.append({
                'id': ey.id,
                'title': ey.title,
                'description': ey.description,
                'start_date': start_date_ist,
                'end_date': end_date_ist,
                'formatted_start': format_datetime(start_date_ist),
                'formatted_end': format_datetime(end_date_ist)
            })
    
    # Format times for display
    for ey in active_election_years:
        # Convert stored UTC times to IST for display
        start_date_ist = datetime.utcnow().replace(
            year=ey.start_date.year, month=ey.start_date.month, day=ey.start_date.day,
            hour=ey.start_date.hour, minute=ey.start_date.minute, second=ey.start_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        end_date_ist = datetime.utcnow().replace(
            year=ey.end_date.year, month=ey.end_date.month, day=ey.end_date.day,
            hour=ey.end_date.hour, minute=ey.end_date.minute, second=ey.end_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        ey.formatted_start = format_datetime(start_date_ist)
        ey.formatted_end = format_datetime(end_date_ist)
    
    # Calculate time remaining for upcoming elections
    for i, ey in enumerate(upcoming_elections):
        time_remaining = calculate_time_remaining(ey['start_date'])
        upcoming_elections[i]['time_remaining'] = time_remaining
    
    return render_template('index.html', 
                         election_years=active_election_years, 
                         upcoming_elections=upcoming_elections,
                         now=ist_time, 
                         ist_timezone=ist_timezone)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form['username']  # This will be the roll number
        email = request.form['email']
        password = request.form['password']
        eth_address = request.form['eth_address']
        
        # Check if username is numeric (roll number)
        if not username.isdigit():
            flash('Roll number must contain only numbers.', 'danger')
            return redirect(url_for('register'))
            
        # Check if roll number already exists
        if User.query.filter_by(username=username).first():
            flash('An account with this roll number already exists.', 'danger')
            return redirect(url_for('register'))
            
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'danger')
            return redirect(url_for('register'))
            
        # Check if Ethereum address already exists
        if User.query.filter_by(eth_address=eth_address).first():
            flash('An account with this Ethereum address already exists.', 'danger')
            return redirect(url_for('register'))
            
        # Handle ID card upload
        if 'id_card' not in request.files:
            flash('No ID card file uploaded.', 'danger')
            return redirect(url_for('register'))
            
        id_card = request.files['id_card']
        if id_card.filename == '':
            flash('No ID card file selected.', 'danger')
            return redirect(url_for('register'))
            
        if id_card and allowed_file(id_card.filename):
            # Secure the filename and save
            filename = secure_filename(f"{username}_{id_card.filename}")
            id_card.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            # Create new user
            user = User(
                username=username,  # Roll number as username
                email=email,
                eth_address=eth_address,
                id_card_image=filename
            )
            user.set_password(password)
            
            try:
                db.session.add(user)
                db.session.commit()
                flash('Registration successful! Please wait for admin verification.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash('Registration failed. Please try again.', 'danger')
                return redirect(url_for('register'))
        else:
            flash('Invalid file type. Please upload PNG or JPEG images only.', 'danger')
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            if not user.is_verified and not user.is_admin:
                flash('Your account is pending verification. Please wait for admin approval.')
                return redirect(url_for('login'))
            login_user(user)
            flash('Logged in successfully!')
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!')
    return redirect(url_for('index'))

@app.route('/register/admin/<token>', methods=['GET', 'POST'])
def register_admin(token):
    if token != app.config['ADMIN_SECRET_TOKEN']:
        abort(404)  # Return 404 for invalid token to hide the admin registration
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        eth_address = request.form.get('eth_address')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register_admin', token=token))
            
        admin = User(
            username=username,
            email=email,
            eth_address=eth_address,
            password_hash=generate_password_hash(password),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        flash('Admin registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('admin/register.html')

# Election Management Routes
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    ist_timezone = pytz_timezone('Asia/Kolkata')
    now = get_ist_time()
    
    # Get all election years and posts
    election_years = ElectionYear.query.all()
    available_posts = ElectionPost.query.all()
    
    # Calculate statistics
    pending_verifications = User.query.filter_by(is_verified=False, is_admin=False).count()
    verified_users = User.query.filter_by(is_verified=True, is_admin=False).count()
    
    # Count active and upcoming elections
    active_elections = 0
    upcoming_elections = 0
    
    for ey in election_years:
        # Convert stored UTC times to IST for comparison
        start_date_ist = datetime.utcnow().replace(
            year=ey.start_date.year, 
            month=ey.start_date.month, 
            day=ey.start_date.day,
            hour=ey.start_date.hour, 
            minute=ey.start_date.minute, 
            second=ey.start_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        end_date_ist = datetime.utcnow().replace(
            year=ey.end_date.year, 
            month=ey.end_date.month, 
            day=ey.end_date.day,
            hour=ey.end_date.hour, 
            minute=ey.end_date.minute, 
            second=ey.end_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        if ey.is_active and start_date_ist <= now <= end_date_ist:
            active_elections += 1
        elif ey.is_active and now < start_date_ist:
            upcoming_elections += 1
    
    # Add formatted dates to election years for display
    for ey in election_years:
        # Convert stored UTC times to IST for display
        start_date_ist = datetime.utcnow().replace(
            year=ey.start_date.year, month=ey.start_date.month, day=ey.start_date.day,
            hour=ey.start_date.hour, minute=ey.start_date.minute, second=ey.start_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        end_date_ist = datetime.utcnow().replace(
            year=ey.end_date.year, month=ey.end_date.month, day=ey.end_date.day,
            hour=ey.end_date.hour, minute=ey.end_date.minute, second=ey.end_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        ey.formatted_start = format_datetime(start_date_ist)
        ey.formatted_end = format_datetime(end_date_ist)
        ey.start_date_ist = start_date_ist
        ey.end_date_ist = end_date_ist
    
    return render_template('admin/dashboard.html',
                         election_years=election_years,
                         available_posts=available_posts,
                         pending_verifications=pending_verifications,
                         verified_users=verified_users,
                         active_elections=active_elections,
                         upcoming_elections=upcoming_elections,
                         now=now,
                         ist_timezone=ist_timezone)

@app.route('/admin/election/post/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_election_post():
    if request.method == 'POST':
        post = ElectionPost(
            title=request.form.get('title'),
            description=request.form.get('description')
        )
        db.session.add(post)
        db.session.commit()
        flash('Election post created successfully!')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/create_election_post.html')

@app.route('/admin/election/<int:election_year_id>/add-post', methods=['POST'])
@login_required
@admin_required
def create_election_for_post(election_year_id):
    post_id = request.form.get('post_id')
    if not post_id:
        flash('Please select a post.', 'error')
        return redirect(url_for('admin_dashboard'))
        
    # Check if this post is already in the election year
    existing_election = Election.query.filter_by(
        election_year_id=election_year_id,
        post_id=post_id
    ).first()
    
    if existing_election:
        flash('This post already exists in the election year.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    election = Election(
        election_year_id=election_year_id,
        post_id=post_id,
        description=request.form.get('description')
    )
    db.session.add(election)
    db.session.commit()
    flash('Post added to election successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/election/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_election():
    if request.method == 'POST':
        # Parse start and end date as IST, then convert to UTC for storage
        ist_offset = timedelta(hours=5, minutes=30)
        start_date_ist = datetime.strptime(request.form.get('start_date'), '%Y-%m-%dT%H:%M')
        end_date_ist = datetime.strptime(request.form.get('end_date'), '%Y-%m-%dT%H:%M')
        # Convert IST to UTC by subtracting 5:30
        start_date_utc = start_date_ist - ist_offset
        end_date_utc = end_date_ist - ist_offset
        election_year = ElectionYear(
            year=int(request.form.get('year')),
            title=request.form.get('title'),
            description=request.form.get('description'),
            start_date=start_date_utc,
            end_date=end_date_utc,
            is_active=True
        )
        db.session.add(election_year)
        db.session.commit()
        flash('Election year created successfully!')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/create_election.html')

@app.route('/admin/election/<int:election_year_id>/post/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_election_post_for_year(election_year_id):
    if request.method == 'POST':
        election_post = ElectionPost(
            title=request.form.get('title'),
            description=request.form.get('description')
        )
        db.session.add(election_post)
        db.session.commit()
        flash('Election post created successfully!')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/create_election_post.html')

@app.route('/admin/election/<int:election_id>/candidates/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_candidate(election_id):
    election = Election.query.get_or_404(election_id)
    if request.method == 'POST':
        candidate = Candidate(
            name=request.form.get('name'),
            description=request.form.get('description'),
            election_id=election_id
        )
        db.session.add(candidate)
        db.session.commit()
        flash('Candidate added successfully!')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/add_candidate.html', election=election)

# Election Routes
@app.route('/election/<int:election_id>')
@login_required
def view_election(election_id):
    election = Election.query.get_or_404(election_id)
    election_year = election.election_year
    ist_timezone = pytz_timezone('Asia/Kolkata')
    now = get_ist_time()
    
    # Convert stored UTC times to IST for comparison and display
    start_date_ist = datetime.utcnow().replace(
        year=election_year.start_date.year, 
        month=election_year.start_date.month, 
        day=election_year.start_date.day,
        hour=election_year.start_date.hour, 
        minute=election_year.start_date.minute, 
        second=election_year.start_date.second
    ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
    
    end_date_ist = datetime.utcnow().replace(
        year=election_year.end_date.year, 
        month=election_year.end_date.month, 
        day=election_year.end_date.day,
        hour=election_year.end_date.hour, 
        minute=election_year.end_date.minute, 
        second=election_year.end_date.second
    ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
    
    # Add IST formatted dates to election_year for template
    election_year.start_date_ist = start_date_ist
    election_year.end_date_ist = end_date_ist
    
    # Check if user has already voted
    has_voted = Vote.query.filter_by(
        election_id=election_id,
        voter_id=current_user.id
    ).first() is not None
    
    return render_template('election/view.html',
                         election=election,
                         election_year=election_year,
                         has_voted=has_voted,
                         now=now,
                         ist_timezone=ist_timezone)

@app.route('/election/<int:election_id>/vote', methods=['POST'])
@login_required
def cast_vote(election_id):
    if not current_user.is_verified:
        return jsonify({'status': 'error', 'message': 'Your account must be verified to vote.'})

    election = Election.query.get_or_404(election_id)
    candidate_id = request.form.get('candidate_id')
    
    if not candidate_id:
        return jsonify({'status': 'error', 'message': 'Please select a candidate.'})
    
    # Check if election is active
    ist_time = get_ist_time()
    ist_timezone = pytz_timezone('Asia/Kolkata')
    
    # Convert stored UTC times to IST for comparison
    start_date_ist = datetime.utcnow().replace(
        year=election.election_year.start_date.year, 
        month=election.election_year.start_date.month, 
        day=election.election_year.start_date.day,
        hour=election.election_year.start_date.hour, 
        minute=election.election_year.start_date.minute, 
        second=election.election_year.start_date.second
    ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
    
    end_date_ist = datetime.utcnow().replace(
        year=election.election_year.end_date.year, 
        month=election.election_year.end_date.month, 
        day=election.election_year.end_date.day,
        hour=election.election_year.end_date.hour, 
        minute=election.election_year.end_date.minute, 
        second=election.election_year.end_date.second
    ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
    
    formatted_start = format_datetime(start_date_ist)
    formatted_end = format_datetime(end_date_ist)
    
    if not (election.election_year.is_active and start_date_ist <= ist_time <= end_date_ist):
        if ist_time < start_date_ist:
            return jsonify({
                'status': 'error',
                'message': f'Election has not started yet. Voting opens at {formatted_start}'
            })
        elif ist_time > end_date_ist:
            return jsonify({
                'status': 'error',
                'message': f'Election has ended. Voting closed at {formatted_end}'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Election is not currently active'
            })

    # Check if already voted
    has_voted = Vote.query.filter_by(
        election_id=election_id,
        voter_id=current_user.id
    ).first() is not None

    if has_voted:
        return jsonify({'status': 'error', 'message': 'You have already voted in this election.'})

    try:
        # Get the contract
        contract = get_contract()
        
        # Create the vote transaction
        nonce = w3.eth.get_transaction_count(current_user.eth_address)
        
        # Build the transaction using the contract's function
        transaction = contract.functions.castVote(
            int(election_id),
            int(candidate_id)
        ).build_transaction({
            'chainId': 11155111,  # Sepolia chain ID
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'from': current_user.eth_address,
            'value': 0
        })

        # Convert data to proper format
        tx_data = {
            'to': transaction['to'],
            'from': transaction['from'],
            'data': transaction['data'].hex() if isinstance(transaction['data'], bytes) else transaction['data'],
            'value': '0x0',
            'gas': hex(transaction['gas']),
            'gasPrice': hex(transaction['gasPrice']),
            'nonce': hex(transaction['nonce']),
            'chainId': transaction['chainId']
        }
        
        # Return the transaction data for MetaMask
        return jsonify({
            'status': 'success',
            'transaction': tx_data
        })

    except Exception as e:
        print(f"Error in cast_vote: {str(e)}")  # Add logging
        import traceback
        traceback.print_exc()  # Print full stack trace
        return jsonify({'status': 'error', 'message': f'Error casting vote: {str(e)}'})

@app.route('/election/<int:election_id>/vote/confirm', methods=['POST'])
@login_required
def confirm_vote(election_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data received'})

        transaction_hash = data.get('transactionHash')
        candidate_id = data.get('candidateId')

        if not transaction_hash or not candidate_id:
            return jsonify({'status': 'error', 'message': 'Missing transaction hash or candidate ID'})

        # Wait for transaction confirmation
        try:
            receipt = w3.eth.wait_for_transaction_receipt(transaction_hash, timeout=60)
            if receipt.status != 1:
                return jsonify({'status': 'error', 'message': 'Transaction failed'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Error confirming transaction: {str(e)}'})

        # Record the vote in database
        vote = Vote(
            voter_id=current_user.id,
            election_id=election_id,
            candidate_id=candidate_id,
            transaction_hash=transaction_hash
        )
        db.session.add(vote)
        db.session.commit()

        return jsonify({'status': 'success', 'message': 'Vote recorded successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Error recording vote: {str(e)}'})

@app.route('/election/results')
@login_required
def election_results():
    ist_timezone = pytz_timezone('Asia/Kolkata')
    current_time = get_ist_time()
    election_years = ElectionYear.query.all()
    results = {}
    
    # Get contract instance
    contract = get_contract()
    
    for election_year in election_years:
        # Convert stored UTC times to IST for comparison
        start_date_ist = datetime.utcnow().replace(
            year=election_year.start_date.year, 
            month=election_year.start_date.month, 
            day=election_year.start_date.day,
            hour=election_year.start_date.hour, 
            minute=election_year.start_date.minute, 
            second=election_year.start_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        end_date_ist = datetime.utcnow().replace(
            year=election_year.end_date.year, 
            month=election_year.end_date.month, 
            day=election_year.end_date.day,
            hour=election_year.end_date.hour, 
            minute=election_year.end_date.minute, 
            second=election_year.end_date.second
        ).replace(tzinfo=pytz_timezone('UTC')).astimezone(ist_timezone)
        
        # Format dates for display
        formatted_start_date = start_date_ist.strftime('%Y-%m-%d %H:%M')
        formatted_end_date = end_date_ist.strftime('%Y-%m-%d %H:%M')
        
        # Only show results if election has ended
        if current_time > end_date_ist:
            results[election_year.id] = {
                'title': election_year.title,
                'end_date': formatted_end_date,
                'elections': [],
                'total_votes': 0,
                'status': 'ended'
            }
            for election in election_year.elections:
                results[election_year.id]['elections'].append({
                    'post': election.post.title,
                    'candidates': [],
                    'total_votes': 0
                })
                for candidate in election.candidates:
                    # Get vote count from both database and blockchain
                    db_vote_count = Vote.query.filter_by(candidate_id=candidate.id).count()
                    try:
                        chain_vote_count = contract.functions.getVoteCount(election.id, candidate.id).call()
                        # Verify vote counts match
                        if db_vote_count != chain_vote_count:
                            flash(f'Warning: Vote count mismatch detected for {candidate.name} in {election.post.title}', 'warning')
                    except Exception as e:
                        chain_vote_count = db_vote_count
                        flash(f'Warning: Could not verify blockchain votes for {candidate.name}: {str(e)}', 'warning')
                    
                    results[election_year.id]['elections'][-1]['candidates'].append({
                        'name': candidate.name,
                        'votes': db_vote_count,
                        'chain_votes': chain_vote_count
                    })
                    results[election_year.id]['elections'][-1]['total_votes'] += db_vote_count
                    results[election_year.id]['total_votes'] += db_vote_count
        else:
            results[election_year.id] = {
                'title': election_year.title,
                'start_date': formatted_start_date,
                'end_date': formatted_end_date,
                'status': 'ongoing' if current_time >= start_date_ist else 'upcoming'
            }
    
    # Convert datetime objects to strings for JavaScript
    for election_year_id, data in results.items():
        if isinstance(data.get('start_date', ''), datetime):
            data['start_date'] = data['start_date'].strftime('%Y-%m-%d %H:%M')
        if isinstance(data.get('end_date', ''), datetime):
            data['end_date'] = data['end_date'].strftime('%Y-%m-%d %H:%M')
        
        for election in data.get('elections', []):
            for candidate in election.get('candidates', []):
                candidate['votes'] = int(candidate['votes'])
                candidate['chain_votes'] = int(candidate['chain_votes'])
    
    return render_template('election/results.html', 
                          results=results,
                          current_time=current_time.isoformat())

# Add admin verification routes
@app.route('/admin/verify-users')
@login_required
@admin_required
def verify_users():
    pending_users = User.query.filter_by(is_verified=False, is_admin=False).all()
    return render_template('admin/verify_users.html', users=pending_users)

@app.route('/admin/verify_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def verify_user(user_id):
    user = User.query.get_or_404(user_id)
    action = request.form.get('action')
    
    if action == 'approve':
        user.is_verified = True
        db.session.commit()
        flash(f'User {user.username} has been verified.')
    elif action == 'reject':
        # Delete the ID card image
        if user.id_card_image:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], user.id_card_image))
            except:
                pass
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} has been rejected and removed.')
    
    return redirect(url_for('verify_users'))

@app.route('/admin/verify-votes')
@login_required
@admin_required
def verify_all_votes():
    try:
        contract = get_contract()
        elections = Election.query.all()
        mismatches = []
        
        for election in elections:
            for candidate in election.candidates:
                db_votes = Vote.query.filter_by(candidate_id=candidate.id).count()
                chain_votes = contract.functions.getVoteCount(election.id, candidate.id).call()
                
                if db_votes != chain_votes:
                    mismatches.append({
                        'election': election.post.title,
                        'candidate': candidate.name,
                        'db_votes': db_votes,
                        'chain_votes': chain_votes
                    })
        
        if mismatches:
            flash('Vote count mismatches found. Please check the details below.', 'warning')
            return render_template('admin/vote_verification.html', mismatches=mismatches)
        else:
            flash('All vote counts verified successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
            
    except Exception as e:
        flash(f'Error verifying votes: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)