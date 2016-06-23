from __future__ import print_function
from flask import Flask, redirect, request, session
from flask_environments import Environments
from flask_sqlalchemy import SQLAlchemy
from bingads import *
from bingads.bulk import *
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db = SQLAlchemy(app)

class Customers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    bing_ads_access_token = db.Column(db.String)
    bing_ads_refresh_token = db.Column(db.String)
    bing_ads_issued_at = db.Column(db.DateTime)
    bing_ads_expires_in_seconds = dbColumn(db.Integer)

@app.route("/<customer_id>")
def register(customer_id):
    session['customer_id'] = customer_id
    oauth_web_auth_code_grant = generate_authenticator()
    return redirect(oauth_web_auth_code_grant.get_authorization_endpoint())

@app.route("/callback")
def callback():
    customer = Customers.query.get(session.pop('customer_id', None))

    oauth_web_auth_code_grant = generate_authenticator()
    oauth_web_auth_code_grant.request_oauth_tokens_by_response_uri(request.url)
    oauth_tokens = oauth_web_auth_code_grant.oauth_tokens
    print("TOKENS INCOMMING")
    print(dir(oauth_tokens))
    access_token = oauth_tokens.access_token
    refresh_token = oauth_tokens.refresh_token
    issued_at = oauth_tokens.issued_at
    expires_in_seconds = oauth_tokens.access_token_expires_in_seconds

    # expires_in = timedelta(seconds=oauth_tokens.access_token_expires_in_seconds)

    customer.bing_ads_access_token = access_token
    customer.bing_ads_refresh_token = refresh_token
    customer.bing_ads_issued_at = issued_at
    customer.bing_ads_expires_in_seconds = expires_in_seconds
    # customer.bing_ads_expires_at = datetime.now() + expires_in
    db.session.commit()
    return redirect(os.environ.get('BING_RETURN_URL'))

def generate_authenticator():
    return OAuthWebAuthCodeGrant(
        client_id=os.environ.get('BING_CLIENT_ID'),
        client_secret=os.environ.get('BING_CLIENT_SECRET'),
        redirection_uri=os.environ.get('BING_CALLBACK_URL')
    )

app.secret_key = os.environ.get('FLASK_SECRET_KEY')

if __name__ == "__main__":
    app.run()
