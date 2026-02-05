from flask import Flask, render_template, request, redirect
import sys
from datetime import datetime
from auth_stub import AuthDbStubTest

from DatabaseModule.Database.database_stub import WebAppDatabaseStub



# Create the Flask application instance
app = Flask(__name__)
stub = AuthDbStubTest()

# ###################### AUTH SERVER REDIRECTS ########################################
@app.route('/', methods=['GET'])

@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')

@app.route('/login_redirect', methods=['GET'])
def login_redirect():
    return render_template('login_redirect.html')

##################### AUTH SERVER FUNCTIONALITY ########################################
@app.route('/login_test', methods=['POST'])
def login_test():
    uname = request.form['username']
    password = request.form['password']
    if stub.login_test(uname, password) == 1:
        #TODO: when you create a key it changes the "password" section of the
        #TODO: database. This makes all other login attempts fail.
        return_url = (
            f"http://localhost:5000/user_account"
            f"?code={stub.create_key(uname, password)}"
            f"&redirect_uri=http://127.0.0.1:5000/callback"
        )
        return redirect(return_url)
    else:
        #TODO: CHANGE THIS TO REDIRECT TO THE login_redirect() PAGE
        return_url = (
            f"http://localhost:5001/login_redirect"
        )
        return redirect(return_url)


@app.route('/create_acount', methods=['POST'])
def create_acount():
    uname = request.form['username']
    password = request.form['password']
    print(uname, password)

@app.route('/validate', methods=['GET'])
def validate():
    code = request.args['code']
    return str(stub.validate_key(code))



# Run the application
if __name__ == '__main__':
    app.run(debug=True, port=5001)