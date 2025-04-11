from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bloodbank.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'donor' or 'staff'
    
class Donor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    blood_type = db.Column(db.String(5), nullable=False)
    contact = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    date_registered = db.Column(db.DateTime, default=datetime.utcnow)
    
class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donor.id'), nullable=False)
    donation_date = db.Column(db.DateTime, default=datetime.utcnow)
    quantity = db.Column(db.Integer, nullable=False)  # in ml
    hemoglobin = db.Column(db.Float)
    blood_pressure = db.Column(db.String(20))
    status = db.Column(db.String(20), default='available')  # available, used, expired
    
class BloodInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blood_type = db.Column(db.String(5), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)  # total quantity in ml
    donation_id = db.Column(db.Integer, db.ForeignKey('donation.id'))
    expiry_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='available')
    
# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_type'] = user.user_type
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Login failed. Check your username and password.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        
        hashed_password = generate_password_hash(password)
        
        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            user_type=user_type
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            
            if user_type == 'donor':
                return redirect(url_for('register_donor', user_id=new_user.id))
            else:
                flash('Staff account created! Please login.', 'success')
                return redirect(url_for('login'))
                
        except:
            db.session.rollback()
            flash('Error creating account. Email or username may already exist.', 'danger')
    
    return render_template('register.html')

@app.route('/register_donor/<int:user_id>', methods=['GET', 'POST'])
def register_donor(user_id):
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        blood_type = request.form['blood_type']
        contact = request.form['contact']
        address = request.form['address']
        
        new_donor = Donor(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            blood_type=blood_type,
            contact=contact,
            address=address
        )
        
        try:
            db.session.add(new_donor)
            db.session.commit()
            flash('Donor registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('Error registering donor information.', 'danger')
    
    return render_template('register_donor.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_type', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session['user_type'] == 'donor':
        donor = Donor.query.filter_by(user_id=session['user_id']).first()
        donations = Donation.query.filter_by(donor_id=donor.id).all()
        return render_template('donor_dashboard.html', donor=donor, donations=donations)
    else:
        # Staff dashboard - show blood inventory stats
        blood_inventory = {}
        for blood_type in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
            total_quantity = db.session.query(db.func.sum(BloodInventory.quantity)).filter_by(
                blood_type=blood_type, status='available').scalar() or 0
            blood_inventory[blood_type] = total_quantity
        
        recent_donations = Donation.query.order_by(Donation.donation_date.desc()).limit(10).all()
        return render_template('staff_dashboard.html', blood_inventory=blood_inventory, recent_donations=recent_donations)

@app.route('/donate', methods=['GET', 'POST'])
def donate():
    if 'user_id' not in session or session['user_type'] != 'donor':
        return redirect(url_for('login'))
    
    donor = Donor.query.filter_by(user_id=session['user_id']).first()
    
    if request.method == 'POST':
        quantity = int(request.form['quantity'])
        hemoglobin = float(request.form['hemoglobin'])
        blood_pressure = request.form['blood_pressure']
        
        new_donation = Donation(
            donor_id=donor.id,
            quantity=quantity,
            hemoglobin=hemoglobin,
            blood_pressure=blood_pressure,
            status='available'
        )
        
        try:
            db.session.add(new_donation)
            db.session.commit()
            
            # Update inventory
            from datetime import timedelta
            expiry_date = datetime.utcnow() + timedelta(days=42)  # Blood expires in 42 days
            
            new_inventory = BloodInventory(
                blood_type=donor.blood_type,
                quantity=quantity,
                donation_id=new_donation.id,
                expiry_date=expiry_date,
                status='available'
            )
            
            db.session.add(new_inventory)
            db.session.commit()
            
            flash('Donation recorded successfully!', 'success')
            return redirect(url_for('dashboard'))
        except:
            db.session.rollback()
            flash('Error recording donation.', 'danger')
    
    return render_template('donate.html', donor=donor)

@app.route('/inventory')
def inventory():
    if 'user_id' not in session or session['user_type'] != 'staff':
        return redirect(url_for('login'))
    
    inventory_items = BloodInventory.query.filter_by(status='available').order_by(BloodInventory.expiry_date).all()
    return render_template('inventory.html', inventory=inventory_items)

@app.route('/search_blood', methods=['GET', 'POST'])
def search_blood():
    if 'user_id' not in session or session['user_type'] != 'staff':
        return redirect(url_for('login'))
    
    blood_type = None
    inventory_items = []
    
    if request.method == 'POST':
        blood_type = request.form['blood_type']
        inventory_items = BloodInventory.query.filter_by(blood_type=blood_type, status='available').order_by(BloodInventory.expiry_date).all()
    
    return render_template('search_blood.html', inventory=inventory_items, blood_type=blood_type)

@app.route('/use_blood/<int:inventory_id>', methods=['POST'])
def use_blood(inventory_id):
    if 'user_id' not in session or session['user_type'] != 'staff':
        return redirect(url_for('login'))
    
    inventory_item = BloodInventory.query.get_or_404(inventory_id)
    inventory_item.status = 'used'
    
    # Also update the donation status
    donation = Donation.query.get(inventory_item.donation_id)
    if donation:
        donation.status = 'used'
    
    try:
        db.session.commit()
        flash('Blood marked as used successfully!', 'success')
    except:
        db.session.rollback()
        flash('Error updating blood status.', 'danger')
    
    return redirect(url_for('inventory'))

@app.route('/api/inventory_stats')
def inventory_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    stats = {}
    for blood_type in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']:
        total = db.session.query(db.func.sum(BloodInventory.quantity)).filter_by(
            blood_type=blood_type, status='available').scalar() or 0
        stats[blood_type] = total
    
    return jsonify(stats)

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/learn')
def learn():
    return render_template('learn.html')

@app.route('/request_blood', methods=['POST'])
def request_blood():
    if 'user_id' not in session or session['user_type'] != 'staff':
        return redirect(url_for('login'))

    req_blood_type = request.form['req_blood_type']
    quantity = request.form['quantity']
    urgency = request.form['urgency']
    patient_name = request.form['patient_name']
    hospital = request.form['hospital']
    notes = request.form['notes']

    flash(f'Request for {quantity} ml of {req_blood_type} blood submitted successfully for {patient_name}.', 'success')
    
    return redirect(url_for('search_blood'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5002)