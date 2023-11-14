from . import ValidationError, decrypt_data
from datetime import datetime as dt, timedelta as delta
from django.conf import settings
import sys
import os

if sys.platform == 'linux':
	from jwt import JWT

	def decode(message, key, algorithms):
		jwt = JWT()
		return jwt.decode(message, key, algorithms)
else:
	from jwt import decode


def folder_checker(base_folder, system_folders):
	if os.path.exists(base_folder):
		for index, folder in enumerate(system_folders):
			dir_path = os.path.join(base_folder, folder)
			try:
				if not os.path.exists(dir_path):
					os.mkdir(dir_path.title())
				else:
					continue
			except Exception as _ex:
				print(_ex)
				return False
		return True
	else:
		return False


def allowed_filename(filename):
	from backend.config import Config
	config = Config()
	return '.' in filename and filename.rsplit('.', 1)[1] in config.ALLOWED_EXTENSIONS


def file_analyzer(filename, runtime):
	if not os.path.exists(filename):
		raise ValidationError('common', 'not_found')
	if not os.path.exists(filename):
		raise ValidationError('analyzer', 'not_found')
	with open(filename, 'r', encoding='utf-8') as file:
		file_lines = file.readlines()
	info = {k.strip(): v.strip() for k, v in (line.split('=') for line in file_lines)}
	out_ms = info.get('out_time_ms')
	if not out_ms:
		return 'continue', 0.0
	percent = round((float(int(out_ms) / 1000000) / (runtime * 60)) * 100, 1)
	return info.get('progress'), percent


def file_deleter(filepath):
	from . import Config
	config = Config()
	requested = os.path.join(config.STORAGE, filepath)
	if not os.path.exists(requested):
		raise ValidationError('common', 'not_found')
	try:
		os.remove(requested)
		return True
	except Exception as _ex:
		print(f'{str(_ex)}')
		return False


def get_user_info(token):
	from authy.models import Users
	decoded_token = decode(token, settings.SECRET_KEY, algorithms=['HS256'])
	user_id = decoded_token['sub']
	user = Users.objects.get(username=user_id)
	if not user:
		raise ValidationError('username', 'not_found')
	return user.json()


def get_user(token):
	from authy.models import Users
	decoded_token = decode(token, settings.SECRET_KEY, algorithms=['HS256'])
	user_id = decoded_token['sub']
	user = Users.objects.get(username=user_id)
	return user


def get_jwt_identity(token):
	decoded_token = decode(token, settings.SECRET_KEY, algorithms=['HS256'])
	return decoded_token['sub']


def is_seen(timestamp, duration):
	if timestamp and duration:
		return ((int(timestamp) / int(duration)) * 100) >= 93


def near_time(time: str):
	diff = delta(minutes=1)
	time_diff = dt.now() - dt.strptime(time, '%Y%m%d%H%M')
	return time_diff <= diff


def is_valid_signature(headers):
	from backend.config import Config
	from authy.models import Users
	config = Config()
	signature, referrer = headers.get('X-Signature'), headers.get('X-Referrer')
	secret, datetime, uuid = decrypt_data(settings.CAC_KEY, signature).split('&')
	user = Users.objects.filter(uid=uuid).first()
	if referrer in config.CAC_REFERRERS and secret == config.SECRET and near_time(datetime) and user:
		return True
	return False
