import os
import requests
from datetime import datetime


def find_songkick_locations(search_term):
    """Return list of Songkick metro areas matching search term

    Makes a GET request to Songkick API for location data using the term.
    """

    # Make GET request to Songkick API for location
    payload = {
        'query': search_term,
        'apikey': os.getenv('SONGKICK_KEY'),
    }
    loc_response = requests.get("http://api.songkick.com/api/3.0/search/locations.json",
                                payload)

    # Create empty list of metro areas
    metros = []

    # If request is successful, get results from the response
    if loc_response.ok:
        results = loc_response.json()['resultsPage']['results']

        # If the results are not empty, create empty list of metro ids
        if results:
            metro_id_list = []

            # Iterate over each location in results
            for loc in results['location']:
                metro = loc['metroArea']

                # If metro area has not already been added to list of metros
                if metro['id'] not in metro_id_list:

                    # Add metro area to list
                    metros.append(metro)
                    metro_id_list.append(metro['id'])

    # Return list of metro areas for each location in results
    return metros


def get_concert_recs(spotify):
    """Returns list of concert recommendation dictionaries using Spotify API object"""

    print "Retrieving top artists"
    start = datetime.now()

    # Get user's top artists
    top_artists_response = spotify.current_user_top_artists(limit=3,
                                                            time_range='medium_term')
    top_artists_dict = parse_artist_response(top_artists_response)

    top_time = datetime.now()
    print "Time to get {} top artists: {}".format(len(top_artists_dict), top_time - start)
    print "Getting related artists"

    # Get artists related to user's top artists
    related_artists_dict = {}
    for artist_id in top_artists_dict.keys():
        rel_artists_resp = spotify.artist_related_artists(artist_id)
        add_artists_to_dict(rel_artists_resp, related_artists_dict)

    rel_time = datetime.now()
    print "Time to get {} related artists: {}".format(len(related_artists_dict), rel_time - top_time)
    print "Finding concerts"

    return related_artists_dict


def parse_artist_response(artists_response):
    """Takes results of API call for top artists and returns a dictionary of artists

    The returned dictionary uses Spotify IDs as keys and artist name as values"""

    artists_dict = {}

    # Iterate through list of artist items in response
    for artist in artists_response['items']:

        # Assigns artist's name as value to key of Spotify ID
        artist_id = artist['id']
        artist_name = artist['name']
        artists_dict[artist_id] = artist_name

    return artists_dict


def add_artists_to_dict(artists_response, original_dict):
    """Adds artists from results of API call for related artists to a dictionary

    The dictionary uses Spotify IDs as keys and artist name as values"""

    # Iterate through list of artists in response
    for artist in artists_response['artists']:

        # Assigns artist's name as value to key of Spotify ID in given dicitonary
        artist_id = artist['id']
        artist_name = artist['name']
        original_dict[artist_id] = artist_name


def find_songkick_concerts(spotify_id, artist, location="sk:26330"):
    """Takes dicitonary of related artists and returns a list of concert recommendation dictionaries

    Makes requests to the Songkick API for upcoming events based on artists
    in the related artist dicitonary"""

    songkick_key = os.getenv('SONGKICK_KEY')

    # Create empty recommendation list
    concert_recs_list = []

    start = datetime.now()

    # Make GET request to songkick API for this location & artist
    payload = {
        'apikey': songkick_key,
        'artist_name': artist,
        'location': location,
    }
    event_response = requests.get("http://api.songkick.com/api/3.0/events.json", payload)

    print datetime.now() - start

    # If request is successful
    if event_response.ok:

        # Get list of events from response
        events = event_response.json()['resultsPage']['results'].get('event')

        # If event list not empty
        if events:

            # Iterate over event list
            for event in events:

                # Create dictionary of concert's information
                concert = {
                    'display_name': event['displayName'],
                    'songkick_id': event['id'],
                    'songkick_url': event['uri'],
                    'artist': artist,
                    'spotify_id': spotify_id,
                    'venue': event['venue']['displayName'],
                    'city': event['location']['city'],
                }

                # Find concert's start date & datetime
                start_datetime = event['start']['datetime']
                start_date = event['start']['date']

                # Set concert dict's start_datetime as start_datetime, or start_date if datetime unavailable
                if start_datetime:
                    concert['start_datetime'] = datetime.strptime(start_datetime[:-5],
                                                                  "%Y-%m-%dT%H:%M:%S")
                elif start_date:
                    concert['start_datetime'] = datetime.strptime(start_date,
                                                                  "%Y-%m-%d")

                # Add concert to recommendation list
                concert_recs_list.append(concert)

    # If request unsuccessful, print error
    else:
        artist = artist.encode('utf-8')
        print "Failed: {}".format(artist)

    return concert_recs_list
