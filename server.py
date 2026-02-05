import requests
from flask import Flask, render_template, request, redirect
import sys
from datetime import datetime

from DatabaseModule.Database.database_stub import WebAppDatabaseStub


CLIENTID = 6789
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
    # code = json.loads(request.args.get('code'))
#     # if pswd_stub.is_this_code_right(code) == True:
#     #     return render_template('user_home.html')
#     # else:
#     #     return render_template('guest.html')
    return render_template('guest.html')

@app.route('/login', methods=['GET'])
def login():
    auth_url = (
        f"http://localhost:5001/login"
        f"?response_type=code"
        f"&redirect_uri=http://127.0.0.1:5000/callback"
    )
    return redirect(auth_url)

@app.route('/user_account', methods=['GET'])
def user_account():
    key = request.args["code"]
    print(f"server: user_account: {key}")
    auth_data = None
    #send a request to auth server to validate code
    try:
        response = requests.get(f"http://localhost:5001/validate?code={key}")

        response.raise_for_status()
        try:
            auth_data = response.json()
        except ValueError:
            print("Invalid response")

    except requests.exceptions.HTTPError as e:
        return "We encountered an authentication error", 500
    print(f"server: data: {auth_data}")
    if auth_data == 1:
        return render_template('user_account.html')
    return render_template('guest.html')

@app.route('/admin_account', methods=['GET'])
def admin_account():
    return render_template('admin_account')

@app.route('/callback', methods=['GET'])
def callback():
    #MAKES SURE USER HAS CORRECT PERMISSIONS!
    #based on the UID (which it verifies is correct with auth server)
    #based on the page it is trying to reach (based on buttons the user has pressed)
    #redirects to the page they want
    pass
##################### WEBPAGE FUNCTIONALITY ########################################

@app.route('/data', methods=["POST"])
def data():
    params = request.get_json()
    needed_id = params["id"]
    if needed_id == None:
        print("GAHHHHH SOMETHING BROKE")
    #SECURITY GOES HERE!    
    data = stub.read_acoustic_data(my_id=needed_id)
    return data

@app.route('/populate_databox', methods=['POST'])
def populate_databox():
    params = request.get_json()
    owner=params['page']
    datalist = params['datalist']
    if owner == None:
        return f"Error: owner is None"
    if datalist == None:
        return f"Error: datalist is None"
    #if guest page asking, use the stub to get all acoustic data whose "restricted"
    #value is 0
    if owner == "guest":
        data = stub.read_acoustic_data(restricted=True) #NOTE: CHANGE THIS TO FALSE FOR PRODUCTION
        return data

@app.route('/password_request', methods=['POST'])
def password_request():
    #get params
    #use stub to ask pwd database to login
    #return the reply(with code)
    pass




# Run the application
if __name__ == '__main__':
    app.run(debug=True)