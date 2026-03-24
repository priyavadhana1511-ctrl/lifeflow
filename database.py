donors = []

def insert_donor(data):
    # initialize fields for ranking and status
    data.setdefault('donation_count', 1)
    data.setdefault('verified', False)
    data.setdefault('last_donation_date', '')
    data.setdefault('type', 'regular')
    donors.append(data)
    return data


def get_all_donors():
    return list(donors)


def find_donor_by_phone(phone):
    for donor in donors:
        if donor.get('phone') == phone:
            return donor
    return None


def search_donors(blood_group, location, available_only=False, emergency_priority=False, ai_priority=False, user_location=''):
    results = []
    bg = blood_group.strip().upper() if blood_group else ''
    loc = location.strip().lower() if location else ''
    for donor in donors:
        if available_only and donor.get('availability', '').lower() != 'available':
            continue
        match_bg = (not bg) or donor.get('blood_group', '').upper() == bg
        match_loc = (not loc) or loc in donor.get('location', '').lower()
        if match_bg and match_loc:
            results.append(donor)

    rare_priority = {'O-': 1, 'AB-': 2, 'B-': 3, 'A-': 4}

    def sort_key(d):
        priority = []
        # emergency/rare first
        if emergency_priority:
            priority.append(rare_priority.get(d.get('blood_group', '').upper(), 100))
        else:
            priority.append(rare_priority.get(d.get('blood_group', '').upper(), 100))
        # availability first
        priority.append(0 if d.get('availability', '').lower() == 'available' else 1)
        # near location first
        dloc = d.get('location', '').lower()
        if user_location and dloc:
            if user_location == dloc or user_location in dloc or dloc in user_location:
                distance = 0
            elif user_location.split()[0] == dloc.split()[0]:
                distance = 1
            else:
                distance = 2
        else:
            distance = 2
        priority.append(distance)
        return tuple(priority)

    if ai_priority or emergency_priority:
        results.sort(key=sort_key)

    return results

