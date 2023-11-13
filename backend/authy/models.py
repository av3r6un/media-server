from django.contrib.auth.hashers import make_password, check_password
from backend.functions import ValidationError, allowed_filename
from datetime import datetime as dt
from django.db import models as md
from backend.config import Config
from api.models import Watching
from PIL import Image
import numpy as np
import os.path
import secrets
import string
import re


class Users(md.Model):
	uid = md.CharField(max_length=5, primary_key=True)
	username = md.CharField(max_length=100, null=False, unique=True)
	email = md.EmailField(max_length=100, null=False, unique=True)
	password = md.CharField(max_length=255, null=False)
	avatar = md.CharField(max_length=16, null=False, default='default.jpg')
	avatar_color = md.CharField(max_length=7, null=False, default='#0d7e80')
	is_admin = md.BooleanField(null=False, default=False)
	age = md.IntegerField(null=False)
	chosen_voice = md.CharField(max_length=3, null=True)
	share_downloads = md.BooleanField(null=False, default=False)
	auto_search = md.BooleanField(null=False, default=False)
	seen_media = md.ManyToManyField('api.MediaElements')

	@property
	def watching(self):
		return Watching.objects.filter(user_uid=self.uid).order_by('-datetime')

	def save(self, *args, **kwargs):
		if not self.uid:
			self._validate_data()
			self.uid = self._create_uid()
		super(Users, self).save(*args, **kwargs)

	def _validate_data(self):
		self.username = self._validate_username(self.username)
		self.email = self._validate_email(self.email)
		self.password = self._validate_passwords(self.password)
		self.age = self._validate_age(self.age)

	@staticmethod
	def _create_uid():
		uids = [a.uid for a in Users.objects.all()]
		alp = string.ascii_letters + string.digits
		while True:
			uid = ''.join(secrets.choice(alp) for _ in range(5))
			if uid not in uids:
				return uid

	def _validate_username(self, username):
		if self.username == username:
			return username
		user = Users.objects.filter(username=username)
		alp = string.ascii_letters + string.digits
		if not user:
			if len(username) >= 5:
				for l in username:
					if l not in alp:
						raise ValidationError('username', 'lang')
				return username
			else:
				raise ValidationError('username', 'shortness')
		else:
			raise ValidationError('username', 'exists')

	def check_pwd(self, password):
		if check_password(password, self.password):
			return True
		else:
			raise ValidationError('password', 'sameness')

	@staticmethod
	def _validate_passwords(passwords: list | tuple):
		pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8,}$'
		if not passwords:
			raise ValidationError('common', 'field_absence')
		pass1, pass2 = passwords
		if pass1 == pass2:
			if re.match(pattern, pass1) or pass1 == 'admin':
				return make_password(pass1)
			else:
				raise ValidationError('password', 'weakness')
		else:
			raise ValidationError('password', 'sameness')

	def _validate_email(self, email):
		if self.email == email:
			return email
		email_ = Users.objects.filter(email=email)
		pattern = r'^\S+@\S+\.\S+$'
		if not email_:
			if re.match(pattern, email):
				return email
			else:
				raise ValidationError('email', 'validity')
		else:
			raise ValidationError('email', 'exists')

	@staticmethod
	def create_avatar_uid(ext):
		uids = [a.avatar.replace(ext, '') for a in Users.objects.all()]
		alp = string.ascii_letters + string.digits
		while True:
			uid = ''.join(secrets.choice(alp) for _ in range(12))
			if uid not in uids:
				return f'{uid}{ext}'

	def _download_image(self, file):
		if file and allowed_filename(file.name):
			ext = f".{file.name.split('.')[-1]}"
			uid = self.create_avatar_uid(ext)
			self.avatar = uid
			filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../', f'storage/pics/{uid}')
			with open(filepath, 'wb') as avatar:
				avatar.write(file.read())
			self.avatar_color = self._detect_avatar_color(filepath)

	def mark_seen(self, media):
		seen_media_uids = [a.uid for a in self.seen_media.all()]
		self.seen_media.add(media) if media.uid not in seen_media_uids else None
		self.save()

	@staticmethod
	def _detect_avatar_color(filepath):
		img_array = np.array(Image.open(filepath))
		average_color = np.mean(img_array, axis=(0, 1)).astype(int)
		hexed = '#{0:02X}{1:02X}{2:02X}'.format(average_color[0], average_color[1], average_color[2])
		return hexed

	@staticmethod
	def _validate_age(birthday):
		if type(birthday) == int or birthday.isdigit():
			if len(birthday) == 2:
				return birthday
			else:
				raise ValidationError('birthday', 'too_much')
		else:
			raise ValidationError('birthday', 'wrong_format')

	@staticmethod
	def _validate_voice(voice_id):
		config = Config()
		if int(voice_id) in config.VOICES.keys():
			return voice_id
		else:
			raise ValidationError('voice', 'not_found')

	def choose_voice(self, voice):
		if not voice:
			return None
		self.chosen_voice = self._validate_voice(voice)
		self.save()

	def toggle_auto_search(self):
		self.auto_search = not self.auto_search
		self.save()

	def edit(self, username, auto_search=None, voice=None, avatar=None, share_downloads=None):
		username = None if username == 'null' else username
		self.username = self._validate_username(username) if username else self.username
		self._download_image(avatar)
		self.chosen_voice = self._validate_voice(voice) if voice else None
		self.auto_search = True if auto_search == 'on' else False
		self.share_downloads = True if share_downloads == 'on' else False
		self.save()

	def json(self):
		return {'uid': self.uid, 'username': self.username, 'is_admin': self.is_admin, 'age': self.age,
				'chosen_voice': self.chosen_voice, 'auto_search': self.auto_search, 'avatar': self.avatar,
				'user_color': self.avatar_color, 'share_downloads': self.share_downloads}

	def __repr__(self):
		return f'<User {self.uid}>'

	class Meta:
		verbose_name = 'Users'
		db_table = 'users'
