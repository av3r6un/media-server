from api.models import MetaData, Queue, Downloads, MediaElements, Episodes
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpRequest
from backend.functions import is_valid_signature, ValidationError
from backend.config import Config
from django.conf import settings
from authy.models import Users
import json

config = Config()

#  /api/cac/meta/{filename}		GET
#  /api/cac/queue/{queue_id}	GET, DELETE
#  /api/cac/download/			POST, PUT


@require_http_methods(['GET'])
def gather_meta(req: HttpRequest, filename):
	if is_valid_signature(req.headers):
		meta = MetaData.objects.filter(filename=filename).first()
		return JsonResponse(meta.cac_response())
	return JsonResponse({'status': 'error', 'message': 'Authorization failed'}), 404


@require_http_methods(['GET', 'DELETE'])
def queue(req: HttpRequest, queue_id):
	if is_valid_signature(req.headers):
		q = Queue.objects.filter_by(id=queue_id).first()
		if req.method == 'GET':
			return JsonResponse(q.cac_response())
		if req.method == 'DELETE':
			data = json.loads(req.body.decode('utf-8'))
			media_uid, episode_uid = data.get('media_uid', None), data.get('episode_uid', None)
			if media_uid:
				q.movies.remove(MediaElements.objects.get(uid=media_uid))
			if episode_uid:
				q.episodes.remove(Episodes.objects.get(uid=episode_uid))
			return JsonResponse({'status': 'success'})
	return JsonResponse({'status': 'error', 'message': 'Authorization failed'}), 404


@require_http_methods(['POST', 'PUT'])
def manage_download(req: HttpRequest):
	if is_valid_signature(req.headers):
		if req.method == 'POST':
			data = json.loads(req.body.decode('utf-8'))
			user = Users.objects.filter(uid=data.get('user_uid')).first()
			user_dwn = Downloads.objects.filter(user_uid=user.uid, media_uid=data.get('media_uid'),
												episode_uid=data.get('episode_uid')).first()
			if user_dwn:
				if user_dwn.stage:
					return JsonResponse({'status': 'error', 'message': 'Already downloaded!', 'msg': 'exists'})
				return JsonResponse({'uid': user_dwn.uid})
			else:
				if data.get('media_uid'):
					data['media_uid'] = MediaElements.objects.filter(uid=data.get('media_uid')).first()
				if data.get('episode_uid'):
					data['episode_uid'] = Episodes.objects.filter(uid=data.get('episode_uid')).first()
				data['user_uid'] = user
				try:
					dwn = Downloads.objects.create(**data)
					return JsonResponse({'uid': dwn.uid})
				except ValidationError as valid:
					print(valid.message)
					return JsonResponse({'status': 'error', 'message': valid.message})
		if req.method == 'PUT':
			data = json.loads(req.body.decode('utf-8'))
			dwn = Downloads.objects.filter(uid=data.get('uid')).first()
			meta = MetaData.objects.filter(uid=data.get('meta_uid')).first()
			dwn.change_stage(data.get('stage'))
			meta.mark_downloaded()
			return JsonResponse({'status': 'success'})
	return JsonResponse({'status': 'error', 'message': 'Authorization failed'}), 404

