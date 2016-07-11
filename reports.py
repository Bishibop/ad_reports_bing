from bingads.service_client import ServiceClient
from bingads.authorization import *
from bingads import *
from bingads.reporting import *

import sys
import webbrowser
from time import gmtime, strftime
from suds import WebFault
from flask_sqlalchemy import SQLAlchemy
from functools import partial
from app import Customers


ENVIRONMENT = 'production'
DEVELOPER_TOKEN = os.environ.get('BING_DEVELOPER_TOKEN')
CLIENT_ID = os.environ.get('BING_CLIENT_ID')
CLIENT_SECRET = os.environ.get('BING_CLIENT_SECRET')
CALLBACK_URL = os.environ.get('BING_CALLBACK_URL')

FILE_DIRECTORY = '~/code'

RESULT_FILE_NAME = 'result.csv'

REPORT_FILE_FORMAT = 'Csv'

authorization_data = AuthorizationData(
    account_id = None,
    customer_id = None,
    developer_token = DEVELOPER_TOKEN,
    authentication = None,
)

customer_service = ServiceClient(
    'CustomerManagementService',
    authorization_data = authorization_data,
    environment = ENVIRONMENT,
    version = 9,
)

reporting_service_manager = ReportingServiceManager(
    authorization_data = authorization_data,
    poll_interval_in_milliseconds = 1000,
    environment = ENVIRONMENT,
)

reporting_service = ServiceClient(
    'ReportingService',
    authorization_data = authorization_data,
    environment = ENVIRONMENT,
    version = 9,
)


def authenticate_with_oauth(customer_id):

    global authorization_data

    authentication = OAuthWebAuthCodeGrant(
        client_id=os.environ.get('BING_CLIENT_ID'),
        client_secret=os.environ.get('BING_CLIENT_SECRET'),
        redirection_uri=os.environ.get('BING_CALLBACK_URL')
    )

    authorization_data.authentication = authentication

    authorization_data.authentication.token_refreshed_callback = partial(save_refresh_token, customer_id)

    refresh_token = get_refresh_token(customer_id)

    authentication.request_oauth_tokens_by_refresh_token(refresh_token)


def get_refresh_token(customer_id):
    customer = Customers.query.get(customer_id)
    refresh_token = customer.bing_ads_refresh_token
    return refresh_token


def save_refresh_token(customer_id, oauth_tokens):
    customer = Customers.query.get(customer_id)
    customer.bing_ads_refresh_token = oauth_tokens.refresh_token


def output_status_message(message):
    print(message)


def get_account_report_request(customer_id):
    # this should pass in a client_id, you're going to need it to write the reports
    # use that to get customer_id

    report_request = reporting_service.factory.create('AccountPerformanceReportRequest')
    report_request.Format = REPORT_FILE_FORMAT
    report_request.ReportName = 'Account Summary Report'
    report_request.ReturnOnlyCompleteData = False
    report_request.Language = 'English'

    scope = reporting_service.factory.create('AccountReportScope')
    scope.AccountIds = {'long': [authorization_data.account_id]}
    report_request.Scope = scope

    report_time = reporting_service.factory.create('ReportTime')

    # Change this to use a custom time range
    report_time.PredefinedTime='Yesterday'

    # custom_date_range_start = reporting_service.factory.create('Date')
    # custom_date_range_start.Day = 1
    # custom_date_range_start.Month = 1
    # custom_date_range_start.Year = 2016
    # report_time.CustomDateRangeStart = customer_date_range_start
    # custom_date_range_end = reporting_service.factory.create('Date')
    # custom_date_range_end.Day = 28
    # custom_date_range_end.Month = 2
    # cutom_date_range_end.Year = 2016
    # report_time.CustomDateRangeEnd = custom_date_range_end
    # report_time.PredefinedTime = None

    report_request.Time = report_time

    report_request.Aggregation = 'Daily'

    report_columns = reporting_service.factory.create('ArrayOfAccountPerformanceReportColumn')
    report_columns.AccountPerformanceReportColumn.append([
        'AccountName',
        'AccountNumber',
        'AccountId',
        'TimePeriod',
        'Impressions',
        'Clicks',
        'Ctr',
        'AverageCpc',
        'Spend',
        'AveragePosition',
        'Conversions',
        'ConversionRate',
        'CostPerConversion',
        'PhoneImpressions',
        'PhoneCalls',
        'ManualCalls',
        'ClickCalls',
        'Ptr',
        'PhoneSpend',
        'AverageCpp',
        'TotalCostPhoneAndClicks',
    ])
    report_request.Columns = report_columns

    return report_request


def background_completion(reporting_download_parameters):

    global reporting_service_manager
    result_file_path = reporting_service_manager.download_file(reporting_download_parameters)
    output_status_message("Download result file: {0}\n".format(result_file_path))


def get_report(customer_id):

    authenticate_with_oauth(customer_id)

    authorization_data.account_id = 40043731
    # authorization_data.customer_id = 19160679

    report_request = get_account_report_request(customer_id)

    reporting_download_parameters = ReportingDownloadParameters(
        report_request = report_request,
        result_file_directory = FILE_DIRECTORY,
        result_file_name = RESULT_FILE_NAME,
        overwrite_result_file = True,
    )

    output_status_message("Awaiting Background Complettion . . .")
    background_completion(reporting_download_parameters)

    output_status_message("Program execution completed")




# @app.cli.command()
# def test_shell_function():
    # click.echo('testing the shell functionality')
