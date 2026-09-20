import datetime
import os
import requests
from math import radians, sin, cos, sqrt, atan2
from data_setup import people, dbsetup
import mysql.connector
from email_api import send_email
from countries import countries_dict

LATEST_COMP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'latest_comp.txt')

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth radius in kilometers

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c
    return distance

if __name__ == "__main__":
    event_names = {
        "222": "2x2x2 Cube",
        "333": "3x3x3 Cube",
        "333bf": "3x3x3 Blindfolded",
        "333fm": "3x3x3 Fewest Moves",
        "333ft": "3x3x3 With Feet",
        "333mbf": "3x3x3 Multi-Blind",
        "333mbo": "3x3x3 Multi-Blind Old Style",
        "333oh": "3x3x3 One-Handed",
        "444": "4x4x4 Cube",
        "444bf": "4x4x4 Blindfolded",
        "555": "5x5x5 Cube",
        "555bf": "5x5x5 Blindfolded",
        "666": "6x6x6 Cube",
        "777": "7x7x7 Cube",
        "clock": "Clock",
        "magic": "Magic",
        "minx": "Megaminx",
        "mmagic": "Master Magic",
        "pyram": "Pyraminx",
        "skewb": "Skewb",
        "sq1": "Square-1"
    }

    page = 1

    params = {
        'include_cancelled': 'false',
        'sort': '-announced_at,name',
        'page': page
    }
    found_end = False

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    yesterday = now - datetime.timedelta(days=1, hours=1) # the cron job running before can take different amounts of time, the db grows etc. 
    week_ago = now - datetime.timedelta(days=7) # guard in case the saved competition disappears from the listing

    last_comp_id = None
    if os.path.exists(LATEST_COMP_FILE):
        with open(LATEST_COMP_FILE, 'r') as f:
            last_comp_id = f.read().strip() or None

    all_new_comps = []

    while not found_end:
        print(f"Processing page {page}")
        params['page'] = page
        response = requests.get('https://www.worldcubeassociation.org/api/v0/competitions', params=params)
        competitions = response.json()

        for comp in competitions:
            announced_at = datetime.datetime.fromisoformat(comp['announced_at'])
            if announced_at < week_ago:
                found_end = True
                break
            if last_comp_id and comp['id'] == last_comp_id:
                found_end = True
                break
            if not last_comp_id and announced_at < yesterday:
                found_end = True
                break
            all_new_comps.append(comp)
                
        page += 1

    mydb = None
    if dbsetup['SECRET_PASSWORD']:
        mydb = mysql.connector.connect(host = dbsetup['SECRET_HOST'], user = dbsetup['SECRET_USER'], database = dbsetup['SECRET_DATABASE'], password = dbsetup['SECRET_PASSWORD'])
    else:
        mydb = mysql.connector.connect(host = dbsetup['SECRET_HOST'], user = dbsetup['SECRET_USER'], database = dbsetup['SECRET_DATABASE'])
    cursor = mydb.cursor()

    for person in people:
        query = f'select iso2 from countries where id in (select distinct country_id from competitions where id in (select distinct competition_id from results where person_id = "{person['wca_id']}"));'
        cursor.execute(query)
        person_countries = [result[0] for result in cursor.fetchall()]

        new_comps_in_range = []
        new_countires_in_range = []
    
        for comp in all_new_comps:
            distance = haversine(person['lat'], person['lon'], comp['latitude_degrees'], comp['longitude_degrees'])
            if distance <= person['range']:
                if comp['country_iso2'] not in person_countries:
                    new_countires_in_range.append(comp)
                else:
                    new_comps_in_range.append(comp)
        
        email_body = ""
        email_body_html = ""
        if new_countires_in_range:
            email_body_html += "New competitions in new countries:<br>"
            email_body += "New competitions in new countries:\n"
            for comp in new_countires_in_range:
                email_body_html += f'- <a href="https://www.worldcubeassociation.org/competitions/{comp['id']}">{comp['name']}</a> ({comp['city']}, {countries_dict[comp['country_iso2']]})<br>'
                email_body_html += f'  Dates: {comp['start_date']} to {comp['end_date']}<br>'
                email_body_html += f'  Events : {', '.join([event_names[event] for event in comp['event_ids']])}<br>'
                email_body += f'- {comp['name']} ({comp['city']}, {countries_dict[comp['country_iso2']]})\n'
                email_body += f'  Dates: {comp['start_date']} to {comp['end_date']}\n'
                email_body += f'  Events : {', '.join([event_names[event] for event in comp['event_ids']])}\n'
            email_body_html += "<br>"
            email_body += '\n'


        if new_comps_in_range:
            email_body_html += "New competitions in range:<br>"
            email_body += "New competitions in range:\n"
            for comp in new_comps_in_range:
                email_body_html += f'- <a href="https://www.worldcubeassociation.org/competitions/{comp['id']}">{comp['name']}</a> ({comp['city']}, {countries_dict[comp['country_iso2']]})<br>'
                email_body_html += f'  Dates: {comp['start_date']} to {comp['end_date']}<br>'
                email_body_html += f'  Events : {', '.join([event_names[event] for event in comp['event_ids']])}<br>'
                email_body += f'- {comp['name']} ({comp['city']}, {countries_dict[comp['country_iso2']]})\n'
                email_body += f'  Dates: {comp['start_date']} to {comp['end_date']}\n'
                email_body += f'  Events : {', '.join([event_names[event] for event in comp['event_ids']])}\n'
            email_body_html += "<br>"
            email_body += '\n'

        print(email_body)
        if email_body:
            send_email(person['email'], person['name'], 'New competitions ' + datetime.datetime.now().strftime('%Y-%m-%d'), email_body, email_body_html)

    if all_new_comps:
        with open(LATEST_COMP_FILE, 'w') as f:
            f.write(all_new_comps[0]['id'])
