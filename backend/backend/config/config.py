from munch import DefaultMunch
import yaml
import os


class Config:
	STORAGE = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../../', 'storage')
	ALLOWED_EXTENSIONS = None

	def __init__(self):
		current_path = os.path.abspath(os.path.dirname(__file__))
		if os.path.exists(os.path.join(current_path, 'settings.yaml')):
			with open(os.path.join(current_path, 'settings.yaml'), 'r', encoding='utf-8') as file:
				data: dict = yaml.safe_load(file)
			self.LANGS = {k: v for k, v in data['LANGS'].items()}
			data.pop('LANGS')
			self.__dict__.update(DefaultMunch.fromDict(data, default=object()))
