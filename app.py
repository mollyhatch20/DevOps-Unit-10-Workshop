from azure.monitor.opentelemetry import configure_azure_monitor

# Configure Azure Monitor telemetry collection
configure_azure_monitor()

# Now import flask after configuring Azure Monitor
from flask import Flask, render_template, request
from datetime import datetime, timezone
import requests
import logging
from werkzeug.utils import redirect
from flask_config import Config
from data.database import initialise_database, add_order, clear_orders, count_orders, get_orders_to_display, get_queued_count, get_recently_placed_count, get_recently_processed_count
from scheduled_jobs import initialise_scheduled_jobs
from products import create_product_download

# Configure logging to send logs to Azure Monitor
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize Database and Scheduled Jobs
initialise_database(app)
initialise_scheduled_jobs(app)

@app.route("/")
def index():
    orders = get_orders_to_display()
    queue_count = get_queued_count()
    recently_placed_count = get_recently_placed_count()
    recently_processed_count = get_recently_processed_count()
    scenarios = [
        { 'display': 'Add broken order', 'value': 'BrokenOrder' },
        { 'display': 'Monitoring Load', 'value': 'HighLoad' },
        { 'display': 'Queue Reliability', 'value': 'UnreliableProcessing' },
        { 'display': 'System Monitoring', 'value': 'VeryHighLoad' },
        { 'display': 'Reset to initial', 'value': 'Reset' }
    ]

    return render_template(
        "layout.html", orders=orders, queue_count=queue_count, recently_placed_count=recently_placed_count,
        recently_processed_count=recently_processed_count, scenarios=scenarios
    )

@app.route("/count")
def count():
    return { 'count': count_orders() }

@app.route("/new", methods=["POST"])
def new_order():
    product = request.json["product"]
    customer = request.json["customer"]
    date_placed = request.json["date_placed"] or datetime.now(tz=timezone.utc)
    download = create_product_download(product)
    try:
        order = add_order(product, customer, date_placed, None, download)
        # Log the order creation
        logging.info(f"Added new order: {order}")
    except Exception as e:
        # Log any error that occurs
        logging.error(f"Error adding new order: {str(e)}")
        return str(e)

    return f"Added: {order}"

@app.route("/scenario", methods=["POST"])
def set_scenario():
    scenario = request.form["scenario"]

    if scenario == 'BrokenOrder':
        product = 'Product from the future'
        download = create_product_download(product)
        add_order('Product from the future', 'Me', '3000-01-01T12:00:00Z', None, download)
        return redirect('/')

    if scenario == 'Reset':
        clear_orders()

    try:
        response = requests.post(
            app.config["FINANCE_PACKAGE_URL"] + "/scenario",
            json=scenario
        )
        response.raise_for_status()
        # Log successful response from the finance package
        logging.info(f"Scenario response: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to set scenario: {str(e)}")
        return str(e)

    return redirect('/')

if __name__ == "__main__":
    app.run()