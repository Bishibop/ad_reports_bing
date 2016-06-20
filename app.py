from __future__ import print_function
from flask import Flask, redirect, request
from flask_environments import Environments
from bingads import *
from bingads.bulk import *
import os

app = Flask(__name__)
env = Environments(self.app)
env.from_object('app.config')


@app.route("/")
def hello():
    return "Hello World!"

@app.route("/register")
def register():
    oauth_web_auth_code_grant = generate_authenticator()
    return redirect(oauth_web_auth_code_grant.get_authorization_endpoint())

@app.route("/callback")
def callback():
    oauth_web_auth_code_grant = generate_authenticator()
    oauth_web_auth_code_grant.request_oauth_tokens_by_response_uri(request.url)
    oauth_tokens = oauth_web_auth_code_grant.oauth_tokens
    access_token = oauth_tokens.access_token
    return "CALLBACK URL WOOT"

def generate_authenticator():
    return OAuthWebAuthCodeGrant(
        client_id=os.environ.get('BING_CLIENT_ID'),
        client_secret=os.environ.get('BING_CLIENT_SECRET'),
        redirection_uri=os.environ.get('BING_CALLBACK_URL')
    )


if __name__ == "__main__":
    app.run()
