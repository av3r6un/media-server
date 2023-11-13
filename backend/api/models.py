from datetime import datetime as dt
from backend.functions import ValidationError
from django.db import models as md
from django.conf import settings
import requests
import secrets
import string
import os


class MediaImages(md.Model):
	uid = md.CharField(max_length=8, primary_key=True)
	poster = md.CharField(max_length=255, null=False, blank=False, unique=True)
	backdrop = md.CharField(max_length=255, null=False, blank=False, unique=True)
	logo = md.CharField(max_length=255, null=True, blank=True, unique=True)

	def save(self, *args, **kwargs):
		if not self.uid:
			self.uid = self._create_uid()
		self.poster = self._download_image('poster', self.poster)
		self.backdrop = self._download_image('backdrop', self.backdrop)
		self.logo = self._download_image('logo', self.logo)
		super(MediaImages, self).save(*args, **kwargs)

	@staticmethod
	def _create_uid():
		uids = [a.uid for a in MediaImages.objects.all()]
		alp = string.ascii_letters + string.ascii_letters
		while True:
			uid = ''.join(secrets.choice(alp) for _ in range(8))
			if uid not in uids:
				return uid

	def _download_image(self, img_type, link):
		if not link:
			return None
		ext = '.png' if img_type == 'logo' else '.jpg'
		img_link = link if img_type == 'logo' else f'{settings.IMAGE_STORAGE}/{link}'
		name = f'{self.uid}-{img_type[0]}{ext}'
		if not os.path.exists(f'{settings.MEDIA_ROOT}/images'):
			os.mkdir(f'{settings.MEDIA_ROOT}/images')
		try:
			with open(f'{settings.MEDIA_ROOT}/images/{name}', 'wb') as file:
				file.write(requests.get(f'{img_link}').content)
			return name
		except Exception as _ex:
			print(_ex)
			return None

	def _download_file(self, file, hint):
		if not file and not hint:
			raise ValidationError('common', 'field_absence')
		if not file:
			if hint == 'logo':
				return None
			else:
				return False
		if file:
			file.save(f'{settings.MEDIA_ROOT}/images/{getattr(self, hint)}')
		return getattr(self.media_images, hint)

	def edit(self, backdrop, poster, logo):
		changed_backdrop = self._download_file(backdrop, 'backdrop')
		changed_poster = self._download_file(poster, 'poster')
		self.logo = self._download_file(logo, 'logo')
		if changed_backdrop:
			self.backdrop = changed_backdrop
		if changed_poster:
			self.poster = changed_poster
		self.save()

	def json(self):
		return {'uid': self.uid, 'poster': self.poster, 'backdrop': self.backdrop, 'logo': self.logo}

	class Meta:
		verbose_name = 'Media Images'
		db_table = 'media_images'


class EpisodeImages(md.Model):
	uid = md.CharField(max_length=8, primary_key=True)
	preview = md.CharField(max_length=255, null=False)

	def save(self, *args, **kwargs):
		if not self.uid:
			self.uid = self._create_uid()
		self.preview = self._download_image(self.preview)
		super(EpisodeImages, self).save(*args, **kwargs)

	@staticmethod
	def _create_uid():
		uids = [a.uid for a in EpisodeImages.objects.all()]
		alp = string.ascii_letters + string.digits
		while True:
			uid = ''.join(secrets.choice(alp) for _ in range(8))
			if uid not in uids:
				return uid

	def _download_image(self, link):
		name = f'{self.uid}-p.jpg'
		if not os.path.exists(f'{settings.MEDIA_ROOT}/images'):
			os.mkdir(f'{settings.MEDIA_ROOT}/images')
		try:
			with open(f'{settings.MEDIA_ROOT}/images/{name}', 'wb') as file:
				file.write(requests.get(f'{settings.IMAGE_STORAGE}/{link}').content)
			return name
		except Exception as _ex:
			print(_ex)
			raise ValidationError('download', 'unknown')

	def _download_file(self, file, hint):
		if not file and not hint:
			raise ValidationError('common', 'field_absence')
		file.save(f'{settings.MEDIA_ROOT}/images/{getattr(self, hint)}')
		return getattr(self.media_images, hint)

	def edit(self, preview):
		changed_preview = self._download_file(preview, 'preview')
		if changed_preview:
			self.preview = changed_preview
		self.save()

	def json(self):
		return {'preview': self.preview}

	class Meta:
		verbose_name = 'Episode Images'
		db_table = 'episode_images'


class MediaElements(md.Model):
	uid = md.CharField(max_length=6, primary_key=True)
	media_type = md.CharField(max_length=5, null=False, blank=False)
	tmdb_id = md.IntegerField(null=False, blank=False)
	kp_id = md.IntegerField(null=False, blank=False)
	imdb_id = md.CharField(max_length=12, null=False, unique=True)
	name = md.CharField(max_length=50, null=False)
	original_name = md.CharField(max_length=50, null=False, blank=False)
	year = md.IntegerField(null=False, blank=False)
	age = md.IntegerField(null=False, default=0)
	media_images = md.OneToOneField(MediaImages, on_delete=md.CASCADE, related_name='media_elements')
	trailer = md.CharField(max_length=255, null=True)
	overview = md.TextField(null=True, blank=True)
	runtime = md.IntegerField(null=True, blank=True)
	last_release = md.IntegerField(null=True, blank=True)
	slogan = md.CharField(max_length=255, null=True, blank=True)
	seasons = md.IntegerField(null=True, blank=True)
	episodes = md.IntegerField(null=True, blank=True)
	seasons_meta = md.CharField(max_length=255, null=True, blank=True)
	tmdb_rate = md.FloatField(null=True, blank=True)
	kp_rate = md.FloatField(null=True, blank=True)
	imdb_rate = md.FloatField(null=True, blank=True)
	kp_url = md.CharField(max_length=32, null=True, blank=True)

	def save(self, *args, **kwargs):
		if not self.uid:
			self.uid = self._create_uid()
		self.original_name = self._validate_name(self.original_name)
		if self.media_type == 'tv':
			self.seasons_meta = self._validate_seasons(self.seasons, self.seasons_meta)
		super(MediaElements, self).save(*args, **kwargs)

	@property
	def extra(self):
		return Episodes.objects.filter(media_uid=self.uid)

	@property
	def meta(self):
		return MetaData.objects.filter(media_uid=self.uid).first()

	@staticmethod
	def _create_uid():
		uids = [a.uid for a in MediaElements.objects.all()]
		alp = string.ascii_letters + string.digits
		while True:
			uid = ''.join(secrets.choice(alp) for _ in range(6))
			if uid not in uids:
				return uid

	@staticmethod
	def _validate_seasons(seasons, seasons_meta):
		if not seasons_meta:
			return None
		if type(seasons_meta) == list:
			if len(seasons_meta) == seasons:
				return ','.join(seasons_meta)
			else:
				raise ValidationError('seasons', 'invalid_meta')
		else:
			if len(seasons_meta.split(',')) == seasons:
				return seasons_meta
			else:
				raise ValidationError('seasons', 'invalid_meta')

	@staticmethod
	def _validate_name(name):
		name = name.replace("DC's", "").replace("Marvel's", "")
		replacements = {':': '', "'": '', '?': '', '...': ''}
		return "".join(replacements.get(c, c) for c in name).strip('_').strip()

	@staticmethod
	def _validate_year(year):
		if not year:
			raise ValidationError('common', 'field_absence')
		return year

	def short_json(self):
		return {
			'uid': self.uid, 'name': self.name, 'media_type': self.media_type, 'year': self.year,
			'original_name': self.original_name, 'poster': self.media_images.poster, 'imdb_rate': self.imdb_rate
		}

	def short(self):
		return {'uid': self.uid, 'name': self.name, 'picture': self.media_images.backdrop, 'runtime': self.runtime,
				'type': self.media_type}

	def _extract_episodes(self):
		return [a.json() for a in self.extra]

	def episodes_info(self, user_uid):
		episodes = self._extract_episodes()
		watching = [watching.where_to_continue(user_uid) for watching in self.extra]
		watching_dict = {watching.episode_uid.uid: watching for watching in watching if watching is not None}
		for episode in episodes:
			if episode['uid'] in watching_dict:
				episode['continue'] = watching_dict[episode['uid']].timestamp
				episode['seen'] = watching_dict[episode['uid']].seen
			else:
				episode['seen'] = False
				episode['continue'] = 0
		return episodes

	def where_to_continue(self, user_uid):
		w = Watching.objects.filter(media_uid=self.uid, user_uid=user_uid).first()
		return w.timestamp if w else 0

	def is_seen(self, user_uid):
		s = Watching.objects.filter(media_uid=self.uid, user_uid=user_uid).first()
		return s.seen if s else False

	def extract_meta(self):
		if self.meta:
			return self.meta.json()
		return None

	def gather_episode_info(self, uid, episode, season, neighbors=False):
		prev_ep = None
		next_ep = None
		if neighbors:
			for episode_item in self.extra:
				if episode_item.episode == episode + 1 and episode_item.season:
					next_ep = episode_item.json()
				if episode_item.episode == episode - 1 and episode_item.season:
					prev_ep = episode_item.json()
		ep = Episodes.objects.filter(uid=uid, episode=episode, season=season).first()
		response = {
			'uid': self.uid, 'media_type': self.media_type, 'name': self.name, 'backdrop': self.media_images.backdrop,
			'logo': self.media_images.logo, 'episode': {
				'uid': ep.uid, 'name': ep.name, 'episode': ep.episode, 'season': ep.season, 'meta': ep.extract_meta(),
				'preview': ep.preview.preview, 'overview': ep.overview, 'short': {
					'imdb_id': self.imdb_id, 'season': ep.season, 'episode': ep.episode, 'media_type': self.media_type
				}, 'title': f'{self.name} - {ep.name} ({ep.season} сезон {ep.episode} серия)',
			}, 'prev_episode': prev_ep, 'next_episode': next_ep
		}
		return response

	def _season_items(self):
		return list(set([a.season for a in self.extra]))

	def short_info(self):
		return {'uid': self.uid, 'name': self.name, 'additional': self.year, 'picture': self.media_images.backdrop}

	def advice(self, user_uid):
		info = self.short_info()
		info.update({'continue': self.where_to_continue(user_uid), 'type': 'movie', 'runtime': self.runtime})
		return info

	def small_info(self, user_uid):
		data = {'uid': self.uid, 'poster': self.media_images.poster, 'name': self.name,
				'original_name': self.original_name}
		data.update(
			{} if self.media_type == 'tv' else {'seen': self.is_seen(user_uid), 'continue': self.where_to_continue(user_uid)}
		)
		return data

	def json(self, user_uid=None):
		data = {
			'uid': self.uid, 'media_type': self.media_type, 'tmdb_id': self.tmdb_id, 'kp_id': self.kp_id,
			'imdb_id': self.imdb_id, 'name': self.name, 'original_name': self.original_name, 'age': self.age,
			'poster': self.media_images.poster, 'backdrop': self.media_images.backdrop, 'logo': self.media_images.logo,
			'trailer': self.trailer, 'overview': self.overview, 'year': self.year, 'tmdb_rate': self.tmdb_rate,
			'kp_rate': self.kp_rate, 'imdb_rate': self.imdb_rate
		}
		updatable = (
			{'slogan': self.slogan, 'seasons': self.seasons, 'episodes': self.episodes, 'last_year': self.last_release,
			 'seasons_meta': self.seasons_meta, 'season_items': self._season_items()}
			if self.media_type == 'tv' else {'runtime': self.runtime, 'meta': self.extract_meta(),
											 'continue': self.where_to_continue(user_uid) if user_uid else 0,
											 'seen': self.is_seen(user_uid) if user_uid else False}
		)
		data.update(updatable)
		return data

	def _download_file(self, file, hint):
		if not file and not hint:
			raise ValidationError('common', 'field_absence')
		if not file:
			if hint == 'logo':
				return None
			else:
				return False
		if file:
			file.save(f'{settings.MEDIA_ROOT}/images/{getattr(self.media_images, hint)}')
		return getattr(self.media_images, hint)

	def edit(self, name, original_name, overview=None):
		changed_name = name if name != self.name else None
		changed_original = original_name if original_name != original_name else None
		self.overview = overview
		if changed_name:
			self.name = changed_name
		if changed_original:
			self.original_name = changed_original
		self.save()

	def __repr__(self):
		return f'<MediaElement #{self.uid} ({self.media_type})>'

	class Meta:
		verbose_name = 'Media Elements'
		db_table = 'media_elements'


class Episodes(md.Model):
	uid = md.CharField(max_length=7, primary_key=True)
	media_uid = md.ForeignKey('MediaElements', md.CASCADE, related_name='media_elements', to_field='uid', unique=False)
	name = md.CharField(max_length=120, null=False)
	season = md.IntegerField(null=False)
	episode = md.IntegerField(null=False)
	preview = md.OneToOneField(EpisodeImages, md.CASCADE, related_name='episode_preview')
	overview = md.TextField(null=False)
	runtime = md.IntegerField(null=False)

	@property
	def meta(self):
		return MetaData.objects.filter(episode_uid=self.uid).first()

	def save(self, *args, **kwargs):
		if not self.uid:
			self.uid = self._create_uid()
		self._validate_episode_info()
		super(Episodes, self).save(*args, **kwargs)

	@staticmethod
	def _create_uid():
		uids = [a.uid for a in Episodes.objects.all()]
		alp = string.ascii_letters + string.digits
		while True:
			uid = ''.join(secrets.choice(alp) for _ in range(7))
			if uid not in uids:
				return uid

	def _validate_episode_info(self):
		media = Episodes.objects.filter(media_uid=self.media_uid, season=self.season, episode=self.episode)
		if media:
			raise ValidationError('episode', 'exists')

	def _download_file(self, file):
		if not file:
			raise ValidationError('common', 'field_absence')
		file.save(f'{settings.MEDIA_ROOT}/images/{self.preview.preview}')
		return self.preview

	def edit(self, preview=None, name=None, overview=None):
		self.name = name if name else self.name
		self.overview = overview if overview else self.overview
		self.preview = self._download_file(preview) if preview else self.preview
		self.save()

	def where_to_continue(self, user_uid):
		return Watching.objects.filter(episode_uid=self.uid, user_uid=user_uid).first()

	def continue_info(self, user_uid):
		w = Watching.objects.filter(episode_uid=self.uid, user_uid=user_uid).first()
		return w.timestamp if w else 0

	def extract_meta(self):
		if self.meta:
			return self.meta.json()
		return None

	def short_info(self):
		title = f'{self.media_uid.name} {self.season} сезон {self.episode} серия'
		return {'uid': self.uid, 'name': title, 'additional': self.name, 'picture': self.preview.preview,
				'runtime': self.runtime, 'type': 'episode'}

	def advice(self, user_uid):
		info = self.short_info()
		info.update({'continue': self.continue_info(user_uid), 'media_uid': self.media_uid.uid, 'episode': self.episode,
					 'season': self.season})
		return info

	def json(self):
		data = {
			'uid': self.uid, 'media_uid': self.media_uid.uid, 'season': self.season, 'episode': self.episode,
			'preview': self.preview.preview, 'overview': self.overview, 'runtime': self.runtime, 'name': self.name,
			'meta': self.extract_meta()
		}
		return data

	def __repr__(self):
		return f'<Episode #{self.uid} for {self.media_uid}>'

	class Meta:
		verbose_name = 'Episodes'
		db_table = 'episodes'


class MetaData(md.Model):
	uid = md.CharField(max_length=9, primary_key=True)
	media_uid = md.ForeignKey(MediaElements, md.CASCADE, null=True)
	episode_uid = md.ForeignKey(Episodes, md.CASCADE, null=True)
	video_source = md.CharField(max_length=255, null=False)
	video_lang = md.CharField(max_length=15, null=False)
	sub = md.CharField(max_length=255, null=True, blank=True)
	sub_lang = md.CharField(max_length=15, null=True, blank=True)
	filename = md.CharField(max_length=11, null=False, blank=True)
	downloaded = md.BooleanField(null=False, blank=False, default=False)

	def save(self, *args, **kwargs):
		if not self.uid:
			self.uid = self._create_uid()
		if not self.filename:
			self.filename = self._create_filename()
		self._validate_params()
		super(MetaData, self).save(*args, **kwargs)

	@staticmethod
	def _create_uid():
		uids = [a.uid for a in MetaData.objects.all()]
		alp = string.ascii_letters + string.digits
		while True:
			uid = ''.join(secrets.choice(alp) for _ in range(9))
			if uid not in uids:
				return uid

	@staticmethod
	def _create_filename():
		filenames = [a.filename for a in MetaData.objects.all()]
		alp = string.ascii_letters + string.digits
		while True:
			filename = ''.join(secrets.choice(alp) for _ in range(11))
			if filename not in filenames:
				return filename

	def _validate_params(self):
		if not self.episode_uid and not self.media_uid:
			raise ValidationError('common', 'field_absence')

	def edit(self, video_source, video_lang, sub=None, sub_lang=None):
		self.video_source = video_source
		self.video_lang = video_lang
		self.sub = sub
		self.sub_lang = sub_lang
		self.save()

	def mark_downloaded(self):
		self.downloaded = True
		self.save()
		return True

	def delete_(self):
		self.downloaded = False
		self.save()

	def cac_response(self):
		response = {'meta_uid': self.uid, 'video_source': self.video_source, 'video_lang': self.video_lang, 'sub': self.sub,
					'sub_lang': self.sub_lang, 'filename': self.filename}
		response.update(
			{'media_type': 'movie', 'uid': self.media_uid.uid, 'title': self.media_uid.name}
			if self.media_uid else
			{'media_type': 'tv', 'uid': self.episode_uid.uid,
			 'title': f'{self.episode_uid.media_uid.name} {self.episode_uid.season} сезон '
					  f'{self.episode_uid.episode} серия - {self.episode_uid.name}'}
		)
		return response

	def json(self):
		response = {'uid': self.uid, 'media_uid': self.media_uid.uid if self.media_uid else None,
					'episode_uid': self.episode_uid.uid if self.episode_uid else None,
					'downloaded': self.downloaded, 'filename': self.filename, 'sub_lang': self.sub_lang,
					'video_lang': self.video_lang}
		response.update({} if self.downloaded else {'video_source': self.video_source, 'sub': self.sub})
		return response

	def __repr__(self):
		return f'<Meta #{self.uid}>'

	class Meta:
		verbose_name = 'MetaData'
		db_table = 'meta'


class Watching(md.Model):
	uid = md.CharField(max_length=4, primary_key=True)
	user_uid = md.ForeignKey('authy.Users', md.CASCADE, related_name='user_watching', to_field='uid', unique=False)
	media_uid = md.ForeignKey(MediaElements, md.CASCADE, related_name='watching_media', null=True)
	episode_uid = md.ForeignKey(Episodes, md.CASCADE, related_name='watching_episode', null=True)
	timestamp = md.IntegerField(null=True)
	seen = md.BooleanField(null=False, default=False)
	hidden = md.BooleanField(null=False, default=False)
	datetime = md.IntegerField(null=False, default=int(dt.now().timestamp()))

	def save(self, *args, **kwargs):
		if not self.uid:
			self.uid = self._create_uid()
		self._validate_params()
		super(Watching, self).save(*args, **kwargs)

	@staticmethod
	def _create_uid():
		uids = [a.uid for a in Watching.objects.all()]
		alp = string.ascii_letters + string.digits
		while True:
			uid = ''.join(secrets.choice(alp) for _ in range(4))
			if uid not in uids:
				return uid

	def _validate_params(self):
		if not self.episode_uid and not self.media_uid:
			raise ValidationError('common', 'field_absence')

	def edit(self, timestamp, seen=False):
		self.timestamp = timestamp
		self.seen = seen
		self.datetime = int(dt.now().timestamp())
		self.save()

	def json(self, short=True):
		resp = {'uid': self.uid, 'timestamp': self.timestamp, 'seen': self.seen}
		resp.update({} if short else {'user_uid': self.user_uid, 'media_uid': self.uid, 'episode_uid': self.episode_uid})
		return resp

	def __repr__(self):
		return f'<Watching #{self.uid}>'

	class Meta:
		verbose_name = 'Watching'
		db_table = 'watching'


class Downloads(md.Model):
	uid = md.CharField(max_length=25, primary_key=True)
	user_uid = md.ForeignKey('authy.Users', md.CASCADE, related_name='downloads_user', to_field='uid', unique=False)
	media_uid = md.ForeignKey(MediaElements, md.CASCADE, related_name='downloads_media', null=True)
	episode_uid = md.ForeignKey(Episodes, md.CASCADE, related_name='downloads_episodes', null=True)
	datetime = md.IntegerField(null=False, default=int(dt.now().timestamp()))
	runtime = md.FloatField(null=True, blank=True)
	stage = md.BooleanField(null=False, default=False)

	def save(self, *args, **kwargs):
		if not self.uid:
			self.uid = self._create_uid()
		self._validate_params()
		super(Downloads, self).save(*args, **kwargs)

	@staticmethod
	def _create_uid():
		uids = [a.uid for a in Downloads.objects.all()]
		alp = string.ascii_letters + string.digits
		while True:
			uid = ''.join(secrets.choice(alp) for _ in range(25))
			if uid not in uids:
				return uid

	def _validate_params(self):
		if not self.episode_uid and not self.media_uid:
			raise ValidationError('common', 'field_absence')

	def change_stage(self, stage):
		self.stage = stage
		self.save()

	def full_clear(self):
		watch_id = self.episode_uid if self.episode_uid else self.media_uid
		filename = watch_id.meta.filename
		filenames = [f'downloads/{filename}.mp4', f'subtitles/{filename}.vtt', f'progress/{filename}.txt']
		for file in filenames:
			try:
				os.remove(f'{settings.MEDIA_ROOT}/{file}')
				watch_id.meta.downloaded = False
			except FileNotFoundError:
				raise ValidationError('common', 'exact_not_found', **{'<filename>': file})

	def clear(self, user):
		if user.is_admin:
			self.full_clear()
		self.delete()
		self.save()

	def json(self):
		response = {'uid': self.uid, 'datetime': self.datetime, 'completed': self.stage, 'runtime': self.runtime}
		response.update(
			{'watch_uid': self.media_uid.uid, 'preview': self.media_uid.media_images.backdrop, 'name': self.media_uid.name}
			if self.media_uid else
			{'watch_uid': self.episode_uid.uid, 'preview': self.episode_uid.preview.preview,
			 'name': f'{self.episode_uid.media_uid.name} {self.episode_uid.season} сезон {self.episode_uid.episode} серия',
			 'title': self.episode_uid.name}
		)
		return response

	def __repr__(self):
		return f'<Download #{self.uid}>'

	class Meta:
		verbose_name = 'Downloads'
		db_table = 'downloads'


class Queue(md.Model):
	id = md.IntegerField(primary_key=True)
	user_uid = md.OneToOneField('authy.Users', md.CASCADE, related_name='user_queue', null=False, unique=False)
	movies = md.ManyToManyField('MediaElements')
	episodes = md.ManyToManyField('Episodes')

	def save(self, *args, **kwargs):
		super(Queue, self).save(*args, **kwargs)

	def add_ids(self, episodes, movies):
		[self.movies.add(movie) for movie in movies if movie]
		[self.episodes.add(episode) for episode in episodes if episode]
		self.save()
		return self.id

	def cac_response(self):
		movies_meta = [a.meta.cac_response() for a in self.movies.all() if self.movies]
		episodes_meta = [a.meta.cac_response() for a in self.episodes.all() if self.episodes]
		return episodes_meta + movies_meta

	def current_items(self):
		movies = [a.uid for a in self.movies.all()]
		episodes = [a.uid for a in self.episodes.all()]
		return movies + episodes

	def json(self):
		movies = [a.uid for a in self.movies.all()]
		episodes = [a.uid for a in self.episodes.all()]
		return {'id': self.id, 'episodes': episodes, 'movies': movies}

	def pretty(self):
		movies = [a.short() for a in self.movies.all() if self.movies]
		episodes = [a.short_info() for a in self.episodes.all() if self.episodes]
		return {'id': self.id, 'queue': movies + episodes}

	def clear_queue(self):
		movies = [a for a in self.movies.all()]
		[self.movies.remove(movie) for movie in movies]
		episodes = [a for a in self.episodes.all()]
		[self.episodes.remove(episode) for episode in episodes]
		self.save()

	def __repr__(self):
		return f'<Queue #{self.uid}>'

	class Meta:
		verbose_name = 'Queue'
		db_table = 'queue'
