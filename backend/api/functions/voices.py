from backend.functions import ValidationError
from bs4 import BeautifulSoup
import requests
import asyncio
import aiohttp
import time


class Voices:
	def __init__(self, media_type, imdb_id, accepted_voices, season=None, episode=None):
		self.start_t = time.time()
		self.media_type = media_type
		self.imdb_id = imdb_id
		self.accepted_voices = accepted_voices
		self.season = season
		self.episode = episode
		self._validate_params()
		self.base_link = f'https://voidboost.tv/embed/{self.imdb_id}'
		self.extended_link = f'{self.base_link}?s={self.season}&e={self.episode}'
		self.voices = None
		self.session = None
		self.loop = None
		self.result = None
		self.available_voices = dict()
		self._start()

	@staticmethod
	def _check_connection(imdb_id):
		r = requests.get(f'http://voidboost.tv/embed/{imdb_id}')
		return True if r.status_code == 200 else False

	@classmethod
	def check_conn(cls, imdb_id):
		return cls._check_connect(imdb_id)

	def _validate_params(self):
		if not self.media_type and not self.imdb_id:
			raise ValidationError('common', 'field_absence')
		if self.media_type == 'tv':
			if not self.season and not self.episode:
				raise ValidationError('common', 'field_absence')

	async def _is_available_link(self, voice_id, voice_name):
		link = f'{self.extended_link}&t={voice_id}' if self.media_type == 'tv' else self.base_link
		async with self.session.get(url=link) as resp:
			if resp.status == 200:
				self.available_voices.update({voice_id: voice_name})

	async def _get_voices(self):
		link = self.extended_link if self.media_type == 'tv' else self.base_link
		async with self.session.get(url=link) as resp:
			response = await resp.text()
		self.voices = self._parse_voices(response)
		tasks = []
		for voice_id, voice_name in self.voices.items():
			task = asyncio.create_task(self._is_available_link(voice_id, voice_name))
			tasks.append(task)
		await asyncio.gather(*tasks)

	async def _init_session(self):
		self.loop = asyncio.get_event_loop()
		self.session = aiohttp.ClientSession(trust_env=True)

	async def _close_session(self):
		await self.session.close()

	async def _main(self):
		await self._init_session()
		await self._get_voices()
		end = time.time()
		self.result = {'consumed': round(end - self.start_t, 1), 'results': self.available_voices}
		await self._close_session()

	def _parse_voices(self, page):
		soup = BeautifulSoup(page, 'html.parser')
		objects = dict()
		try:
			voices = soup.select('.video_selectors > select[name=translator] > option')
			for option in voices:
				voice_id = option.__getitem__('value')[:-1]
				title = option.get_text(strip=True)
				if voice_id != '' and int(voice_id) in list(self.accepted_voices.keys()):
					objects[voice_id] = title
			return objects
		except Exception as _ex:
			print(f'[ERROR]: {type(_ex)} | {str(_ex)}')

	def _start(self):
		asyncio.run(self._main())
