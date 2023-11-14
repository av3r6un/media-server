from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
import selenium.webdriver.common.devtools.v85.runtime
from selenium.webdriver.chrome.service import Service
from backend.functions import ValidationError
from selenium.webdriver.common.by import By
from selenium.webdriver import Chrome
from seleniumwire import webdriver
from munch import DefaultMunch
from fake_useragent import UserAgent
import yaml
import time
import sys
import os


class LocalStorage:
	def __init__(self, driver: Chrome):
		self.driver = driver

	def __len__(self):
		return self.driver.execute_script('return window.localStorage.length;')

	def items(self):
		script = "var ls = window.localStorage, items = {}; " \
				 "for (var i = 0, k; i < ls.length; ++i) " \
				 "	items[k = ls.key(i)] = ls.getItem(k); " \
				 "return items;"
		return self.driver.execute_script(script)

	def keys(self):
		script = "var ls = window.localStorage, keys = []; " \
				 "for (var i = 0; i < ls.length; ++i) " \
				 "	keys[i] = ls.key(i); " \
				 "return keys;"
		self.driver.execute_script(script)

	def get(self, key):
		return self.driver.execute_script("return window.localStorage.getItem(arguments[0]);", key)

	def set(self, key, value):
		return self.driver.execute_script("window.localStorage.setItem(arguments[0], arguments[1]);", key, value)

	def has(self, key):
		return key in self.keys()

	def remove(self, key):
		self.driver.execute_script("window.localStorage.removeItem(arguments[0]);", key)

	def clear(self):
		self.driver.execute_script("window.localStorage.clear();")

	def __getitem__(self, key):
		value = self.get(key)
		if value is None:
			raise KeyError(key)
		return value

	def __setitem__(self, key, value):
		self.set(key, value)

	def __contains__(self, key):
		return key in self.keys()

	def __iter__(self):
		return self.items().__iter__()

	def __repr__(self):
		return self.items().__str__()


class MetaEngine:
	langs = {'eng': 'English', 'rus': 'Русский'}
	default_config = {
		'pljsquality': {'default': '480p', 'user': None},
		'pljssubtitle': {'default': 'откл.', 'user': None},
		'pljsuserid': {'default': 'qajnwp9dd8', 'user': None},
		'changes': False
	}
	buttons = {
		'set_cont': "//body/div[@id='player']/pjsdiv[@id='oframeplayer']/pjsdiv[19]/pjsdiv[1]/pjsdiv[1]",
		'settings': "//body/div[@id='player']/pjsdiv[@id='oframeplayer']/pjsdiv[12]/pjsdiv[3]",
		'qual': "//body/div[@id='player']/pjsdiv[@id='oframeplayer']/pjsdiv[19]/pjsdiv[1]/pjsdiv[1]/pjsdiv[1]",
		'set_subs': "//body/div[@id='player']/pjsdiv[@id='oframeplayer']/pjsdiv[19]/pjsdiv[1]/pjsdiv[1]/pjsdiv[3]",
		'set_sub_cont': "//body/div[@id='player']/pjsdiv[@id='oframeplayer']/pjsdiv[19]/pjsdiv[1]/pjsdiv[1]",
		'subtitles_cont': "//body/div[@id='player']/pjsdiv[@id='oframeplayer']/pjsdiv[@id='player_control_cc']/pjsdiv[3]",
	}
	chromedriver = (
		os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../../', 'apps/chromedriver.exe')
		if sys.platform != 'linux'
		else '/usr/bin/chromedriver'
	)
	config_path = os.path.join(
		os.path.abspath(os.path.dirname(__file__)), '../../', 'backend/config/driver-settings.yaml'
	)

	def __init__(self):
		self.start_t = time.time()
		self.media_type = None
		self.imdb_id = None
		self.season = None
		self.episode = None
		self.voice = None
		self.sub_lang = None
		self.c = self._init_config()
		self.requests = dict()
		self.user_agent = UserAgent().random
		self.opts = webdriver.ChromeOptions()
		self._apply_opts()
		self.service = Service(executable_path=self.chromedriver)
		self.driver = webdriver.Chrome(options=self.opts, service=self.service)
		self.local_storage = LocalStorage(self.driver)

	def _init_config(self):
		if not os.path.exists(self.config_path):
			data = self._save_config()
		else:
			with open(self.config_path, 'r', encoding='utf-8') as file:
				data = yaml.safe_load(file)
		return DefaultMunch.fromDict(data, default=object())

	def _save_config(self, config: dict = None):
		if not config:
			config = self.default_config
		with open(self.config_path, 'w', encoding='utf-8') as file:
			yaml.safe_dump(config, file, allow_unicode=True, encoding='utf-8')
		return config

	def _apply_opts(self):
		self.opts.add_argument('--headless')
		self.opts.add_argument('--disable-gpu')
		self.opts.add_argument('--ignore-certificate-errors')
		self.opts.add_argument('--disable-dev-shm-usage')
		self.opts.add_argument('--no-sandbox')
		self.opts.add_argument('--log-level=3')
		self.opts.add_argument('--disable-3d-apis')
		self.opts.add_argument(f'user-agent={self.user_agent}')
		if sys.platform == 'linux':
			self.opts.binary_location = '/usr/bin/chromium-browser'

	def _validate_params(self):
		if not self.imdb_id and not self.media_type:
			raise ValidationError('common', 'field_absence')
		if self.media_type == 'tv' and not self.season and not self.episode:
			raise ValidationError('common', 'field_absence')
		if self.media_type and self.imdb_id:
			if not self.voice:
				raise ValidationError('common', 'field_absence')

	def _first_start(self, quality, user):
		if self.sub_lang:
			self.c.pljssubtitle['user'] = self.langs[self.sub_lang]
			self.local_storage.set('pljssubtitle', self.langs[self.sub_lang])
			self.config['pljssubtitle'].update({'user': self.langs[self.sub_lang]})
		else:
			self.local_storage.set('pljssubtitle', self.c.pljssubtitle['default'])
		self.c.pljsuserid['user'] = user
		self.config['pljsuserid'].update({'user': user})
		self.local_storage.set('pljsuserid', user)
		self.c.pljsquality['user'] = quality
		self.config['pljsquality'].update({'user': f'{quality}p'})
		self.local_storage.set('pljsquality', quality)
		self.c.changes = True
		self.config['changes'] = True
		self._save_config(self.config)

	def edit_config(self, key, value):
		config = self.c.__dict__
		config[f'pljs{key}']['user'] = value
		self._save_config(config)

	def _is_first_start(self):
		return not self.c.changes

	def _parse_requests(self, parse_subtitles=True):
		data = {'video_src': None, 'sub_src': None}
		for request in self.driver.requests:
			if request.response and request.response.status_code == 200:
				if request.response.headers['Content-Type'] == 'application/vnd.apple.mpegurl':
					data.update({'video_src': request.url})
				if parse_subtitles:
					if request.response.headers['Content-Type'] == 'application/octet-stream':
						data.update({'sub_src': request.url})
		return data

	def _get_highest_quality(self):
		self.driver.find_element(by=By.XPATH, value=self.buttons['settings']).click()
		self.driver.implicitly_wait(0.45)
		self.driver.find_element(by=By.XPATH, value=self.buttons['qual']).click()
		qus = self.driver.find_element(by=By.XPATH, value=self.buttons['set_cont']).find_elements(by=By.TAG_NAME,
																								  value='pjsdiv')
		quality = {}
		for q in qus:
			if q.get_attribute('f2id'):
				if int(q.get_attribute('f2id')) > 0:
					q_text = q.find_element(by=By.CSS_SELECTOR, value='pjsdiv:nth-child(3)').text.replace('p', '')
					quality[int(q_text)] = q
		highest = max(quality.keys())
		return highest

	def _select_subtitles(self):
		self.driver.find_element(by=By.XPATH, value=self.buttons['settings']).click()
		time.sleep(0.45)
		self.driver.find_element(by=By.XPATH, value=self.buttons['set_subs']).click()
		time.sleep(0.45)
		subs = self.driver.find_element(by=By.XPATH, value=self.buttons['set_cont']).find_elements(by=By.TAG_NAME,
																								   value='pjsdiv')
		for s in subs:
			try:
				if s.get_attribute('f2id'):
					if int(s.get_attribute('f2id')) > 0:
						s_text = s.find_element(by=By.CSS_SELECTOR, value='pjsdiv:nth-child(3)').text
						if s_text == self.langs[self.sub_lang]:
							s.click()
			except StaleElementReferenceException:
				continue

	def _run(self):
		if self.media_type == 'tv':
			link = f'https://voidboost.tv/embed/{self.imdb_id}?t={self.voice}&e={self.episode}&s={self.season}'
		else:
			link = f'https://voidboost.tv/embed/{self.imdb_id}?t={self.voice}'
		self.driver.get(link)
		if self._is_first_start():
			quality = self._get_highest_quality()
			userid = self.local_storage.get('pljsuserid')
			self.first_start(quality, userid)
		self.local_storage.set('pljsquality', self.c.pljsquality['user'])
		self.local_storage.set('pljsuserid', self.c.pljsuserid['user'])
		if self.sub_lang:
			self.local_storage.set('pljssubtitle', self.c.pljssubtitle['default'])
		self.driver.refresh()
		time.sleep(0.45)
		if self.sub_lang:
			self._select_subtitles()
			time.sleep(1)
			self.requests.update(self._parse_requests())
		else:
			self.requests.update(self._parse_requests(parse_subtitles=False))

	def get_meta(self, media_type, imdb_id, voice, episode=None, season=None, sub_lang=None):
		self.media_type = media_type
		self.imdb_id = imdb_id
		self.voice = voice
		self.episode = episode
		self.season = season
		self.sub_lang = sub_lang
		self._validate_params()
		try:
			self._run()
			return {'status': 'success', 'results': self.requests, 'consumed': f'{round(time.time() - self.start_t)}s'}
		except NoSuchElementException or KeyError or Exception as _ex:
			print(f'[ERROR]: {type(_ex)} | {str(_ex)}')
			return {'status': 'error'}
		finally:
			self.driver.close()
			self.driver.quit()
