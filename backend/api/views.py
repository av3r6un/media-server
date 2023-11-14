from .models import MediaElements, MediaImages, Episodes, EpisodeImages, MetaData, Watching, Downloads, Queue
from api.functions import parse_item, Voices, MetaEngine, MediaEngine, AdviceEngine
from backend.functions import get_user_info, ValidationError, get_user, is_seen
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse, HttpRequest
from django_jwt_extended import jwt_required
from backend.config import Config
import requests
import json

config = Config()


@jwt_required()
@require_http_methods(['GET', 'POST'])
def media_elements(req: HttpRequest, media_type: str):
	jwt_token = req.headers.get('Authorization').split()[1]
	current_user = get_user(jwt_token)
	if media_type not in config.MEDIA_TYPES:
		return JsonResponse({'status': 'error', 'message': 'Not Found'}), 404
	if req.method == 'POST':
		json_data = json.loads(req.body.decode('utf-8'))
		json_data.update({'media_type': media_type})
		try:
			item = parse_item(**json_data)
			return JsonResponse({'status': 'success', 'body': {'uid': item}})
		except ValidationError as valid:
			return JsonResponse({'status': 'error', 'message': valid.message})
	if req.method == 'GET':
		all_items = MediaElements.objects.filter(age__lt=current_user.age, media_type=media_type).all()
		items = [a.small_info(current_user.uid) for a in all_items]
		return JsonResponse({'status': 'success', 'body': items})


@jwt_required()
def search(req: HttpRequest):
	data = {'query': req.GET.get('keyword', None)}
	extra = {'imageStorage': config.IMAGE_STORAGE}
	if data['query']:
		resp = requests.post(config.SEARCH_ENGINE, data=data, timeout=15)
		try:
			r = resp.json()
			# duplicates = find_duplicates()
			return JsonResponse({'status': 'success', 'body': r.get('results'), 'extra': extra})
		except Exception as _ex:
			print(_ex)
			return JsonResponse({'status': 'error'})
	else:
		return JsonResponse({'status': 'error'}), 422


@jwt_required()
def all_data(req: HttpRequest):
	jwt_token = req.headers.get('Authorization').split()[1]
	current_user = get_user(jwt_token)
	all_items = MediaElements.objects.filter(age__lt=current_user.age).all()
	items = [a.short_json() for a in all_items]
	return JsonResponse({'status': 'success', 'body': items})


@jwt_required()
def media_info(req: HttpRequest, uid):
	cu = get_user(req.headers.get('Authorization').split()[1])
	media = MediaElements.objects.filter(uid=uid).first()
	media_basic = media.json()
	if media.media_type == 'tv':
		media_basic['extra'] = media.episodes_info(cu.uid)
	else:
		media_basic['continue'] = media.where_to_continue(cu.uid)
	extra = {'voices': config.VOICES, 'langs': config.LANGS}
	if media:
		return JsonResponse({'status': 'success', 'body': media_basic, 'extra': extra})


@jwt_required()
def episode_info(req: HttpRequest, uid):
	cu = get_user(req.headers.get('Authorization').split()[1])
	ep = Episodes.objects.filter(uid=uid).first()
	if not ep:
		return JsonResponse({'status': 'error', 'message': 'Not Found'}), 404
	this_media = MediaElements.objects.filter(uid=ep.media_uid.uid).first()
	watch = this_media.gather_episode_info(ep.uid, ep.episode, ep.season, neighbors=req.GET.get('nghbr'))
	watch['episode']['continue'] = ep.continue_info(cu.uid)
	extra = {'langs': config.LANGS, 'voices': config.VOICES, 'default_langs': config.DEFAULT_LANGS}
	return JsonResponse({'status': 'success', 'body': watch, 'extra': extra})


@jwt_required()
def parse_voices(req: HttpRequest, media_type):
	params = {
		'imdb_id': req.GET.get('imdb_id'), 'episode': req.GET.get('episode'), 'season': req.GET.get('season'),
		'media_type': media_type, 'accepted_voices': config.VOICES
	}
	try:
		voices = Voices(**params)
		return JsonResponse({'status': 'success', 'body': voices.result})
	except ValidationError as valid:
		return JsonResponse({'status': 'error', 'message': valid.message})


@jwt_required()
def parse_meta(req: HttpRequest, media_type, imdb_id):
	params = {
		'media_type': media_type, 'imdb_id': imdb_id, 'voice': req.GET.get('voice'),
		'sub_lang': req.GET.get('sub') if req.GET.get('sub') != 'null' else None,
		'episode': req.GET.get('e'), 'season': req.GET.get('s')
	}
	try:
		media_meta = MetaEngine()
		result = media_meta.get_meta(**params)
		return JsonResponse(result)
	except ValidationError as valid:
		return JsonResponse({'status': 'error', 'message': valid.message})


@jwt_required()
@require_POST
def edit_meta(req: HttpRequest, media_type, uid):
	current = {
		'tv': {'current': Episodes.objects.filter(uid=uid).first(),
			   'meta': MetaData.objects.filter(episode_uid=uid).first()},
		'movie': {'current': MediaElements.objects.filter(uid=uid).first(),
				  'meta': MetaData.objects.filter(media_uid=uid).first()},
	}
	if req.method == 'POST':
		request_data = req.POST if media_type == 'tv' else json.loads(req.body.decode('utf-8'))
		params = {
			'video_source': request_data.get('videoSource'), 'video_lang': request_data.get('videoLang'),
			'sub': request_data.get('sub'), 'sub_lang': request_data.get('subLang'),
		}
		try:
			if current[media_type]['meta']:
				if req.FILES.get('preview'):
					current[media_type]['current'].edit(preview=req.FILES.get('preview'))
				current[media_type]['meta'].edit(**params)
			else:
				params.update(
					{'episode_uid': current[media_type]['current']}
					if media_type == 'tv' else {'media_uid': current[media_type]['current']}
				)
				MetaData.objects.create(**params)
			return JsonResponse({'status': 'success'})
		except ValidationError as valid:
			return JsonResponse({'status': 'error', 'message': valid.message})


@require_POST
def watch_beacon(req: HttpRequest):
	if req.method == 'POST':
		data = json.loads(req.body.decode('utf-8'))
		small_data = {'timestamp': data['player']['time'], 'duration': data['player']['duration']}
		edit_data = {'timestamp': small_data.get('timestamp'),
					 'seen': data['player']['seen'] if data['player'].get('seen') else is_seen(**small_data)}

		media_type = data.get('mediaType')
		current_user = get_user(data.get('headers').get('Authorization').split()[1])
		model_data = {'user_uid': current_user}
		model_data.update(edit_data)
		if not current_user:
			return JsonResponse({'status': 'error', 'message': 'User Not Found'}), 404
		current = {
			'tv': {'instance': Episodes.objects.filter(uid=data['uid']).first(),
				   'watch': Watching.objects.filter(user_uid=current_user.uid, episode_uid=data['uid']).first()},
			'movie': {'instance': MediaElements.objects.filter(uid=data['uid']).first(),
					  'watch': Watching.objects.filter(user_uid=current_user.uid, media_uid=data['uid']).first()}
		}
		model_data.update({'media_uid': None, 'episode_uid': current[media_type]['instance']}
						  if media_type == 'tv' else {'media_uid': current[media_type]['instance'], 'episode_uid': None})
		if model_data['media_uid'] and model_data['seen']:
			current_user.mark_seen(model_data['media_uid'])
		if not model_data['timestamp']:
			return JsonResponse({'status': 'error', 'message': 'Poor body'}, status=202)
		if not current[media_type]['watch']:
			try:
				Watching.objects.create(**model_data)
			except ValidationError as valid:
				print(f'[BEACON]: {valid.message}')
				return JsonResponse({'status': 'error', 'message': valid.message})
		else:
			current[media_type]['watch'].edit(**edit_data)
			return JsonResponse({'ok': True})


@jwt_required()
@require_POST
def mark_media_seen(req: HttpRequest, uid):
	if req.method == 'POST':
		current_user = get_user(req.headers.get('Authorization').split()[1])
		media = MediaElements.objects.filter(uid=uid).first()
		obj = 'Фильм' if media.media_type == 'movie' else 'Сериал'
		if media:
			try:
				current_user.mark_seen(media)
				return JsonResponse({'status': 'success', 'message': f'{obj} успешно добавлен в Просмотрено.'})
			except Exception as _ex:
				print(str(_ex))
				return JsonResponse({'status': 'error', 'message': str(_ex)})
		else:
			return JsonResponse({'status': 'error', 'message': 'Object Not Found'}, status=404)


@jwt_required()
@require_http_methods(['POST', 'GET'])
def user_info(req: HttpRequest):
	current_user = get_user(req.headers.get('Authorization').split()[1])
	if req.method == 'POST':
		json_data = {'username': req.POST.get('username'), 'auto_search': req.POST.get('auto_search'),
					 'voice': req.POST.get('voice'), 'avatar': req.FILES.get('avatar') if req.FILES else None,
					 'share_downloads': req.POST.get('share_downloads')}
		try:
			current_user.edit(**json_data)
			return JsonResponse({'status': 'success', 'message': 'Профиль успешно изменён'})
		except ValidationError as valid:
			return JsonResponse({'status': 'error', 'message': valid.message})
	watchings = [a.media_uid if a.media_uid else a.episode_uid for a in
				 Watching.objects.filter(user_uid=current_user.uid, seen=True).order_by('-datetime').all()]
	user_dwn = [a.json() for a in Downloads.objects.filter(user_uid=current_user.uid).order_by('-datetime').all()]
	history = [a.short_info() for a in watchings][:5]
	queue = Queue.objects.filter(user_uid=current_user.uid).first()
	queue_list = queue.pretty()['queue'][:5] if queue else []
	response = {'history': history, 'downloads': user_dwn[:5], 'queue': queue_list}
	extra = {'voices': config.VOICES, 'user_info': current_user.json()}
	extra.update({'queue': queue.id}) if queue else None
	return JsonResponse({'status': 'success', 'body': response, 'extra': extra})


@jwt_required()
@require_http_methods(['POST', 'GET', 'DELETE'])
def user_queue_info(req: HttpRequest):
	current_user = get_user(req.headers.get('Authorization').split()[1])
	queue = Queue.objects.filter(user_uid=current_user.uid).first()
	dbs = {'episode': {'table': Episodes, 'items': [], 'objects': queue.episodes},
		   'movie': {'table': MediaElements, 'items': [], 'objects': queue.movies}}
	if req.method == 'DELETE':
		json_data = json.loads(req.body.decode('utf-8'))
		if not queue:
			return JsonResponse({'status': 'error', 'message': 'Queue Not Found'}, status=404)
		obj = dbs[json_data['type']]['table'].objects.filter(uid=json_data['uid']).first()
		try:
			dbs[json_data['type']]['objects'].remove(obj)
			return JsonResponse({'status': 'success', 'message': 'Очередь успешно изменена.'})
		except Exception as _ex:
			print(str(_ex))
			return JsonResponse({'status': 'error', 'message': str(_ex)})
	if req.method == 'POST':
		json_data = json.loads(req.body.decode('utf-8'))
		queue_current = queue.current_items() if queue else []
		if not queue:
			queue = Queue.objects.create(user_uid=current_user)
		for uq_item in json_data:
			if uq_item[uq_item['type']]['uid'] not in queue_current:
				dbs[uq_item['type']]['items'].append(
					dbs[uq_item['type']]['table'].objects.filter(uid=uq_item[uq_item['type']]['uid']).first()
				)
		try:
			queue.add_ids(dbs['episode']['items'], dbs['movie']['items'])
			return JsonResponse({'status': 'success'})
		except ValidationError as valid:
			return JsonResponse({'status': 'error', 'message': valid.message})
	if not queue:
		return JsonResponse({'status': 'success', 'body': []})
	return JsonResponse({'status': 'success', 'body': queue.json()})


@jwt_required()
@require_POST
def clear_user_queue(req: HttpRequest):
	if req.method == 'POST':
		current_user = get_user(req.headers.get('Authorization').split()[1])
		queue = Queue.objects.filter(user_uid=current_user.uid).first()
		try:
			queue.clear_queue()
			return JsonResponse({'status': 'success', 'message': 'Очередь успешно очищена'})
		except Exception as _ex:
			return JsonResponse({'status': 'error', 'message': str(_ex)})


@jwt_required()
@require_http_methods(['GET', 'DELETE'])
def manage_user_downloads(req: HttpRequest):
	current_user = get_user(req.headers.get('Authorization').split()[1])
	downloads = Downloads.objects.filter(user_uid=current_user.uid).all()
	if req.method == 'DELETE':
		json_data = json.loads(req.body.decode('utf-8'))
		if json_data.get('type') == 'all':
			try:
				for d in downloads:
					d.clear(current_user)
				return JsonResponse({'status': 'success', 'message': 'Загрузки успешно очищены'})
			except ValidationError as valid:
				return JsonResponse({'status': 'error', 'message': valid.message})
		else:
			try:
				for d in downloads:
					if d.uid == json_data.get('uid'):
						d.clear(current_user)
				return JsonResponse({'status': 'success', 'message': 'Загрузка успешно удалена'})
			except ValidationError as valid:
				return JsonResponse({'status': 'error', 'message': valid.message})
	ds = [a.json() for a in downloads]
	return JsonResponse({'status': 'success', 'body': ds})


@jwt_required()
@require_POST
def download(req: HttpRequest):
	current_user = get_user(req.headers.get('Authorization').split()[1])
	if req.method == 'POST':
		data = json.loads(req.body.decode('utf-8'))
		me = MediaEngine()
		if data.get('type') == 'multi':
			me_info = me.start_multi(data.get('queue_id'), current_user.uid)
		elif data.get('type') == 'ofq':
			me_info = me.start_one_form_queue(data.get('queue_id'), data.get('uid'), current_user.uid)
		else:
			me_info = me.start(data.get('filename'), current_user.uid)
		return JsonResponse({'status': 'success', 'message': me_info['message'], 'extra': me_info['thread_name']})


@jwt_required()
@require_http_methods(['GET'])
def send_advice(req: HttpRequest):
	current_user = get_user(req.headers.get('Authorization').split()[1])
	ae = AdviceEngine(current_user)
	return JsonResponse({'status': 'success', 'body': ae.suggestion})
