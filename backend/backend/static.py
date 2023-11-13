from django.http import HttpRequest, JsonResponse, StreamingHttpResponse, FileResponse, HttpResponse
from datetime import datetime as dt
from django.core.files import File
from django.conf import settings
from authy.models import Users
import base64
import os
import re


def file_iterator(fp, chunk_size=8192):
	with open(fp, 'rb') as file:
		while True:
			chunk = file.read(chunk_size)
			if not chunk:
				break
			yield chunk


def file_serve(req: HttpRequest, path):
	decoded_path = base64.b64decode(path).decode('utf-8')
	filename, uuid, date_string = decoded_path.split('&')
	date = dt.strptime(date_string, '%Y-%m-%d %H')
	user = Users.objects.filter(uid=uuid).first()
	if date > dt.now() and user:
		requested = os.path.join(settings.MEDIA_ROOT, 'downloads', filename)
		if os.path.exists(requested):
			chunk_size = 8192 * 10
			with open(requested, 'rb') as file:
				response = HttpResponse(content_type='video/mp4')
				response['Accept-Ranges'] = 'bytes'
				range_header = req.headers.get('Range')
				if range_header:
					start, end = range_header.split('=')[1].split('-')
					start = int(start)
					end = int(end) if end else int(os.path.getsize(requested) - 1)
					response['Content-Range'] = f'bytes {start}-{end}/{os.path.getsize(requested)}'
					file.seek(start)
					response['Content-Length'] = end - start + 1
					while start <= end:
						bytes_to_read = min(chunk_size, end - start + 1)
						data = file.read(bytes_to_read)
						response.write(data)
						start += bytes_to_read
				else:
					response['Content-Length'] = os.path.getsize(requested)
					response.write(file.read())
				return response
		else:
			return JsonResponse({'status': 'error', 'message': 'File Not Found'}, status=404)
	return JsonResponse({'status': 'error'}, status=404)


def subtitles_serve(req: HttpRequest, path, filename):
	decoded_path = base64.b64decode(path).decode('utf-8')
	fname, uuid, date_string = decoded_path.split('&')
	date = dt.strptime(date_string, '%Y-%m-%d %H')
	user = Users.objects.filter(uid=uuid).first()
	if date > dt.now() and user and filename.replace('.vtt', '') == fname:
		requested = os.path.join(settings.MEDIA_ROOT, "subtitles", filename)
		if os.path.exists(requested):
			response = FileResponse(open(requested, 'rb'))
			response['Accept-Ranges'] = 'bytes'
			response['Content-Type'] = 'text/vtt'
			response['Content-Disposition'] = f'attachment'
			return response
		else:
			return JsonResponse({'status': 'error', 'message': 'File Not Found'}, status=404)
	return JsonResponse({'status': 'error'}, status=404)
