import requests
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import sys
from datetime import datetime
import os

from DatabaseModule.Database.database_stub import WebAppDatabaseStub


CLIENTID = 6789
# Create the Flask application instance
app = Flask(__name__)
stub = WebAppDatabaseStub()
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'secret')

@app.route('/', methods=['GET'])
def guest():
    if check_logged_in():
        return render_template('user_account.html')
    return render_template('guest.html')

@app.route('/about', methods=['GET'])
def about():
    return render_template('about.html')

@app.route('/user_home', methods=['GET'])
def user_home():
    if not check_logged_in():
        return render_template("login_redirect.html"), 401

    account = session.get("account")
    return render_template("user_home.html", account=account)

@app.route('/login', methods=['GET'])
def login():
    if check_logged_in():
        return user_home()
    auth_url = (
        f"http://localhost:5001/login"
        f"?response_type=code"
        f"&redirect_uri=http://127.0.0.1:5000/callback"
    )
    return redirect(auth_url)

@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect("/")

@app.route('/user_account', methods=['GET'])
def user_account():
    if not check_logged_in():
        return render_template("login_redirect.html"), 401

    account = session["account"]
    return render_template("user_account.html", account=account)

@app.route('/admin_account', methods=['GET'])
def admin_account():
    return render_template('admin_account.html')

@app.route('/callback', methods=['GET'])
def callback():
    #MAKES SURE USER HAS CORRECT PERMISSIONS!
    #based on the UID (which it verifies is correct with auth server)
    #based on the page it is trying to reach (based on buttons the user has pressed)
    #redirects to the page they
    code = request.args.get("code")
    account = request.args.get("account")

    if not code or not account:
        return render_template("login_redirect.html")

    valid = check_key(code, account)
    if valid != 1:
        session.clear()
        return render_template("login_redirect.html"), 401

    session["logged_in"] = True
    session["account"] = account

    if session["account"] == "admin":
        return redirect(url_for("admin_account"))
    return redirect(url_for("user_home"))

def check_logged_in():
    if not session.get("logged_in"):
        return False
    if not session.get("account"):
        return False
    return True

##################### WEBPAGE FUNCTIONALITY ########################################

@app.route('/data', methods=["POST"])
def data():
    params = request.get_json()
    print(params)
    needed_id = params["id"]
    if needed_id is None:
        print("GAHHHHH SOMETHING BROKE")
    #SECURITY GOES HERE!    
    return stub.read_acoustic_data(my_id=needed_id)

@app.route('/populate_databox', methods=['POST'])
def populate_databox():
    params = request.get_json()

    owner=params['page']

    datalist = params['datalist']

    print("DATALIST =", datalist)
    print("OWNER =", owner)

    if owner is None:
        return {f"Error": "owner is None"}, 400
    if datalist is None:
        return {f"Error": "datalist is None"}, 400
    #if guest page asking, use the stub to get all acoustic data whose "restricted"
    #value is 0
    if owner == "guest" and datalist == "guest":
        received_data = stub.read_acoustic_data(restricted=False) #TODO: CHANGE THIS TO FALSE FOR PRODUCTION
        print(f"I am returning: {received_data}")
        return received_data

    #everything but the guest page loading requires authentication
    if not check_logged_in():
        return {f"Error": "logged_in == False"}, 401

    #user_home guest dataset:
    if owner == "user_home" and datalist == "guest":
        received_data = stub.read_acoustic_data(restricted=True)  # TODO: CHANGE THIS TO FALSE FOR PRODUCTION
        return jsonify(received_data)

    #user_home restricted dataset
    if owner == "user_home" and datalist == session["account"]:

        received_data = stub.read_user_data(user=session["account"])
        #stub.read_acoustic_data(user=datalist) # TODO: DatabaseStub needs to be updated with this functionality!
        return jsonify(received_data)


    return {"error": "invalid database queries"}, 400

@app.route('/request_data_auth', methods=['POST'])
def request_data_auth():
    params = request.get_json()
    start_time = params["start_time"]
    end_time = params["end_time"]
    username = session["account"]

    print("START =", start_time)
    print("END =", end_time)
    stub.add_user_request(username, start_time, end_time)
    return {"Response": "Input received"}

# function to check if the given key is valid.
# params:
#   key: the key received from the request
#   account: the username of the account in str form
# returns:
#   0: key not valid
#   1: key valid
#   2: error occurred#
def check_key(code, uname):
    print(f"server: user_account: {code}")
    auth_data = None
    # send a request to auth server to validate code
    try:
        response = requests.get(f"http://localhost:5001/validate?code={code}&username={uname}")

        response.raise_for_status()
        try:
            auth_data = response.json()
        except ValueError:
            return 2

    except requests.exceptions.HTTPError as e:
        return 2
    print(auth_data)
    if auth_data.get("valid") == 1:
        return 1
    else:
        return 0


# Run the application
if __name__ == '__main__':
    app.run(debug=True)