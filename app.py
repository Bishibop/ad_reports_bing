from __future__ import print_function
from flask import Flask, redirect, request, session
from flask_environments import Environments
from bingads import *
from bingads.bulk import *
import os

app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello World!"

@app.route("/register/<customer_id>")
def register(customer_id):
    session['customer_id'] = customer_id
    oauth_web_auth_code_grant = generate_authenticator()
    return redirect(oauth_web_auth_code_grant.get_authorization_endpoint())

@app.route("/callback")
def callback():
    oauth_web_auth_code_grant = generate_authenticator()
    oauth_web_auth_code_grant.request_oauth_tokens_by_response_uri(request.url)
    oauth_tokens = oauth_web_auth_code_grant.oauth_tokens
    access_token = oauth_tokens.access_token
    return session.pop('customer_id', None)

def generate_authenticator():
    return OAuthWebAuthCodeGrant(
        client_id=os.environ.get('BING_CLIENT_ID'),
        client_secret=os.environ.get('BING_CLIENT_SECRET'),
        redirection_uri=os.environ.get('BING_CALLBACK_URL')
    )


if __name__ == "__main__":
    app.run()
