from backend.functions import encrypt_data
from datetime import datetime as dt
from backend.config import Config
from django.conf import settings
from threading import Thread
import requests
import logging
import ffmpeg
import time
import os

LOGS_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../../', 'logs')

logging.basicConfig(
	filename=f'{LOGS_FOLDER}/download.log', level=logging.ERROR,
	format='%(asctime)s - %(levelname)s - %(message)s',
	datefmt='%H:%M:%S %d-%m-%Y', filemode='w'
)

config = Config()


class MetaEngineException(BaseException):
	""" :raises when occurs errors in MetaEngine"""
	messages = {
		'requests': {
			'slow_internet': 'Подключение было разорвано в связи с долгим подключение к серверу.',
			'connection_error': 'Ошибка подключения. Проверьте интернет соединение.'
		}
	}
	message = None

	def __init__(self, case, error, **kwargs):
		super(ValidationError, self).__init__()
		self._make_error(self.messages[case][error], **kwargs)

	def _make_error(self, message, **kwargs):
		self.message = f'{message}\n {" ".join([f"{k} {v}" for k, v in kwargs.items()]).strip()}'


class MediaEngineMeta:
	dfl_lng = config.DEFAULT_LANGS
	uid = None
	media_type = None
	meta_uid = None
	video_source = None
	video_lang = None
	sub = None
	sub_lang = None
	sub_t_lang = None
	filename = None
	title = None

	def __init__(self, uid, media_type, meta_uid, video_source, video_lang, sub, sub_lang, filename, title):
		self.uid = uid
		self.media_type = media_type
		self.meta_uid = meta_uid
		self.video_source = video_source
		self.video_lang = 'eng' if video_lang == '20' else 'rus'
		self.sub = sub
		self.sub_t_lang = self.dfl_lng[sub_lang]
		self.sub_lang = sub_lang
		self.filename = filename
		self.title = title


class MediaEngine:
	stg = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../../', 'storage')
	sbt_fldr = os.path.join(stg, 'subtitles')
	prg_fldr = os.path.join(stg, 'progress')
	dwl_fldr = os.path.join(stg, 'downloads')

	def __init__(self):
		self.uuid = None
		self.queue_id = None
		self.thread = None

	@staticmethod
	def _video_file_info(url):
		probe = ffmpeg.probe(url)
		response = {'a_c': probe['streams'][0]['codec_name'], 'v_c': probe['streams'][1]['codec_name'],
					'duration': round(float(probe['format']['duration']), 2)}
		return response

	@staticmethod
	def _download_subs(sub):
		_func_name_ = 'download_subs'
		req = requests.get(sub, timeout=25)
		try:
			return req.content
		except requests.Timeout or requests.ConnectTimeout:
			logging.error('Subtitles downloading timed out.')
			raise MetaEngineException('requests', 'slow_internet_connection', **{'RaisedBy': _func_name_})
		except requests.ConnectionError:
			logging.error('Subtitles downloading failed due to bad connection.')
			raise MetaEngineException('requests', 'connection_error', **{'RaisedBy': _func_name_})
		finally:
			req.close()

	def _cac_request(self, url, method, data: dict = None):
		_func_params_ = {'Method': method, 'URL': url, 'RaisedBy': 'cac_request'}
		headers = {'X-Signature': self._create_secret(), 'X-Referrer': 'MediaEngine'}
		req = requests.request(method, f'http://192.168.3.71:8000/{url}', headers=headers, json=data, timeout=10)
		try:
			r = None
			if req.status_code == 200:
				r = req.json()
			return r
		except requests.JSONDecodeError:
			logging.error('')
			raise MetaEngineException('requests', 'error_decoding_response', **_func_params_)
		except requests.Timeout or requests.ConnectTimeout:
			logging.error('')
			raise MetaEngineException('requests', 'slow_internet_connection', **_func_params_)
		except requests.ConnectionError:
			logging.error('')
			raise MetaEngineException('requests', 'connection_error', **_func_params_)
		except Exception as _ex:
			logging.error(f'Unknown Error: {str(_ex)}')
			_func_params_.update({'traceback': str(_ex)})
			raise MetaEngineException('common', 'unknown_error', **_func_params_)
		finally:
			req.close()

	def _create_secret(self):
		_func_name_ = 'create_secret'
		if not self.uuid:
			raise MetaEngineException('encryption', 'raised_before_asking', **{'RaisedBy': _func_name_})
		return encrypt_data(settings.CAC_KEY, f'{config.SECRET}&{dt.now().strftime("%Y%m%d%H%M")}&{self.uuid}')

	def _save_subtitles(self, filename, subtitles):
		fp = f'{self.sbt_fldr}/{filename}.vtt'
		with open(fp, 'wb') as f:
			f.write(subtitles)
		return fp

	def _collect_meta(self, filename):
		return MediaEngineMeta(**self._cac_request(f'api/cac/meta/{filename}', 'GET'))

	def _collect_queue(self, queue_id):
		queue = self._cac_request(f'api/cac/gather/queue/{queue_id}', 'GET')
		return [MediaEngineMeta(**q) for q in queue]

	def _clear_queue(self, queue_id, media_uid=None, episode_uid=None):
		json_data = {'media_uid': media_uid, 'episode_uid': episode_uid}
		return self._cac_request(f'api/cac/queue/{queue_id}', 'DELETE', data=json_data)

	def _initiate_downloading(self, media_type, uid, runtime):
		json_data = {'runtime': runtime, 'user_uid': self.uuid}
		json_data.update({'episode_uid': uid} if media_type == 'tv' else {'media_uid': uid})
		return self._cac_request(f'api/cac/download', 'POST', data=json_data)

	def _finish_downloading(self, meta_uid, download_uid, filename):
		os.remove(f'{self.prg_fldr}/{filename}.txt')
		return self._cac_request(f'api/cac/download', 'PUT',
								 data={'uid': download_uid, 'stage': True, 'meta_uid': meta_uid})

	def _start(self, filename, uuid):
		self.uuid = uuid
		meta = self._collect_meta(filename)
		self._convert(meta)

	def _start_multi(self, queue_id, uuid):
		self.queue_id = queue_id
		self.uuid = uuid
		queue = self._collect_queue(self.queue_id)
		for q in queue:
			result = self._convert(q)
			if result['status'] == 'success':
				qi = {'episode_uid': result['uid']} if result['media_type'] == 'tv' else {'media_uid': result['uid']}
				self._clear_queue(queue_id, **qi)

	def _start_ofq(self, queue_id, uid, uuid):
		self.queue_id = queue_id
		self.uuid = uuid
		queue = self._collect_queue(self.queue_id)
		meta = [q for q in queue if q.uid == uid][0]
		result = self._convert(meta)
		if result['status'] == 'success':
			qi = {'episode_uid': result['uid'] if result['media_type'] == 'tv' else {'media_uid': result['uid']}}
			self._clear_queue(queue_id, **qi)

	def _convert(self, meta: MediaEngineMeta):
		vfi = self._video_file_info(meta.video_source)
		v_codec = 'copy' if vfi['v_c'] in ['libx264', 'h264'] else 'libx264'
		download_uid = self._initiate_downloading(meta.media_type, meta.uid, vfi['duration'])['uid']
		sub_path = self._save_subtitles(meta.filename, self._download_subs(meta.sub)) if meta.sub else None
		params = {'c:v': v_codec, 'c:a': 'aac', 'strict': -2, 'format': 'mp4',
				  'metadata:s:a:0': f'language={meta.video_lang}', 'metadata': f'title={meta.title}'}
		args = ['-progress', f'{self.prg_fldr}/{meta.filename}.txt', '-loglevel', 'error']
		if sub_path:
			params.update({'c:s': 'mov_text', 'metadata:s:s:0': f'title={meta.sub_t_lang}:language={meta.sub_lang}'})
			args.insert(0, '-i')
			args.insert(1, sub_path)
		try:
			print('No way to turn back')
			process = (
				ffmpeg
				.input(meta.video_source)
				.output(f'{self.dwl_fldr}/{meta.filename}.mp4', **params)
				.global_args(*args)
				.overwrite_output()
				.run_async(pipe_stdout=True)
			)
			for line in process.stdout:
				logging.error(line.decode('utf-8').strip())
			process.wait()
			self._finish_downloading(meta.meta_uid, download_uid, meta.filename)
			return {'status': 'success', 'uid': meta.uid, 'media_type': meta.media_type}
		except Exception as _ex:
			print(type(_ex), str(_ex))
			logging.error(f'Converting error: {str(_ex)}')
			return {'status': 'error', 'uid': meta.uid, 'media_type': meta.media_type}

	def start(self, filename, uuid):
		self.thread = Thread(target=self._start, args=(filename, uuid,), daemon=True)
		self.thread.name = f'MetaEngine for {filename}'
		self.thread.start()
		time.sleep(1)
		if self.thread.is_alive():
			return {'status': 'success', 'thread_name': self.thread.name, 'message': 'Загрузка успешно началась'}

	def start_one_form_queue(self, queue_id, uid, uuid):
		self.thread = Thread(target=self._start_ofq, args=(queue_id, uid, uuid))
		self.thread.name = f'MetaEngine for {queue_id} | {uid}'
		self.thread.start()
		time.sleep(1)
		if self.thread.is_alive():
			return {'status': 'success', 'thread_name': self.thread.name, 'message': 'Загрузка успешно началась'}

	def start_multi(self, queue_id, uuid):
		self.thread = Thread(target=self._start_multi, args=(queue_id, uuid), daemon=True)
		self.thread.name = f'MetaEngine Queue for user {uuid}'
		self.thread.start()
		time.sleep(1)
		if self.thread.is_alive():
			return {'status': 'success', 'thread_name': self.thread.name, 'message': 'Загрузка очереди успешно началась.'}
