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

    authorization_data.authentication.token_refreshed_callback = partial(update_tokens, customer)

    refresh_token = get_refresh_token(customer)

    authentication.request_oauth_tokens_by_refresh_token(refresh_token)


def get_refresh_token(customer):
    return customer.bingads_refresh_token


def update_tokens(customer, oauth_tokens):
    customer.bingads_refresh_token = oauth_tokens.refresh_token
    customer.bingads_access_token = oauth_tokens.access_token
    customer.bingads_expires_in_seconds = oauth_tokens.access_token_expires_in_seconds
    customer.bingads_issued_at = datetime.now() - timedelta(seconds=15)

    db.session.add(customer)
    db.session.commit()


def background_completion(reporting_download_parameters):
    global reporting_service_manager
    result_file_path = reporting_service_manager.download_file(reporting_download_parameters)
    print("\tDownload result file: {0}".format(result_file_path))


def get_metrics_report_request(start_date, end_date):
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


def get_queries_report_request(start_date, end_date):
    report_request = reporting_service.factory.create('SearchQueryPerformanceReportRequest')
    report_request.Format = REPORT_FILE_FORMAT
    report_request.ReportName = 'Query Conversions Report'
    report_request.ReturnOnlyCompleteData = False
    report_request.Language = 'English'

    scope = reporting_service.factory.create('AccountThroughAdGroupReportScope')
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

    report_columns = reporting_service.factory.create('ArrayOfSearchQueryPerformanceReportColumn')
    report_columns.SearchQueryPerformanceReportColumn.append([
        'AccountName',
        'AccountId',
        'TimePeriod',
        'CampaignName',
        'SearchQuery',
        'Clicks',
        'BidMatchType',
        'DeliveredMatchType',
    ])
    report_request.Columns = report_columns

    return report_request


def generate_date_list(start_date, end_date):
    numdays = (end_date - start_date).days + 1
    return [end_date - timedelta(days=x) for x in range(0, numdays)]


def request_queries_reports(client, start_date, end_date):
    try:
        print("\n\nGetting queries reports for " + client.name + " - " + start_date.isoformat() + " to " + end_date.isoformat() + "\n")

        customer = client.customer
        authenticate_with_oauth(customer)

        authorization_data.account_id = client.bingads_aid

        date_list = generate_date_list(start_date, end_date)

        for report_date in date_list:

            report_request = get_queries_report_request(report_date, report_date)

            reporting_download_parameters = ReportingDownloadParameters(
                report_request = report_request,
                result_file_directory = FILE_DIRECTORY,
                result_file_name = RESULT_FILE_NAME,
                overwrite_result_file = True,
            )

            print("\tReport request sent for " + report_date.isoformat() + "...")
            background_completion(reporting_download_parameters)
            print("\tReport downloaded")

            line_count = None
            with open('/tmp/result.csv', 'rb') as csvfile:
                line_count = sum(1 for _ in csvfile)

            with open('/tmp/result.csv', 'rb') as csvfile:
                sub_file = itertools.islice(csvfile, 11, line_count - 2)
                reader = csv.reader(sub_file)

                query_clicks = {}
                for row in reader:
                    # print "\t--" + ', '.join(row)
                    if row[4] in query_clicks:
                        query_clicks[row[4]] = str(int(query_clicks[row[4]]) + int(row[5]))
                    else:
                        query_clicks[row[4]] = row[5]

                existing_report = client.bingads_reports.filter_by(date=report_date).first()
                if existing_report:
                    print("\tUpdating report for " + report_date.isoformat() + "\n")
                    existing_report.query_clicks = query_clicks
                    db.session.add(existing_report)
                else:
                    print("\tCreating a new report for " + row[2] + "\n")
                    new_report = BingadsReports(date=report_date, query_clicks=query_clicks)
                    new_report.client = client
                    db.session.add(new_report)

            db.session.commit()

        print("\nBingads Queries Report request completed.")

    except WebFault as ex:
        output_webfault_errors(ex)
    except Exception as ex:
        output_status_message(ex)


def request_metrics_reports(client, start_date, end_date):
    try:
        print("\n\nGetting reports for " + client.name + " - " + start_date.isoformat() + " to " + end_date.isoformat() + "\n")

        customer = client.customer
        authenticate_with_oauth(customer)

        authorization_data.account_id = client.bingads_aid

        report_request = get_metrics_report_request(start_date, end_date)

        reporting_download_parameters = ReportingDownloadParameters(
            report_request = report_request,
            result_file_directory = FILE_DIRECTORY,
            result_file_name = RESULT_FILE_NAME,
            overwrite_result_file = True,
        )

        print("\tReport request sent, waiting for completion...")
        background_completion(reporting_download_parameters)
        print("\tReport downloaded")

        line_count = None
        with open('/tmp/result.csv', 'rb') as csvfile:
            line_count = sum(1 for _ in csvfile)

        with open('/tmp/result.csv', 'rb') as csvfile:
            sub_file = itertools.islice(csvfile, 11, line_count - 2)
            reader = csv.reader(sub_file)

            for row in reader:
                print "\t--" + ', '.join(row)
                report_date = parser.parse(row[2]).date()

                existing_report = client.bingads_reports.filter_by(date=report_date).first()
                if existing_report:
                    print("\tUpdating report for " + row[2])
                    existing_report.date=report_date
                    existing_report.impressions=row[3]
                    existing_report.clicks=row[4]
                    existing_report.click_through_rate=row[5]
                    existing_report.average_cost_per_click=row[6]
                    existing_report.cost=row[7]
                    existing_report.average_position=row[8]
                    existing_report.form_conversions=row[9]
                    # existing_report.conversion_rate=row[10]
                    db.session.add(existing_report)
                else:
                    print("\tCreating a new report for " + row[2])
                    new_report = BingadsReports(date=report_date,
                                                impressions=row[3],
                                                clicks=row[4],
                                                click_through_rate=row[5],
                                                average_cost_per_click=row[6],
                                                cost=row[7],
                                                average_position=row[8],
                                                form_conversions=row[9])
                        # took this out because it returns blank for no conversions
                                                # conversion_rate=row[10])
                                                # cost_per_conversion=row[11])
                    new_report.client = client
                    db.session.add(new_report)

        # filling in days with no rows (for which I presume the campaigns weren't running)
        print("\n\tChecking for and filling in blank days...")
        number_of_days = (end_date - start_date).days
        date_list = [date.today() - timedelta(days=x) for x in range(0, number_of_days + 1)]
        for report_date in date_list:
            if not client.bingads_reports.filter_by(date=report_date).first():
                print("\tCreating a new (blank) report for " + report_date.strftime("%m/%d/%Y"))
                blank_report = BingadsReports(date=report_date,
                                              impressions='0',
                                              clicks='0',
                                              click_through_rate='0.0',
                                              average_cost_per_click='0.0',
                                              cost='0.0',
                                              average_position='0.0',
                                              form_conversions='0',
                                              conversion_rate='0.00')
                blank_report.client = client
                db.session.add(report_blank)

        db.session.commit()

        print("\nBingads Report request completed.")

    except WebFault as ex:
        output_webfault_errors(ex)
    except Exception as ex:
        output_status_message(ex)


def output_status_message(message):
    print(message)


def output_bingads_webfault_error(error):
    if hasattr(error, 'ErrorCode'):
        output_status_message("ErrorCode: {0}".format(error.ErrorCode))
    if hasattr(error, 'Code'):
        output_status_message("Code: {0}".format(error.Code))
    if hasattr(error, 'Message'):
        output_status_message("Message: {0}".format(error.Message))
    output_status_message('')


def output_webfault_errors(ex):
    if hasattr(ex.fault, 'detail') \
        and hasattr(ex.fault.detail, 'ApiFault') \
        and hasattr(ex.fault.detail.ApiFault, 'OperationErrors') \
        and hasattr(ex.fault.detail.ApiFault.OperationErrors, 'OperationError'):
        api_errors=ex.fault.detail.ApiFault.OperationErrors.OperationError
        if type(api_errors) == list:
            for api_error in api_errors:
                output_bingads_webfault_error(api_error)
        else:
            output_bingads_webfault_error(api_errors)
    elif hasattr(ex.fault, 'detail') \
        and hasattr(ex.fault.detail, 'AdApiFaultDetail') \
        and hasattr(ex.fault.detail.AdApiFaultDetail, 'Errors') \
        and hasattr(ex.fault.detail.AdApiFaultDetail.Errors, 'AdApiError'):
        api_errors=ex.fault.detail.AdApiFaultDetail.Errors.AdApiError
        if type(api_errors) == list:
            for api_error in api_errors:
                output_bingads_webfault_error(api_error)
        else:
            output_bingads_webfault_error(api_errors)
    elif hasattr(ex.fault, 'detail') \
        and hasattr(ex.fault.detail, 'ApiFaultDetail') \
        and hasattr(ex.fault.detail.ApiFaultDetail, 'BatchErrors') \
        and hasattr(ex.fault.detail.ApiFaultDetail.BatchErrors, 'BatchError'):
        api_errors=ex.fault.detail.ApiFaultDetail.BatchErrors.BatchError
        if type(api_errors) == list:
            for api_error in api_errors:
                output_bingads_webfault_error(api_error)
        else:
            output_bingads_webfault_error(api_errors)
    elif hasattr(ex.fault, 'detail') \
        and hasattr(ex.fault.detail, 'ApiFaultDetail') \
        and hasattr(ex.fault.detail.ApiFaultDetail, 'OperationErrors') \
        and hasattr(ex.fault.detail.ApiFaultDetail.OperationErrors, 'OperationError'):
        api_errors=ex.fault.detail.ApiFaultDetail.OperationErrors.OperationError
        if type(api_errors) == list:
            for api_error in api_errors:
                output_bingads_webfault_error(api_error)
        else:
            output_bingads_webfault_error(api_errors)
    elif hasattr(ex.fault, 'detail') \
        and hasattr(ex.fault.detail, 'EditorialApiFaultDetail') \
        and hasattr(ex.fault.detail.EditorialApiFaultDetail, 'BatchErrors') \
        and hasattr(ex.fault.detail.EditorialApiFaultDetail.BatchErrors, 'BatchError'):
        api_errors=ex.fault.detail.EditorialApiFaultDetail.BatchErrors.BatchError
        if type(api_errors) == list:
            for api_error in api_errors:
                output_bingads_webfault_error(api_error)
        else:
            output_bingads_webfault_error(api_errors)
    elif hasattr(ex.fault, 'detail') \
        and hasattr(ex.fault.detail, 'EditorialApiFaultDetail') \
        and hasattr(ex.fault.detail.EditorialApiFaultDetail, 'EditorialErrors') \
        and hasattr(ex.fault.detail.EditorialApiFaultDetail.EditorialErrors, 'EditorialError'):
        api_errors=ex.fault.detail.EditorialApiFaultDetail.EditorialErrors.EditorialError
        if type(api_errors) == list:
            for api_error in api_errors:
                output_bingads_webfault_error(api_error)
        else:
            output_bingads_webfault_error(api_errors)
    elif hasattr(ex.fault, 'detail') \
        and hasattr(ex.fault.detail, 'EditorialApiFaultDetail') \
        and hasattr(ex.fault.detail.EditorialApiFaultDetail, 'OperationErrors') \
        and hasattr(ex.fault.detail.EditorialApiFaultDetail.OperationErrors, 'OperationError'):
        api_errors=ex.fault.detail.EditorialApiFaultDetail.OperationErrors.OperationError
        if type(api_errors) == list:
            for api_error in api_errors:
                output_bingads_webfault_error(api_error)
        else:
            output_bingads_webfault_error(api_errors)
    # Handle serialization errors e.g. The formatter threw an exception while trying
    # to deserialize the message:
    # There was an error while trying to deserialize parameter
    # https://bingads.microsoft.com/CampaignManagement/v9:Entities.
    elif hasattr(ex.fault, 'detail') \
        and hasattr(ex.fault.detail, 'ExceptionDetail'):
        api_errors=ex.fault.detail.ExceptionDetail
        if type(api_errors) == list:
            for api_error in api_errors:
                output_status_message(api_error.Message)
        else:
            output_status_message(api_errors.Message)
    else:
        raise Exception('Unknown WebFault')


