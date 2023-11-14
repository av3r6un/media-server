from backend.functions import ValidationError, get_user_info, get_jwt_identity, get_user, create_admin_user
from django_jwt_extended import create_access_token, create_refresh_token, jwt_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpRequest
from django.conf import settings
from authy.models import Users
import json


@require_POST
def authorize(request: HttpRequest):
	if request.method == 'POST':
		create_admin_user()
		json_data = json.loads(request.body.decode('utf-8'))
		user = Users.objects.get(username=json_data.get('username'))
		if user:
			try:
				if user.check_pwd(json_data.get('password')):
					token = create_access_token(identity=user.username)
					rfsh = create_refresh_token(identity=user.username)
					data = user.json()
					data.update({'accs_token': token, 'rfsh_token': rfsh})
					return JsonResponse({'status': 'success', 'body': data})
			except ValidationError as valid:
				return JsonResponse({'status': 'error', 'message': valid.message})
		else:
			return JsonResponse({'status': 'error', 'message': 'Пользователь не найден'})


@jwt_required()
def get_me(request: HttpRequest):
	jwt_token = request.headers.get('Authorization').split()[1]
	try:
		get_user_info(jwt_token)
		return JsonResponse({'status': 'success', 'granted': True})
	except ValidationError as valid:
		return JsonResponse({'status': 'error', 'message': valid.message}), 404


@jwt_required(refresh=True)
@require_POST
def refresh(req: HttpRequest):
	if req.method == 'POST':
		iden = get_jwt_identity(req.headers.get('Authorization').split()[1])
		token = create_access_token(identity=iden)
		return JsonResponse({'status': 'success', 'token': token})


@jwt_required()
@require_POST
def new_user(req: HttpRequest):
	if req.method == 'POST':
		json_data = json.loads(req.body.decode('utf-8'))
		try:
			Users.objects.create(**json_data)
			return JsonResponse({'status': 'success', 'message': 'Пользователь успешно создан'})
		except ValidationError as valid:
			return JsonResponse({'status': 'error', 'message': valid.message})
