import unittest
from freezegun import freeze_time
from datetime import datetime
import spotipy
import os
from passlib.hash import pbkdf2_sha256 as sha
import json

import sample_apis
import songkick
import analyzation
import spotify_oauth_tools
import model
import server


class TestSongkick(unittest.TestCase):

    def test_location_request(self):
        SF_Metros = songkick.find_songkick_locations("San Francisco")
        self.assertIsInstance(SF_Metros, list)
        self.assertIn("SF Bay Area", SF_Metros[0]['displayName'])

    def test_location_response(self):
        locations = songkick.create_location_list(sample_apis.london)
        self.assertEqual(len(locations), 2)
        self.assertEqual(locations[0]['displayName'], 'London')
        self.assertEqual(locations[0]['country']['displayName'], 'UK')
        self.assertEqual(locations[1]['displayName'], 'Lexington')
        self.assertEqual(locations[1]['state']['displayName'], 'KY')

    def test_long_location_response(self):
        locations = songkick.create_location_list(sample_apis.houston)
        self.assertEqual(len(locations), 5)

    def test_nowhere(self):
        self.assertEqual(songkick.create_location_list(sample_apis.nowhere), [])

    def test_concert_request(self):
        artist = {'spotify_id': '1234',
                  'artist': 'Open Mike Eagle',
                  'image_url': 'https://i.scdn.co/image/7a79a4f7ef164f418034d6fe5e53be24123610bf',
                  'source': 'Run The Jewels'}
        concerts = songkick.find_songkick_concerts(artist)
        self.assertIsInstance(concerts, list)

    def test_concert_response(self):
        artist = {'spotify_id': '9999',
                  'artist': 'Vampire Weekend',
                  'image_url': 'http://placemelon.com/200/200',
                  'source': 'Phoenix'}
        concerts = songkick.create_concert_list(sample_apis.vw_concerts, artist)

        self.assertEqual(len(concerts), 2)

        self.assertIn('Weekend at O2', concerts[0]['display_name'])
        self.assertIn('placemelon', concerts[0]['image_url'])
        self.assertIn('2010-02-16T19:30:00', concerts[0]['start_datetime'])
        self.assertIsNone(concerts[0].get('end_date'))

        self.assertIn('2010-02-17T00:00:00', concerts[1]['start_date'])
        self.assertIn('2010-02-17T00:00:00', concerts[1]['start_datetime'])
        self.assertEqual(concerts[1]['spotify_id'], '9999')
        self.assertEqual(concerts[1]['source'], 'Phoenix')

    def test_festival_response(self):
        artist = {'spotify_id': '5555',
                  'artist': 'Little Dragon',
                  'image_url': 'xyz',
                  'source': None}
        festival = songkick.create_concert_list(sample_apis.outside_lands, artist)[0]

        self.assertIn('2017-08-11T00:00:00', festival['start_date'])
        self.assertIn('2017-08-11T00:00:00', festival['start_datetime'])
        self.assertIn('2017-08-13T00:00:00', festival['end_date'])
        self.assertIn('2017-08-13T00:00:00', festival['end_datetime'])


class TestAnalyzation(unittest.TestCase):

    def test_find_spotify_artists(self):
        result = analyzation.find_spotify_artists('Run the Jewels')
        self.assertIn('Run The Jewels', result[0]['artist'])

    def test_parse_artist_response(self):
        clip_search = sample_apis.clipping_search['artists']['items']
        result = analyzation.parse_artist_response(clip_search)

        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], dict)
        self.assertEqual(result[0]['spotify_id'], '5HJ2kX5UTwN4Ns8fB5Rn1I')
        self.assertEqual(result[0]['image_url'], 'https://i.scdn.co/image/96f3fd452d3871eea1ba9ba9cab63b002d8360bb')
        self.assertEqual(result[1]['artist'], 'Clipping')
        self.assertIsNone(result[2]['image_url'])
        self.assertIsNone(result[0]['source'])

    def test_parse_repeats(self):
        clip_search = sample_apis.clipping_search['artists']['items']
        initial_list = [{'artist': u'clipping.',
                         'image_url': u'https://i.scdn.co/image/96f3fd452d3871eea1ba9ba9cab63b002d8360bb',
                         'source': None,
                         'spotify_id': u'5HJ2kX5UTwN4Ns8fB5Rn1I'},
                        {'artist': u'Clipping',
                         'image_url': u'https://i.scdn.co/image/1a08ba0b21ca3a1a9e9c1a460c6ced7e1fcdc4ef',
                         'source': 'Death Grips',
                         'spotify_id': u'7iUaTsRiiEVbslUcOs5mpd'}]
        result = analyzation.parse_artist_response(clip_search, initial_list, 'Run the Jewels')

        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]['source'], 'Death Grips')
        self.assertEqual(result[2]['source'], 'Run the Jewels')

    def test_get_artist_recs(self):
        top_artist = [{'spotify_id': '6Tyzp9KzpiZ04DABQoedps', 'artist': 'Little Dragon'}]
        result = analyzation.get_artist_recs(top_artist)
        self.assertIsInstance(result, list)
        self.assertNotEqual(len(result), 0)
        self.assertEqual(result[1]['source'], 'Little Dragon')


class TestSpotifyOauth(unittest.TestCase):

    def test_get_spotify_oauth(self):
        sp_oauth = spotify_oauth_tools.get_spotify_oauth()

        self.assertIsInstance(sp_oauth, spotipy.oauth2.SpotifyOAuth)
        self.assertIn('user-top-read', sp_oauth.scope)
        self.assertEqual(sp_oauth.client_id, os.getenv('SPOTIPY_CLIENT_ID'))
        self.assertEqual(sp_oauth.client_secret, os.getenv('SPOTIPY_CLIENT_SECRET'))


class TestModel(unittest.TestCase):

    def setUp(self):
        import model
        model.connect_to_db(server.app, "postgresql:///testconsa")
        model.db.create_all()
        model.example_data()

    def tearDown(self):
        model.db.session.close()
        model.db.drop_all()

    def test_users(self):
        kiko = model.User.query.get(2)
        self.assertEqual(kiko.email, 'kiko@creat.er')
        self.assertTrue(sha.verify('kikokikokiko', kiko.pw_hash))
        self.assertIsInstance(kiko.concerts, list)
        self.assertIsInstance(kiko.concerts[0], model.Concert)

    def test_user_add_concert(self):
        noone = model.User.query.get(3)
        self.assertEqual(noone.concerts, [])

        success = noone.add_concert(2)
        self.assertTrue(success)
        self.assertNotEqual(noone.concerts, [])
        self.assertEqual(noone.concerts[0].artist, 'Cakes Da Killa')

        failure = noone.add_concert(99)
        self.assertFalse(failure)

    def test_user_remove_concert(self):
        user = model.User.query.first()
        clip = model.Concert.query.get(1)
        self.assertNotEqual(user.concerts, [])
        self.assertEqual(len(user.concerts), 1)
        self.assertIsNotNone(clip)

        success = user.remove_concert(1)
        clip = model.Concert.query.get(1)
        self.assertTrue(success)
        self.assertEqual(len(user.concerts), 0)
        self.assertIsNone(clip)

    def test_concerts(self):
        clip = model.Concert.query.get(1)
        self.assertEqual(clip.artist, 'clipping.')
        self.assertEqual(clip.city, 'San Francisco, CA')
        self.assertIsNone(clip.songkick_url)
        self.assertEqual(clip.venue_lat, 37.7697)
        self.assertEqual(clip.venue_lng, -122.4203)
        self.assertEqual(clip.image_url, 'https://i.scdn.co/image/96f3fd452d3871eea1ba9ba9cab63b002d8360bb')

        cakes = model.Concert.query.get(2)
        self.assertEqual(cakes.artist, 'Cakes Da Killa')
        self.assertEqual(cakes.venue_name, 'The New Parish')
        self.assertEqual(cakes.venue_lat, 37.8077)
        self.assertIsInstance(cakes.start_datetime, datetime)
        self.assertEqual(2017, cakes.start_datetime.year)
        self.assertIsInstance(cakes.users, list)

    def test_concert_create_from_form(self):
        form = {'songkick-id': u'4',
                'artist': u'Princess Nokia',
                'venue-name': u'Starline Social Club',
                'venue-lat': u'37.8123',
                'venue-lng': u'-122.2725',
                'city': u'Oakland, CA',
                'image-url': u'https://i.scdn.co/image/0aee878e922c97b73cbef3aa590781a615313791',
                'start-datetime': u'2017-05-06T21:00:00-0500'}

        nokia = model.Concert.query.get(4)
        self.assertIsNone(nokia)

        success = model.Concert.create_from_form(form)
        self.assertTrue(success)

        nokia = model.Concert.query.get(4)
        self.assertIsNotNone(nokia)
        self.assertEqual(nokia.artist, 'Princess Nokia')
        self.assertEqual(nokia.venue_lng, -122.2725)
        self.assertEqual(nokia.venue_name, 'Starline Social Club')
        self.assertEqual(nokia.image_url, 'https://i.scdn.co/image/0aee878e922c97b73cbef3aa590781a615313791')
        self.assertEqual(nokia.start_datetime.day, 6)
        self.assertEqual(nokia.start_datetime.hour, 21)

        failure = model.Concert.create_from_form({})
        self.assertFalse(failure)

    def test_users_concerts(self):
        assoc = model.UserConcert.query.first()
        self.assertEqual(assoc.user_id, 1)
        self.assertEqual(assoc.songkick_id, 1)


class TestServer(unittest.TestCase):

    def setUp(self):
        server.app.config['TESTING'] = True
        self.client = server.app.test_client()

        model.connect_to_db(server.app, "postgresql:///testconsa")
        model.db.create_all()
        model.example_data()

    def tearDown(self):
        model.db.session.close()
        model.db.drop_all()

    def test_homepage(self):
        result = self.client.get('/')
        self.assertEqual(result.status_code, 200)
        self.assertIn('Consa', result.data.decode('utf-8'))

        self.assertIn('your location', result.data.decode('utf-8'))
        self.assertIn('<div id="auth-option"', result.data.decode('utf-8'))
        self.assertIn('Use your Spotify account', result.data.decode('utf-8'))

        self.assertIn('<div id="spotify-artist-search"', result.data.decode('utf-8'))
        self.assertIn('Selected Artists', result.data.decode('utf-8'))

    def test_nav_bar(self):
        result = self.client.get('/')
        self.assertEqual(result.status_code, 200)

        self.assertIn('Register', result.data.decode('utf-8'))
        self.assertIn('Login', result.data.decode('utf-8'))
        self.assertNotIn('My Profile', result.data.decode('utf-8'))
        self.assertNotIn('Logout', result.data.decode('utf-8'))

    def test_display_login_form(self):
        result = self.client.get('/login')
        self.assertEqual(result.status_code, 200)
        self.assertIn(': Login', result.data.decode('utf-8'))

        self.assertIn('<form action="/login" method="POST"', result.data.decode('utf-8'))
        self.assertIn('Email', result.data.decode('utf-8'))
        self.assertIn('Password', result.data.decode('utf-8'))
        self.assertNotIn('already logged in', result.data.decode('utf-8'))

    def test_log_in(self):
        result = self.client.post('/login',
                                  data={'email': 'teST@tEst.ts', 'password': 'testtesttest'},
                                  follow_redirects=True)
        self.assertEqual(result.status_code, 200)

        self.assertIn('<h1>Your profile</h1>', result.data.decode('utf-8'))
        self.assertIn('Email: test@test.ts', result.data.decode('utf-8'))
        self.assertIn('Login successful', result.data.decode('utf-8'))
        self.assertNotIn('Invalid username or password', result.data.decode('utf-8'))

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_id'), 1)

    def test_log_in_fail(self):
        result = self.client.post('/login',
                                  data={'email': 'test@test.ts', 'password': 'wrong'},
                                  follow_redirects=True)
        self.assertEqual(result.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('user_id'))

        self.assertIn('<form action="/login" method="POST"', result.data.decode('utf-8'))
        self.assertIn('Invalid username or password', result.data.decode('utf-8'))
        self.assertNotIn('<h1>Your profile</h1>', result.data.decode('utf-8'))
        self.assertNotIn('Login successful', result.data.decode('utf-8'))

    def test_log_out(self):
        result = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(result.status_code, 200)

        self.assertNotIn('Logged out', result.data.decode('utf-8'))
        self.assertIn('No user currently logged in.', result.data.decode('utf-8'))
        self.assertIn('Use your Spotify account', result.data.decode('utf-8'))

    def test_display_registration_form(self):
        result = self.client.get('/register')
        self.assertEqual(result.status_code, 200)
        self.assertIn(': Register', result.data.decode('utf-8'))

        self.assertIn('<form action="/register" method="POST"', result.data.decode('utf-8'))
        self.assertIn('Email', result.data.decode('utf-8'))
        self.assertIn('Password', result.data.decode('utf-8'))
        self.assertNotIn('already logged in', result.data.decode('utf-8'))

    def test_register(self):
        result = self.client.post('/register',
                                  data={'email': 'new@cool.dude', 'password': 'c00ld00d'},
                                  follow_redirects=True)
        self.assertEqual(result.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_id'), 4)

        self.assertIn('<h1>Your profile</h1>', result.data.decode('utf-8'))
        self.assertIn('Email: new@cool.dude', result.data.decode('utf-8'))
        self.assertIn('Registration successful', result.data.decode('utf-8'))
        self.assertNotIn('username already exists', result.data.decode('utf-8'))

    def test_register_fail(self):
        result = self.client.post('/register',
                                  data={'email': 'test@test.ts', 'password': 'lolsame'},
                                  follow_redirects=True)
        self.assertEqual(result.status_code, 200)

        self.assertIn('<form action="/register" method="POST"', result.data.decode('utf-8'))
        self.assertIn('username already exists', result.data.decode('utf-8'))
        self.assertNotIn('<h1>Your profile</h1>', result.data.decode('utf-8'))
        self.assertNotIn('Registration successful', result.data.decode('utf-8'))

    def test_profile(self):
        result = self.client.get('/my-profile', follow_redirects=True)
        self.assertEqual(result.status_code, 200)
        self.assertIn(': Login', result.data.decode('utf-8'))

        self.assertIn('<form action="/login" method="POST"', result.data.decode('utf-8'))
        self.assertIn('must be logged in', result.data.decode('utf-8'))
        self.assertNotIn('<h1>Your profile</h1>', result.data.decode('utf-8'))

    def test_past(self):
        result = self.client.get('/my-profile/past', follow_redirects=True)
        self.assertEqual(result.status_code, 200)
        self.assertIn(': Login', result.data.decode('utf-8'))

        self.assertIn('<form action="/login" method="POST"', result.data.decode('utf-8'))
        self.assertIn('must be logged in', result.data.decode('utf-8'))
        self.assertNotIn('<h1>Your past concerts</h1>', result.data.decode('utf-8'))

    def test_callback_results_page(self):
        result = self.client.get('/callback?code=AbCdEf')
        self.assertEqual(result.status_code, 200)
        self.assertIn(': Concert Recommendations', result.data.decode('utf-8'))

        self.assertIn('authCode = "AbCdEf"', result.data.decode('utf-8'))
        self.assertIn('<h3>FINDING CONCERTS...</h3>', result.data.decode('utf-8'))
        self.assertIn('<div id="concert-results" hidden>', result.data.decode('utf-8'))

    def test_no_auth_results_page(self):
        artists = [{'spotify_id': '5HJ2kX5UTwN4Ns8fB5Rn1I', 'artist': 'clipping.'}]
        result = self.client.post('/no-auth-search', data={'artists': json.dumps(artists)})
        self.assertEqual(result.status_code, 200)
        self.assertIn(': Concert Recommendations', result.data.decode('utf-8'))

        self.assertIn('authCode = ""', result.data.decode('utf-8'))
        self.assertIn('5HJ2kX5UTwN4Ns8fB5Rn1I', result.data.decode('utf-8'))
        self.assertIn('<h3>FINDING CONCERTS...</h3>', result.data.decode('utf-8'))
        self.assertIn('<div id="concert-results" hidden>', result.data.decode('utf-8'))

    def test_location_matches(self):
        result = self.client.get('/location-search.json?search-term=SanFrancisco,+TX')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data.decode('utf-8'), '""\n')

        result = self.client.get('/location-search.json?search-term=Houston')
        self.assertNotEqual(result.data.decode('utf-8'), '')
        self.assertIn('"displayName":"Houston"', result.data.decode('utf-8'))
        self.assertIn('"displayName":"TX"', result.data.decode('utf-8'))

    def test_artist_matches(self):
        result = self.client.get('/artist-search.json?search-term=Run+The+Jewels')
        self.assertEqual(result.status_code, 200)
        self.assertIn('Run The Jewels', result.data.decode('utf-8'))

        result = self.client.get('/artist-search.json?search-term=asdfasdfasdf')
        self.assertEqual(result.status_code, 200)
        self.assertEqual('""\n', result.data.decode('utf-8'))

    def test_request_authorization(self):
        result = self.client.get('/spotify-auth.json')
        self.assertEqual(result.status_code, 200)

        client_id = os.getenv('SPOTIPY_CLIENT_ID')
        self.assertIn(client_id, result.data.decode('utf-8'))
        self.assertIn('user-top-read', result.data.decode('utf-8'))
        self.assertIn('accounts.spotify.com', result.data.decode('utf-8'))

    def test_recommendations(self):
        result = self.client.get('/recs.json?code=AbCdEf')
        self.assertEqual(result.status_code, 200)
        self.assertIn('Unable to authorize', result.data.decode('utf-8'))

    def test_recs_from_search(self):
        artists = [{'spotify_id': '5HJ2kX5UTwN4Ns8fB5Rn1I', 'artist': 'clipping.'}]
        result = self.client.get('/recs-from-search.json?artists=' + json.dumps(artists))
        self.assertEqual(result.status_code, 200)

    def test_concerts(self):
        result = self.client.get('/concerts.json?spotify-id=123&artist=clipping&image-url=www.clip.com/img.jpg')
        self.assertEqual(result.status_code, 200)
        self.assertIsNotNone(result.data)


class TestServerLoggedIn(unittest.TestCase):

    def setUp(self):
        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'key'
        self.client = server.app.test_client()

        with self.client.session_transaction() as sess:
            sess['user_id'] = 2

        model.connect_to_db(server.app, "postgresql:///testconsa")
        model.db.create_all()
        model.example_data()

    def tearDown(self):
        model.db.session.close()
        model.db.drop_all()

    def test_nav_bar(self):
        result = self.client.get('/')
        self.assertEqual(result.status_code, 200)

        self.assertIn('My Profile', result.data.decode('utf-8'))
        self.assertIn('Logout', result.data.decode('utf-8'))
        self.assertNotIn('Register', result.data.decode('utf-8'))
        self.assertNotIn('Login', result.data.decode('utf-8'))

    def test_display_login_form(self):
        result = self.client.get('/login', follow_redirects=True)
        self.assertEqual(result.status_code, 200)
        self.assertNotIn(': Login', result.data.decode('utf-8'))

        self.assertNotIn('<form action="/login" method="POST">', result.data.decode('utf-8'))
        self.assertIn('already logged in', result.data.decode('utf-8'))
        self.assertIn('Use your Spotify account', result.data.decode('utf-8'))

    def test_log_out(self):
        result = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(result.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('user_id'))

        self.assertIn('Logged out', result.data.decode('utf-8'))
        self.assertNotIn('No user currently logged in.', result.data.decode('utf-8'))
        self.assertIn('Use your Spotify account', result.data.decode('utf-8'))

        self.assertIn('Register', result.data.decode('utf-8'))
        self.assertIn('Login', result.data.decode('utf-8'))
        self.assertNotIn('My Profile', result.data.decode('utf-8'))
        self.assertNotIn('Logout', result.data.decode('utf-8'))

    def test_display_registration_form(self):
        result = self.client.get('/register', follow_redirects=True)
        self.assertEqual(result.status_code, 200)
        self.assertNotIn(': Register', result.data.decode('utf-8'))

        self.assertNotIn('<form action="/register" method="POST">', result.data.decode('utf-8'))
        self.assertIn('already logged in', result.data.decode('utf-8'))
        self.assertIn('Use your Spotify account', result.data.decode('utf-8'))

    def test_profile_with_no_concerts(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 3
        result = self.client.get('/my-profile')

        self.assertEqual(result.status_code, 200)
        self.assertIn(': Your Profile', result.data.decode('utf-8'))

        self.assertIn('<h1>Your profile</h1>', result.data.decode('utf-8'))
        self.assertIn('Email: no@one', result.data.decode('utf-8'))

        self.assertNotIn('<h3>Your saved concerts</h3>', result.data.decode('utf-8'))
        self.assertIn('<h3>You have no saved concerts</h3>', result.data.decode('utf-8'))

    def test_add_saved_concert(self):
        success_form = {'songkick-id': u'4',
                        'artist': u'Princess Nokia',
                        'venue-name': u'Starline Social Club',
                        'city': u'Oakland, CA',
                        'start-datetime': u'Sat, 06 May 2017 21:00:00 GMT'}
        success = self.client.post('/add-concert.json', data=success_form)
        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.data.decode('utf-8'), 'true\n')

        user = model.User.query.get(2)
        self.assertEqual(user.concerts[1].artist, 'Princess Nokia')

        failure_form = {'songkick-id': u'99'}
        failure = self.client.post('/add-concert.json', data=failure_form)
        self.assertEqual(failure.status_code, 200)
        self.assertEqual(failure.data.decode('utf-8'), 'false\n')

    def test_remove_saved_concert(self):
        result = self.client.post('/remove-concert.json', data={'songkick-id': '2'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data.decode('utf-8'), 'true\n')

        user = model.User.query.get(2)
        self.assertEqual(len(user.concerts), 1)


class TestFrozenMid(unittest.TestCase):
    def setUp(self):
        model.connect_to_db(server.app, "postgresql:///testconsa")
        model.db.create_all()
        model.example_data()

        with freeze_time('2017-06-01 23:00:00', tz_offset=-7):
            model.User.future_concerts = model.db.relationship("Concert",
                                                               order_by="Concert.start_datetime",
                                                               secondary="users_concerts",
                                                               secondaryjoin=model.db.and_(model.UserConcert.songkick_id == model.Concert.songkick_id,
                                                                                           model.Concert.start_datetime > datetime.now()))
            model.User.past_concerts = model.db.relationship("Concert",
                                                             order_by="Concert.start_datetime.desc()",
                                                             secondary="users_concerts",
                                                             secondaryjoin=model.db.and_(model.UserConcert.songkick_id == model.Concert.songkick_id,
                                                                                         model.Concert.start_datetime < datetime.now()))

        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'key'
        self.client = server.app.test_client()

        with self.client.session_transaction() as sess:
            sess['user_id'] = 2

    def tearDown(self):
        model.db.session.close()
        model.db.drop_all()

    def test_midpoint(self):
        kiko = model.User.query.get(2)

        self.assertEqual(len(kiko.concerts), 2)
        self.assertEqual(len(kiko.past_concerts), 1)
        self.assertEqual(kiko.past_concerts[0].artist, 'Cakes Da Killa')
        self.assertEqual(len(kiko.future_concerts), 1)
        self.assertEqual(kiko.future_concerts[0].artist, 'Sleigh Bells')

    def test_profile(self):
        result = self.client.get('/my-profile')
        self.assertEqual(result.status_code, 200)
        self.assertIn(': Your Profile', result.data.decode('utf-8'))

        self.assertIn('<h1>Your profile</h1>', result.data.decode('utf-8'))
        self.assertIn('Email: kiko@creat.er', result.data.decode('utf-8'))

        self.assertIn('<h4>Sleigh Bells</h4>', result.data.decode('utf-8'))
        self.assertIn('Outside Lands', result.data.decode('utf-8'))
        self.assertIn('<input type="hidden" class="map-lat" value="35.0">', result.data.decode('utf-8'))
        self.assertIn('<input type="hidden" class="map-lng" value="-123.0">', result.data.decode('utf-8'))
        self.assertIn('<input type="hidden" class="songkick-id" value="3">', result.data.decode('utf-8'))
        self.assertRegexpMatches(result.data.decode('utf-8'), 'Fri Aug 11, 2017\s+to Sun Aug 13, 2017')
        self.assertIn('View this event on Songkick', result.data.decode('utf-8'))

        self.assertNotIn('<h4>Cakes Da Killa</h4>', result.data.decode('utf-8'))
        self.assertNotIn('Mykki Blanco &amp; Cakes Da Killa', result.data.decode('utf-8'))

    def test_past(self):
        result = self.client.get('/my-profile/past')
        self.assertEqual(result.status_code, 200)
        self.assertIn(': Your Past Concerts', result.data.decode('utf-8'))

        self.assertIn('<h1>Your past concerts</h1>', result.data.decode('utf-8'))
        self.assertIn('Email: kiko@creat.er', result.data.decode('utf-8'))

        self.assertIn('<h4>Cakes Da Killa</h4>', result.data.decode('utf-8'))
        self.assertIn('Mykki Blanco &amp; Cakes Da Killa', result.data.decode('utf-8'))
        self.assertIn('The New Parish', result.data.decode('utf-8'))
        self.assertIn('src="https://i.scdn.co/image/0aee878e922c97b73cbef3aa590781a615313791"', result.data.decode('utf-8'))
        self.assertRegexpMatches(result.data.decode('utf-8'), 'Fri Mar 03, 2017\s+at 8:00 PM')
        self.assertIn('View this event on Songkick', result.data.decode('utf-8'))

        self.assertNotIn('<h4>Sleigh Bells</h4>', result.data.decode('utf-8'))
        self.assertNotIn('Outside Lands', result.data.decode('utf-8'))


class TestFrozenEarly(unittest.TestCase):
    def setUp(self):
        model.connect_to_db(server.app, "postgresql:///testconsa")
        model.db.create_all()
        model.example_data()

        with freeze_time('2016-06-01 23:00:00', tz_offset=-7):
            model.User.future_concerts = model.db.relationship("Concert",
                                                               order_by="Concert.start_datetime",
                                                               secondary="users_concerts",
                                                               secondaryjoin=model.db.and_(model.UserConcert.songkick_id == model.Concert.songkick_id,
                                                                                           model.Concert.start_datetime > datetime.now()))
            model.User.past_concerts = model.db.relationship("Concert",
                                                             order_by="Concert.start_datetime.desc()",
                                                             secondary="users_concerts",
                                                             secondaryjoin=model.db.and_(model.UserConcert.songkick_id == model.Concert.songkick_id,
                                                                                         model.Concert.start_datetime < datetime.now()))

    def tearDown(self):
        model.db.session.close()
        model.db.drop_all()

    def test_way_past(self):
        kiko = model.User.query.get(2)
        self.assertEqual(len(kiko.past_concerts), 0)
        self.assertEqual(len(kiko.future_concerts), 2)
        self.assertEqual(kiko.future_concerts[0].artist, 'Cakes Da Killa')


class TestFrozenFuture(unittest.TestCase):
    def setUp(self):
        model.connect_to_db(server.app, "postgresql:///testconsa")
        model.db.create_all()
        model.example_data()

        with freeze_time('2018-06-01 23:00:00', tz_offset=-7):
            model.User.future_concerts = model.db.relationship("Concert",
                                                               order_by="Concert.start_datetime",
                                                               secondary="users_concerts",
                                                               secondaryjoin=model.db.and_(model.UserConcert.songkick_id == model.Concert.songkick_id,
                                                                                           model.Concert.start_datetime > datetime.now()))
            model.User.past_concerts = model.db.relationship("Concert",
                                                             order_by="Concert.start_datetime.desc()",
                                                             secondary="users_concerts",
                                                             secondaryjoin=model.db.and_(model.UserConcert.songkick_id == model.Concert.songkick_id,
                                                                                         model.Concert.start_datetime < datetime.now()))

    def tearDown(self):
        model.db.session.close()
        model.db.drop_all()

    def test_way_future(self):
        kiko = model.User.query.get(2)
        self.assertEqual(len(kiko.future_concerts), 0)
        self.assertEqual(len(kiko.past_concerts), 2)
        self.assertEqual(kiko.past_concerts[0].artist, 'Sleigh Bells')


if __name__ == "__main__":
    unittest.main()
