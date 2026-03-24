from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import insert_donor, find_donor_by_phone, search_donors, get_all_donors

app = Flask(__name__)
app.secret_key = "life_flow_secret"

# Store active emergency alerts and simulated notification status
emergency_alerts = []
emergency_active = False
emergency_info = {}


def distance_label(user_location, donor_location):
    if not user_location or not donor_location:
        return 'Far'
    u = user_location.strip().lower()
    d = donor_location.strip().lower()
    if u == d or u in d or d in u:
        return 'Near'
    if u.split()[0] == d.split()[0]:
        return 'Medium'
    return 'Far'


def eligibility_status(last_donation_date):
    from datetime import datetime, timedelta
    if not last_donation_date:
        return 'Eligible'
    try:
        last = datetime.strptime(last_donation_date, '%Y-%m-%d')
    except ValueError:
        return 'Unknown'
    return 'Eligible' if datetime.now() - last >= timedelta(days=90) else 'Not eligible'


def donor_badges(donor):
    badges = []
    if donor.get('type') == 'volunteer':
        badges.append('Volunteer Donor')
    if donor.get('verified'):
        badges.append('Verified Donor')
    dc = int(donor.get('donation_count', 0))
    if dc >= 3:
        badges.append('Frequent Donor')
    if dc <= 1:
        badges.append('New Donor')
    return badges


@app.route('/')
def home():
    donors = get_all_donors()
    total_donors = len(donors)
    available_donors = len([d for d in donors if d.get('availability', '').lower() == 'available'])
    rare_donors = len([d for d in donors if d.get('blood_group', '').upper() in ('O-', 'AB-', 'B-', 'A-')])
    emergency_count = len(emergency_alerts)
    return render_template('home.html', donors=donors, emergency_alerts=emergency_alerts,
                           emergency_active=emergency_active, emergency_info=emergency_info,
                           total_donors=total_donors, available_donors=available_donors,
                           rare_donors=rare_donors, emergency_count=emergency_count)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        blood_group = request.form.get('blood_group', '').strip().upper()
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()
        availability = request.form.get('availability', 'Available')
        donor_type = request.form.get('type', 'regular')
        last_donation_date = request.form.get('last_donation_date', '').strip()

        if not (name and blood_group and phone and location):
            flash('All fields are required.', 'error')
            return redirect(url_for('register'))

        existing = find_donor_by_phone(phone)
        if existing:
            flash('Phone number already registered. Update your donor info.', 'error')
            return redirect(url_for('register'))

        insert_donor({
            'name': name,
            'blood_group': blood_group,
            'phone': phone,
            'location': location,
            'availability': availability,
            'type': donor_type,
            'last_donation_date': last_donation_date,
            'donation_count': 1,
            'verified': False
        })
        flash('Donor registered successfully!', 'success')
        return redirect(url_for('home'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        donor = find_donor_by_phone(phone)
        if donor:
            flash('Login successful. Welcome back, {}!'.format(donor.get('name')), 'success')
            return redirect(url_for('home'))
        flash('No donor found with this phone number.', 'error')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    results = []
    query = ''
    location = ''
    donor_count = 0
    is_emergency = False
    search_elsewhere = False
    
    if request.method == 'POST':
        query = request.form.get('blood_group', '').strip().upper()
        location = request.form.get('location', '').strip().lower()
        is_emergency = request.form.get('emergency') == 'on'
        
        if request.form.get('search_elsewhere'):
            # Handle search elsewhere
            new_location = request.form.get('new_location', '').strip().lower()
            if new_location:
                location = new_location
                search_elsewhere = True
        
        results = search_donors(query, location, available_only=True,
                                emergency_priority=is_emergency, ai_priority=True,
                                user_location=location)
        donor_count = len(results)

        # Enrich results with distance/eligibility/badges
        for d in results:
            d['distance_label'] = distance_label(location, d.get('location', ''))
            d['eligibility'] = eligibility_status(d.get('last_donation_date', ''))
            d['badges'] = donor_badges(d)

        if donor_count > 0:
            flash(f'{donor_count} donors found near you', 'success')

        if not results and not search_elsewhere:
            flash('No available donors found for this blood group and location.', 'info')
    
    return render_template('search.html', donors=results, query=query, location=location, 
                         donor_count=donor_count, is_emergency=is_emergency, 
                         search_elsewhere=search_elsewhere)

@app.route('/volunteer')
def volunteer():
    return render_template('register.html', volunteer_mode=True)

@app.route('/hospital_dashboard')
def hospital_dashboard():
    donors = get_all_donors()
    total_donors = len(donors)
    available_donors = len([d for d in donors if d.get('availability', '').lower() == 'available'])
    emergency_requests = len(emergency_alerts)
    rare_donors = len([d for d in donors if d.get('blood_group', '').upper() in ('O-', 'AB-', 'B-', 'A-')])
    return render_template('hospital_dashboard.html', donors=donors, total_donors=total_donors,
                           available_donors=available_donors, emergency_requests=emergency_requests,
                           rare_donors=rare_donors)

@app.route('/emergency', methods=['GET', 'POST'])
def emergency():
    global emergency_active, emergency_info
    message = ''
    matching = []
    if request.method == 'POST':
        blood_group = request.form.get('blood_group', '').strip().upper()
        location = request.form.get('location', '').strip().lower()
        message = 'Emergency alert: Need {} blood in {}. Please reach out to available donors.'.format(blood_group, location.title())

        matching = search_donors(blood_group, location, available_only=True, emergency_priority=True)
        donor_count = len(matching)

        emergency_active = True
        emergency_info = {
            'blood_group': blood_group,
            'location': location.title(),
            'nearby_donors': donor_count
        }

        # Add to emergency alerts for history/dashboard
        emergency_alerts.append({
            'blood_group': blood_group,
            'location': location,
            'message': message,
            'timestamp': 'now'  # Simple timestamp
        })

        # Flash simulation messages
        flash('Emergency alert created', 'warning')
        flash(f'Nearby donors found: {donor_count}', 'info')
        flash('Notification sent to nearby donors', 'success')

        if donor_count == 0:
            flash('No available donors matched the emergency request.', 'danger')

    return render_template('emergency.html', message=message, matching=matching)

@app.route('/hospital_login', methods=['GET', 'POST'])
def hospital_login():
    if request.method == 'POST':
        hospital_id = request.form.get('hospital_id', '').strip()
        password = request.form.get('password', '').strip()
        
        # Simple authentication (in real app, use proper auth)
        if hospital_id == 'admin' and password == 'admin':
            flash('Hospital login successful! You can now coordinate donations.', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid hospital credentials.', 'error')
            return redirect(url_for('hospital_login'))
    
    return render_template('hospital_login.html')

@app.route('/api/donors', methods=['GET'])
def api_donors():
    donors = get_all_donors()
    return jsonify(donors)

if __name__ == '__main__':
    app.run(debug=True)
