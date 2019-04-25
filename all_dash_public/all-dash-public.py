#!/usr/bin/env python
import argparse
import os
import sys
import textwrap
from datadog import initialize
from datadog import api
import json
from halo import Halo
import requests

def getAllPublicDashboards(api_key, app_key):
    # @ckelner: These won't work - no way to get:
        # - boolean as to whether the dashboard is public or not
        # - public token from API at this time
            # - If we could, then we could use the public dash API:
                # - https://api.datadoghq.com/api/v1/public_dashboard/<token>
            # - token generation is a combo of public org id and a randomly generated token
                # def generate_token(cls, org_public_id):
                #    '''
                #    TOKEN_LENGTH size is set to 16 bytes.
                #     - The random token size will be 32 chars
                #     - The org_public_id is limited to 16 chars
                #    So the full token size will be less than 49 chars
                #    '''
        # - public URL, or any indicator that the board is public
    # result = api.Dashboard.get_all()
    # result = api.Screenboard.get_all()
    # result = api.Screenboard.get(<redacted>)
    # result = api.Dashboard.get(<redacted>)
    #
    # Using various dashboard list API calls we can get this information though
    # https://docs.datadoghq.com/api/?lang=python#dashboard-lists
    #
    # Logic:
    # 1. Fetch all dashboard lists
    # 2. Check that they have more than 1 dashboard in the list
    # 3. Fetch each dashboard list item (the list itself doesn't contain the
    # boolean we need to know if the dashboard is public or not)
    # 4. Check is the dashboard is public or not
    # 5. Check the dashboard id against a running dictionary we have to
    # guarentee our dict is unique dashboards only
    # 6. If unique place it in our dict to return to the user
    spinner = Halo(text="Getting all public dashboards; This might take awhile...", spinner="dots")
    spinner.start()

    # dict to hold the public dashboard info
    public_dashboards = {}
    # list of dashboard items (of undetermined state)
    dashboard_items = []
    # unique list of dashboard items
    unique_dashboard_items = []

    # get all dashboard lists
    # @ckelner: this ONLY gets manually created dashboard lists, as seen in:
    # - https://docs.datadoghq.com/api/?lang=bash#dashboard-lists
    #   - GET https://api.datadoghq.com/api/v1/dashboard/lists/manual
    #       - Note the `/manual` bit
    # - https://github.com/DataDog/datadogpy/blob/master/datadog/api/dashboard_lists.py#L20
    #
    # However, an endpoint does exists that isn't documented:
    # https://github.com/DataDog/dogweb/blob/prod/dogweb/config/routing/core.py#L375
    #
    # We will need to call this manually as it isn't mapped in the python lib
    #
    # d_lists = api.DashboardList.get_all()["dashboard_lists"]

    # @ckelner: This doesn't work -- Preset lists (e.g. `1` which is All custom)
    # Results in:
    # {
    #   "errors": [
    #        "Manual Dashboard List with id 1 not found"
    #    ]
    # }
    # present_all_custom_d_list = api.DashboardList.get(1)

    # gets all dashboards from UNPUBLISHED API ENDPOINT
    # Includes `"type": "preset_dashboard_list"` and `"type": "manual_dashboard_list"`
    all_dash_list = json.loads(requests.get(
        'https://api.datadoghq.com/api/v1/dashboard/lists?' +
        'api_key=' + api_key + '&application_key=' + app_key).text)["dashboard_lists"]

    # poor man's debugging
    # print json.dumps(all_dash_list, indent=4, sort_keys=True)

    '''
        Presets differ from manual lists, like so:
        {
            "author": {
                "handle": null,
                "name": null
            },
            "created": null,
            "dashboard_count": null,
            "dashboards": null,
            "id": 1,
            "is_favorite": false,
            "modified": null,
            "name": "All Custom",
            "type": "preset_dashboard_list"
        }
        versus
        {
            "author": {
                "handle": "chris.kelner@datadoghq.com",
                "name": "Chris Kelner"
            },
            "created": "2018-08-22T18:20:33.837849+00:00",
            "dashboard_count": 2,
            "dashboards": null,
            "id": 12362,
            "is_favorite": true,
            "modified": "2018-08-22T18:22:29.345054+00:00",
            "name": "AWS Migration",
            "type": "manual_dashboard_list"
        }
    '''

    # iterate over the lists
    for d_list in all_dash_list:
        # poor man's debugging
        # print json.dumps(d_list, indent=4, sort_keys=True)
        # print d_list["dashboard_count"]
        # print d_list["type"]

        # @ckelner: can no longer use this, presents return `"dashboard_count": null`
        # ignore those with no dashboards
        # if d_list["dashboard_count"] > 0:

        if d_list["type"] == "preset_dashboard_list":
            # We need to use another UNPUBLISHED API here to get preset dashboards
            # https://github.com/DataDog/dogweb/blob/prod/dogweb/config/routing/core.py#L477
            preset_list_items = json.loads(requests.get(
                'https://api.datadoghq.com/api/v1/dashboard/lists/preset/' +
                str(d_list["id"]) + '/dashboards?' +
                'api_key=' + api_key +
                '&application_key=' + app_key).text)["dashboards"]
            # poor man's debugging
            # print json.dumps(preset_list_items, indent=4, sort_keys=True)
            dashboard_items.extend(preset_list_items)
        else:
            dash_list_items = api.DashboardList.get_items(d_list["id"])["dashboards"]
            # poor man's debugging
            # print json.dumps(dash_list_items, indent=4, sort_keys=True)
            dashboard_items.extend(dash_list_items)

    # keep count
    count = 0
    # iterate over dashboard_items
    for dash in dashboard_items:
        # check if the dashboard is shared (public)
        # and make sure that we only save uniques
        if dash["is_shared"] == True and dash["id"] not in public_dashboards:
            # save it
            public_dashboards[dash["id"]] = dash
            count+=1

    spinner.stop()
    # print it!
    print json.dumps(public_dashboards, indent=4, sort_keys=True)
    with open('public-dashboards.json', 'w') as outfile:
        json.dumps(public_dashboards, indent=4, sort_keys=True)
    print "="*30
    print "Script complete. Found " + str(count) + " public dashboards."
    print "JSON has been dumped to ./public-dashboards.json"
    print "Exiting..."


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Create an empty dashboard for testing purposes")
    parser.add_argument(
        "-k", "--apikey", help="Your Datadog API key", type=str, default=None)
    parser.add_argument(
        "-a", "--appkey", help="Your Datadog app key", type=str, default=None)
    args = parser.parse_args()
    api_key = args.apikey or os.getenv("DATADOG_API_KEY", None) or os.getenv("DD_API_KEY", None)
    app_key = args.appkey or os.getenv("DATADOG_APP_KEY", None) or os.getenv("DD_APP_KEY", None)
    errors = []
    if not api_key:
        errors.append("""
                      You must supply your Datadog API key by either passing a
                      -k/--apikey argument or defining a DATADOG_API_KEY or
                      DD_API_KEY environment variable.""")
    if not app_key:
        errors.append("""
                      You must supply your Datadog application key by either
                      passing a -a/--appkey argument or defining a
                      DATADOG_APP_KEY or DD_APP_KEY environment variable.""")
    if errors:
        for error in errors:
            print textwrap.dedent(error)
        sys.exit(2)
    else:
        # Initialize the dd client
        options = {
            'api_key': api_key,
            'app_key': app_key
        }
        initialize(**options)
        getAllPublicDashboards(api_key, app_key)
