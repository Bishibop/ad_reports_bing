from __future__ import print_function
from flask import Flask, redirect, request, session
from flask_environments import Environments
from flask_sqlalchemy import SQLAlchemy
from bingads import *
from bingads.bulk import *
from datetime import date, datetime, timedelta
import os, click

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db = SQLAlchemy(app)

# Has to be after assignment of db, because models.py needs it
from models import Customers, Clients, BingadsReports
import reports

def register(customer_id):
    session['customer_id'] = customer_id
    oauth_web_auth_code_grant = generate_authenticator()
    return redirect(oauth_web_auth_code_grant.get_authorization_endpoint())

@app.route("/<customer_id>")
def register_from_customer(customer_id):
    session['came_from'] = 'customer'
    return register(customer_id)

@app.route("/admin/<customer_id>")
def register_from_admin(customer_id):
    session['came_from'] = 'admin'
    return register(customer_id)

@app.route("/callback")
def callback():
    customer = Customers.query.get(session.pop('customer_id', None))

    oauth_web_auth_code_grant = generate_authenticator()
    oauth_web_auth_code_grant.request_oauth_tokens_by_response_uri(request.url)
    oauth_tokens = oauth_web_auth_code_grant.oauth_tokens

    access_token = oauth_tokens.access_token
    refresh_token = oauth_tokens.refresh_token
    expires_in_seconds = oauth_tokens.access_token_expires_in_seconds

    # Bing doesn't give you an issued_at time,
    # so I just made it a bit before we received the response.
    # We do this, rather than 'expires_at', to mirror AdWords' OAuth2 implementation.
    issued_at = datetime.now() - timedelta(seconds=15)

    customer.bing_ads_access_token = access_token
    customer.bing_ads_refresh_token = refresh_token
    customer.bing_ads_expires_in_seconds = expires_in_seconds
    customer.bing_ads_issued_at = issued_at

    db.session.commit()

    if session.pop('came_from', None) == 'admin':
        return redirect(os.environ.get('MAIN_APP_URL') + '/customers/' + str(customer.id) + '/api_permissions')
    else:
        return redirect(os.environ.get('MAIN_APP_URL') + '/api_permissions')

def generate_authenticator():
    return OAuthWebAuthCodeGrant(
        client_id=os.environ.get('BING_CLIENT_ID'),
        client_secret=os.environ.get('BING_CLIENT_SECRET'),
        redirection_uri=os.environ.get('BING_CALLBACK_URL')
    )

@app.cli.command()
@click.option('--days', default=2)
def request_daily_reports(days):
    client = Clients.query.filter_by(name="McGeorge's Rolling Hills RV").first()
    start_date = date.today() - timedelta(days=(days-1))
    reports.request_metrics_reports(client, start_date, date.today())
    reports.request_queries_reports(client, start_date, date.today())

@app.cli.command()
@click.option('--days', default=2)
def request_metrics_for_mcgeorges(days):
    client = Clients.query.filter_by(name="McGeorge's Rolling Hills RV").first()
    start_date = date.today() - timedelta(days=(days-1))
    reports.request_metrics_reports(client, start_date, date.today())

@app.cli.command()
@click.option('--days', default=2)
def request_queries_for_mcgeorges(days):
    client = Clients.query.filter_by(name="McGeorge's Rolling Hills RV").first()
    start_date = date.today() - timedelta(days=(days-1))
    reports.request_queries_reports(client, start_date, date.today())

@app.cli.command()
def request_all_queries_for_mcgeorges():
    client = Clients.query.filter_by(name="McGeorge's Rolling Hills RV").first()
    start_date = client.bingads_reports.order_by(BingadsReports.date).first().date
    end_date = client.bingads_reports.filter_by(query_clicks=None).order_by(BingadsReports.date).last().date
    reports.request_queries_reports(client, start_date, end_date)

app.secret_key = os.environ.get('FLASK_SECRET_KEY')

if __name__ == "__main__":
    app.run()
