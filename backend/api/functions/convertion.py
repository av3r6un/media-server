from api.models import MetaData, Downloads, Queue, MediaElements, Episodes
from backend.functions import ValidationError
from backend.config import Config
import requests
import logging
import ffmpeg
import os

LOGS_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../../', 'logs')

logging.basicConfig(
	filename=f'{LOGS_FOLDER}/download.log', level=logging.ERROR,
	format='%(asctime)s - %(levelname)s - %(message)s',
	datefmt='%H:%M:%S %d-%m-%Y', filemode='w'
)


class InternalConverter:
	STORAGE = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../../', 'storage')

	def __init__(self):
		self.prg_fldr = os.path.join(self.STORAGE, 'progress')
		self.dwl_fldr = os.path.join(self.STORAGE, 'downloads')
		self.sbt_fldr = os.path.join(self.STORAGE, 'subtitles')
		self.config = Config()
		self.dfl_lng = self.config.DEFAULT_LANGS
		self.uuid = None
		self.wuid = None
		self.filename = None
		self.download = None
		self.queue_id = None
		self.a_codec = None
		self.v_codec = None
		self.can_convert = False

	@staticmethod
	def _video_file_info(url):
		probe = ffmpeg.probe(url)
		response = {'a_c': probe['streams'][0]['codec_name'], 'v_c': probe['streams'][1]['codec_name'],
					'duration': probe['format']['duration']}
		return response

	@staticmethod
	def _download_subs(sub):
		req = requests.get(sub, timeout=25)
		try:
			return req.content
		except requests.Timeout or requests.ConnectTimeout:
			logging.error('Subtitles downloading timed out.')
			raise ValidationError('common', 'slow_internet_connection')
		except requests.ConnectionError:
			logging.error('Subtitles downloading failed due to bad connection.')
			raise ValidationError('common', 'connection_error')
		finally:
			req.close()

	def _save_subtitles(self, filename, subtitles):
		fp = f'{self.sbt_fldr}/{filename}.vtt'
		with open(fp, 'wb') as file:
			file.write(subtitles)
		return fp

	def queued_downloading(self, queue_id):
		queue = Queue.objects.filter(id=queue_id).first()
		if queue:
			try:
				for episode in queue.episodes:
					self.video(episode.meta.filename, queue.user_uid, queue_id)
				for movie in queue.movies:
					self.video(movie.meta.filename, queue.user_uid, queue_id)
			except Exception as _ex:
				logging.error(f'[ERROR]: {str(_ex)}')

	def video(self, filename, uuid, queue_id=None):
		file = MetaData.objects.filter(filename=filename).first()
		if file:
			print(filename)
			self.uuid = uuid
			self.wuid = {'episodes': file.episode_uid} if file.episode_uid else {'movies': file.media_uid}
			self.filename = file.filename
			self.queue_id = queue_id
			self.can_convert = True
			vfi = self._video_file_info(file.video_source)
			self.a_codec, self.v_codec, runtime = vfi['a_c'], v['v_c'], v['duration']
			download_info = {'user_uid': uuid, 'runtime': runtime}
			download_info.update(
				{'episode_uid': file.episode_uid.uid} if file.episode_uid == 'tv' else {'media_uid': file.media_uid.uid}
			)
			self.download = Downloads.objects.create(download_info)
		else:
			raise ValidationError('common', 'not_found')
		print('Starting converting')
		self._convert(file)

	def finish_downloading(self):
		if self.queue_id:
			queue = Queue.objects.filter(id=self.queue_id).first()
			for media_type, media_instance in self.wuid.items():
				queue[media_type].remove(media_instance)
			self.download.change_state()

	def _convert(self, file):
		v_codec = 'copy' if self.v_codec in ['libx264', 'h264'] else 'libx264'
		sub_path = self._save_subtitles(self.filename, self._download_subs(file.sub)) if file.sub else None
		title = (
			f'{file.episode_uid.media_uid.name} {file.episode_uid.season} сезон {file.episode_uid.episode} '
			f'серия - {file.episode_uid.name}' if file.episode_uid else file.media_uid.name
		)
		video_lang = 'eng' if file.video_lang == '20' else 'rus'
		params = {'c:v': v_codec, 'c:a': 'aac', 'strict': -2, 'format': mp4, 'metadata:s:a:0': f'language={video_lang}',
				  'metadata': f'title={title}'}
		args = ['progress', f'{self.prg_fldr}/{self.filename}.txt', '-loglevel', 'error']
		if sub_path:
			params.update({'c:s': 'mov_text', 'metadata:s:s:0': f'title={self.dfl_lng[file.sub_lang]}:language={file.sub_lang}'})
			args.insert(0, '-i')
			args.insert(1, sub_path)
		try:
			print('No way to roll back!')
			process = (
				ffmpeg
				.input(file.video_source)
				.output(f'{self.dwl_fldr}/{self.filename}.mp4', **params)
				.global_args(*args)
				.overwrite_output()
				.run_async(pipe_stdout=True, pipe_stderr=True)
			)
			for line in process.stderr:
				logging.error(line.decode('utf-8').stript())
			process.wait()
			self._finish_downloading()
			return 'success'
		except Exception as _ex:
			logging.error(f'Converting error: {str(_ex)}')
			return 'error'

