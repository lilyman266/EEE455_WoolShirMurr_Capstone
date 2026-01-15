from flask import Flask, render_template, request
import sys
from datetime import datetime

from EEE455_WoolShirMurr_Capstone.DatabaseModule.Database.database_stub import WebAppDatabaseStub

sys.path.append('./../DatabaseModule/Database')
from database_stub import WebAppDatabaseStub

# Create the Flask application instance
app = Flask(__name__)
stub = WebAppDatabaseStub()

# ###################### WEBPAGE REDIRECTS ########################################
@app.route('/', methods=['GET'])
def guest():
    return render_template('guest.html')

@app.route('/about', methods=['GET'])
def about():
    return render_template('about.html')

@app.route('/user_home', methods=['GET'])
def user_home():
    return render_template('user_home.html')

@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')

@app.route('/login_redirect', methods=['GET'])
def login_redirect():
    return render_template('login_redirect.html')

@app.route('/user_account', methods=['GET'])
def user_account():
    return render_template('user_account.html')

@app.route('/admin_account', methods=['GET'])
def admin_account():
    return render_template('admin_account')

##################### WEBPAGE FUNCTIONALITY ########################################

@app.route('/data', methods=["POST"])
def data():
    params = request.get_json()
    start_date = params['start_date']
    end_date = params['end_date']
    if type(start_date) is datetime and type(end_date) is datetime:
        return stub.read_acoustic_data(start_time=start_date, end_time=end_date)
    #logic to confirm correct params
    if start_date is None or start_date is "":
        return f"start date was None"
    if not start_date.isnumeric():
        return f"start date must be a number"
    if int(start_date) <= 3:
        return f"start date was less than 3"
    elif int(start_date) >= 5:
        return f"start date was more than 5"
    else:
        return f"start date was 4. Try something less than 3 or more than 5."

@app.route('/populate_databox', methods=['POST'])
def populate_databox():
    params = request.get_json()
    owner=params['page']
    datalist = params['datalist']
    if owner is None:
        return f"Error: owner is None"
    if datalist is None:
        return f"Error: datalist is None"
    #if guest page asking, use the stub to get all acoustic data whose "restricted"
    #value is 0
    if owner is "guest":
        return stub.read_acoustic_data(restricted=False)

# Run the application
if __name__ == '__main__':
    app.run(debug=True)