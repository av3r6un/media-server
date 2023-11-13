from api.models import MediaElements, MediaImages, Episodes, EpisodeImages
from backend.functions import ValidationError
from datetime import datetime as dt
from backend.config import Config
import requests

config = Config()


def ask_backend(endpoint, method, heads=None, data=None, json=None, timeout=30):
	resp = requests.request(method, f'{config.ENGINE}/{endpoint}', headers=heads, data=data, json=json, timeout=timeout)
	try:
		r = None
		if resp.status_code == 200:
			r = resp.json()
		if not r:
			raise ValidationError('common', 'connection_error')
		return r.get('results')
	except requests.JSONDecodeError:
		raise ValidationError('common', 'response_error')
	except requests.ConnectTimeout:
		raise ValidationError('common', 'slow_internet_connection')
	except requests.ConnectionError:
		raise ValidationError('common', 'connection_error')


def check_air_date(air_date):
	air_date = dt.strptime(air_date, '%Y-%m-%d')
	if dt.now() < air_date:
		raise ValidationError('episode', 'upcoming')


def parse_item(media_type, **kwargs):
	form = {k: v for k, v in kwargs.items()}
	element = MediaElements.objects.filter(uid=kwargs.get('mediaUid'))
	episode = Episodes.objects.filter(media_uid=kwargs.get('mediaUid'), season=kwargs.get('season'),
									  episode=kwargs.get('episode'))
	objs = {
		'tv': {'name': 'Сериал', 'table': MediaElements, 'images': MediaImages, 'db_field': 'media_images',
			   'current': element},
		'movie': {'name': 'Фильм', 'table': MediaElements, 'images': MediaImages, 'db_field': 'media_images',
				  'current': element},
		'episode': {'name': 'Эпизод', 'table': Episodes, 'images': EpisodeImages, 'db_field': 'preview',
					'current': episode},
	}
	if objs[media_type]['current']:
		raise ValidationError(media_type, 'exists')
	result = ask_backend(f'parse/{media_type}', 'POST', data=form)
	media_images = objs[media_type]['images'].objects.create(**result['images'])
	result.pop('images')
	result['media_type'] = media_type
	if media_type == 'episode':
		result.update({'season': kwargs.get('season'), 'episode': kwargs.get('episode'), 'media_uid': element.first()})
		check_air_date(result['air_date'])
		result.pop('air_date')
		result.pop('media_type')
	result[objs[media_type]['db_field']] = media_images
	item = objs[media_type]['table'].objects.create(**result)
	return item.uid
