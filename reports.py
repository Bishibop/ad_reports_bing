from bingads.service_client import ServiceClient
from bingads.authorization import *
from bingads import *
from bingads.reporting import *
from time import gmtime, strftime
from suds import WebFault
from flask_sqlalchemy import SQLAlchemy
from functools import partial
from datetime import datetime, date, timedelta
from dateutil import parser
from models import Customers, Clients, BingadsReports
from app import db
import sys, csv, itertools


ENVIRONMENT = 'production'
DEVELOPER_TOKEN = os.environ.get('BING_DEVELOPER_TOKEN')

FILE_DIRECTORY = '/tmp'

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


def authenticate_with_oauth(customer):

    global authorization_data

    authentication = OAuthWebAuthCodeGrant(
        client_id=os.environ.get('BING_CLIENT_ID'),
        client_secret=os.environ.get('BING_CLIENT_SECRET'),
        redirection_uri=os.environ.get('BING_CALLBACK_URL')
    )

    authorization_data.authentication = authentication

    authorization_data.authentication.token_refreshed_callback = partial(save_refresh_token, customer)

    refresh_token = get_refresh_token(customer)

    authentication.request_oauth_tokens_by_refresh_token(refresh_token)


def get_refresh_token(customer):
    return customer.bing_ads_refresh_token


def save_refresh_token(customer, oauth_tokens):
    customer.bing_ads_refresh_token = oauth_tokens.refresh_token
    db.session.add(customer)
    db.session.commit()


def output_status_message(message):
    print(message)


def get_account_report_request(start_date, end_date):
    report_request = reporting_service.factory.create('AccountPerformanceReportRequest')
    report_request.Format = REPORT_FILE_FORMAT
    report_request.ReportName = 'Account Summary Report'
    report_request.ReturnOnlyCompleteData = False
    report_request.Language = 'English'

    scope = reporting_service.factory.create('AccountReportScope')
    scope.AccountIds = {'long': [authorization_data.account_id]}
    report_request.Scope = scope

    report_time = reporting_service.factory.create('ReportTime')
    report_time.PredefinedTime = None

    custom_date_range_start = reporting_service.factory.create('Date')
    custom_date_range_start.Day = start_date.day
    custom_date_range_start.Month = start_date.month
    custom_date_range_start.Year = start_date.year
    report_time.CustomDateRangeStart = custom_date_range_start

    custom_date_range_end = reporting_service.factory.create('Date')
    custom_date_range_end.Day = end_date.day
    custom_date_range_end.Month = end_date.month
    custom_date_range_end.Year = end_date.year
    report_time.CustomDateRangeEnd = custom_date_range_end

    report_request.Time = report_time

    report_request.Aggregation = 'Daily'

    report_columns = reporting_service.factory.create('ArrayOfAccountPerformanceReportColumn')
    report_columns.AccountPerformanceReportColumn.append([
        'AccountName',
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
    ])
    report_request.Columns = report_columns

    return report_request


def background_completion(reporting_download_parameters):

    global reporting_service_manager
    result_file_path = reporting_service_manager.download_file(reporting_download_parameters)
    output_status_message("Download result file: {0}\n".format(result_file_path))


def get_reports_for_date_range(client, start_date, end_date):

    customer = client.customer
    authenticate_with_oauth(customer)

    authorization_data.account_id = client.bing_ads_aid

    report_request = get_account_report_request(start_date, end_date)

    reporting_download_parameters = ReportingDownloadParameters(
        report_request = report_request,
        result_file_directory = FILE_DIRECTORY,
        result_file_name = RESULT_FILE_NAME,
        overwrite_result_file = True,
    )

    output_status_message("Awaiting Background Completion...")
    background_completion(reporting_download_parameters)

    output_status_message("Program execution completed")

    line_count = None
    with open('/tmp/result.csv', 'rb') as csvfile:
        line_count = sum(1 for _ in csvfile)

    with open('/tmp/result.csv', 'rb') as csvfile:
        sub_file = itertools.islice(csvfile, 11, line_count - 2)
        reader = csv.reader(sub_file)

        for row in reader:
            print "--" + ', '.join(row)
            report_date = parser.parse(row[2]).date()

            existing_report = client.bingads_reports.filter_by(date=report_date).first()
            if existing_report:
                print("already have report for " + row[2])
                existing_report.date=report_date,
                existing_report.impressions=row[3],
                existing_report.clicks=row[4],
                existing_report.click_through_rate=row[5],
                existing_report.average_cost_per_click=row[6],
                existing_report.cost=row[7],
                existing_report.average_position=row[8],
                existing_report.form_conversions=row[9],
                existing_report.conversion_rate=row[10]
                db.session.add(existing_report)
            else:
                print("creating a new report for " + row[2])
                report = BingadsReports(date=report_date,
                                        impressions=row[3],
                                        clicks=row[4],
                                        click_through_rate=row[5],
                                        average_cost_per_click=row[6],
                                        cost=row[7],
                                        average_position=row[8],
                                        form_conversions=row[9],
                                        conversion_rate=row[10])
                    # took this out because it returns blank for no conversions
                                        # cost_per_conversion=row[11])
                report.client = client
                db.session.add(report)

    # filling in days with no rows (for which I presume the campaigns weren't running)
    number_of_days = (end_date - start_date).days
    date_list = [date.today() - timedelta(days=x) for x in range(0, number_of_days + 1)]
    for report_date in date_list:
        if client.bingads_reports.filter_by(date=report_date).first():
            # there is a record for that date. Do nothing
            print("already have report for " + report_date.strftime("%m/%d/%Y"))
        else:
            print("creating a new (blank) report for " + report_date.strftime("%m/%d/%Y"))
            report = BingadsReports(date=report_date,
                                    impressions='0',
                                    clicks='0',
                                    click_through_rate='0.0',
                                    average_cost_per_click='0.0',
                                    cost='0.0',
                                    average_position='0.0',
                                    form_conversions='0')
                                    conversion_rate='0.00')
            report.client = client
            db.session.add(report)

    db.session.commit()


# @app.cli.command()
# def test_shell_function():
    # click.echo('testing the shell functionality')
