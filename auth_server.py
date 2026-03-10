from flask import Flask, render_template, request, redirect, jsonify

from auth_stub import AuthDbStubTest, AuthStubUserTable

from DatabaseModule.Database.database_stub import WebAppDatabaseStub



# Create the Flask application instance
app = Flask(__name__)
stub = AuthStubUserTable()    #NOTE: COMMENT ONE OF THESE AT A TIME
#stub = AuthDbStubTest()
db_stub = WebAppDatabaseStub()

# ###################### AUTH SERVER REDIRECTS ########################################
@app.route('/', methods=['GET'])
def home():
    login()

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

    if not uname or not password:
        return redirect("/login_redirect")

    if stub.login_test(uname, password) == 1:
        return_url = (
            f"http://localhost:5000/callback"
            f"?code={stub.create_key(uname, password)}"
            f"&account={uname}"
            f"&redirect_uri=http://127.0.0.1:5000/callback"
        )
        return redirect(return_url)
    else:
        return_url = (
            f"http://localhost:5001/login_redirect"
        )
        return redirect(return_url)


@app.route('/create_account', methods=['POST'])
def create_account():
    params = request.get_json()
    uname = params['username']
    password = params['password']
    code = db_stub.create_user(user=uname, passwd=password)
    if code == 0:
        return jsonify(ok=False, message="Username already exists!")
    else:
        return jsonify(ok=True, message="Account created!")

@app.route('/validate', methods=['GET'])
def validate():
    code = request.args['code']
    username = request.args['username']
    return jsonify({"valid": stub.validate_key(code, username) })

@app.route('/guest', methods=['GET'])
def guest():
    return_url = (
                f"http://localhost:5000"
            )
    return redirect(return_url)



# Run the application
if __name__ == '__main__':
    app.run(debug=True, port=5001)
