from flask import Flask, render_template

# Initialize the Flask application
app = Flask(__name__)

# Define the route for the main page (the root URL '/')
@app.route('/')
def home():
    """
    Renders the 'index.html' file when a user accesses the root URL.
    Flask automatically looks for template files in a 'templates' folder.
    """
    return render_template('guest.html')

@app.route('/about')
def about():
    """
    Renders the 'about.html' file when a user accesses the '/about' URL.
    Flask automatically looks for template files in a 'templates' folder.
    """
    return render_template('about.html')

@app.route('/user_home')
def user_home():
    """
    Renders the 'user_home.html' file when a user accesses the '/user_home' URL.
    Flask automatically looks for template files in a 'templates' folder.
    """
    return render_template('user_home.html')

@app.route('/admin')
def admin():
    """
    Renders the 'admin.html' file when a user accesses the '/admin' URL.
    Flask automatically looks for template files in a 'templates' folder.
    """
    return render_template('admin.html')

@app.route('/login_redirect')
def login_redirect():
    """
    Renders the 'login_redirect.html' file when a user accesses the '/login_redirect' URL.
    Flask automatically looks for template files in a 'templates' folder.
    """
    return render_template('login_redirect.html')

@app.route('/login')
def login():
    """
    Renders the 'login.html' file when a user accesses the '/login' URL.
    Flask automatically looks for template files in a 'templates' folder.
    """
    return render_template('login.html')

@app.route('/user_account')
def user_account():
    """
    Renders the 'user_account.html' file when a user accesses the '/user_account' URL.
    Flask automatically looks for template files in a 'templates' folder.
    """
    return render_template('user_account.html')

# Run the application
if __name__ == '__main__':
    # Setting debug=True allows for automatic reloading when code changes
    # and provides helpful error messages in the browser.
    app.run(debug=True)