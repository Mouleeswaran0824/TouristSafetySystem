from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file,
    jsonify
)

import os
from io import BytesIO

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


# ============================================================
# CONNECT TO SUPABASE
# ============================================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "admin_secret_key"
)


# ============================================================
# ADMIN LOGIN DETAILS
# ============================================================

ADMIN_USERNAME = os.getenv(
    "ADMIN_USERNAME",
    "admin"
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "admin1234"
)


# ============================================================
# HOME PAGE - TOURIST LOGIN
# ============================================================

@app.route('/')
def home():

    return render_template(
        'login.html'
    )


# ============================================================
# TOURIST LOGIN
# ============================================================

@app.route('/login', methods=['POST'])
def login():

    username = request.form['username']
    location = request.form['location']

    tourist_data = {
        "name": username,
        "location": location
    }

    # Save tourist login data in Supabase
    supabase.table(
        "tourist_logins"
    ).insert(
        tourist_data
    ).execute()

    return render_template(
        "dashboard.html",
        username=username,
        location=location,
        status="SAFE"
    )


# ============================================================
# EMERGENCY SOS
# ============================================================

@app.route('/sos', methods=['POST'])
def sos():

    username = request.form['username']
    location = request.form['location']

    latitude = request.form.get('latitude')
    longitude = request.form.get('longitude')

    sos_data = {

        "name": username,

        "location": location,

        "latitude":
            float(latitude)
            if latitude
            else None,

        "longitude":
            float(longitude)
            if longitude
            else None,

        "status": "DANGER"
    }

    # Save SOS alert in Supabase
    supabase.table(
        "sos_alerts"
    ).insert(
        sos_data
    ).execute()

    return render_template(
        "dashboard.html",
        username=username,
        location=location,
        status="DANGER"
    )


# ============================================================
# LIVE GPS LOCATION UPDATE
# ============================================================

@app.route('/update_location', methods=['POST'])
def update_location():

    data = request.get_json()

    username = data.get("username")
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if not username:

        return jsonify({
            "status": "error",
            "message": "Username missing"
        }), 400


    # Find latest SOS alert of the tourist
    response = (

        supabase

        .table("sos_alerts")

        .select("id")

        .eq("name", username)

        .order(
            "created_at",
            desc=True
        )

        .limit(1)

        .execute()
    )


    if not response.data:

        return jsonify({
            "status": "no_alert_found"
        })


    alert_id = response.data[0]["id"]


    # Update GPS location
    supabase.table(
        "sos_alerts"
    ).update({

        "latitude": latitude,
        "longitude": longitude

    }).eq(

        "id",
        alert_id

    ).execute()


    return jsonify({
        "status": "updated"
    })


# ============================================================
# ADMIN LOGIN PAGE
# ============================================================

@app.route('/admin_login')
def admin_login():

    return render_template(
        'admin_login.html'
    )


# ============================================================
# ADMIN LOGIN CHECK
# ============================================================

@app.route(
    '/admin_login',
    methods=['POST']
)
def admin_login_post():

    username = request.form['username']
    password = request.form['password']


    if (
        username == ADMIN_USERNAME
        and
        password == ADMIN_PASSWORD
    ):

        session['admin_logged_in'] = True

        return redirect(
            url_for('admin')
        )


    return render_template(
        'admin_login.html',
        error="Invalid admin credentials"
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route('/admin')
def admin():

    if not session.get(
        'admin_logged_in'
    ):

        return redirect(
            url_for('admin_login')
        )


    # Read SOS alerts from Supabase
    response = (

        supabase

        .table("sos_alerts")

        .select("*")

        .order(
            "created_at",
            desc=True
        )

        .execute()
    )


    alerts = []


    for row in response.data:

        location_text = str(
            row.get(
                "location",
                ""
            )
        ).lower()


        latitude = row.get(
            "latitude"
        )

        longitude = row.get(
            "longitude"
        )


        # Risk Zone Calculation
        if any(

            city in location_text

            for city in [

                "chennai",
                "coimbatore",
                "bangalore",
                "kochi",
                "trivandrum",
                "madurai"

            ]

        ):

            risk_zone = "Urban"


        elif (

            latitude is not None
            and
            longitude is not None

        ):

            risk_zone = "Semi-Remote"


        else:

            risk_zone = "Remote"


        alerts.append({

            "Name":
                row.get("name"),

            "Location":
                row.get("location"),

            "Latitude":
                latitude,

            "Longitude":
                longitude,

            "Status":
                row.get("status"),

            "Time":
                row.get("created_at"),

            "RiskZone":
                risk_zone
        })


    return render_template(
        "admin.html",
        alerts=alerts
    )


# ============================================================
# GET ALERTS - AUTO REFRESH
# ============================================================

@app.route('/get_alerts')
def get_alerts():

    if not session.get(
        'admin_logged_in'
    ):

        return jsonify([])


    response = (

        supabase

        .table("sos_alerts")

        .select("*")

        .order(
            "created_at",
            desc=True
        )

        .execute()
    )


    return jsonify(
        response.data
    )


# ============================================================
# DOWNLOAD SOS REPORT
# ============================================================

@app.route('/download_sos')
def download_sos():

    if not session.get(
        'admin_logged_in'
    ):

        return redirect(
            url_for('admin_login')
        )


    # Get SOS data from Supabase
    response = (

        supabase

        .table("sos_alerts")

        .select("*")

        .order(
            "created_at",
            desc=True
        )

        .execute()
    )


    data = response.data


    if not data:

        return "No SOS data available"


    # Convert data into DataFrame
    df = pd.DataFrame(data)


    # Create Excel file in memory
    output = BytesIO()


    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="SOS Alerts"
        )


    output.seek(0)


    return send_file(

        output,

        as_attachment=True,

        download_name="SOS_Report.xlsx",

        mimetype=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route('/admin_logout')
def admin_logout():

    session.pop(
        'admin_logged_in',
        None
    )

    return redirect(
        url_for('admin_login')
    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )