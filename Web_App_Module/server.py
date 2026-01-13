from flask import Flask, render_template, request

# Create the Flask application instance
app = Flask(__name__)

# Define the route for the home page
@app.route('/')
def home():
    # Use render_template to look for index.html inside the 'templates' folder
    return render_template('guest.html')

@app.route('/data', methods=["POST"])
def data():
    params = request.get_json()
    start_date = params['start_date']
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

# Run the application
if __name__ == '__main__':
    app.run(debug=True)