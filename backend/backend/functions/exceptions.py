import yaml


class ValidationError(BaseException):
	""" :raises when given function is not valid"""

	message = None

	def __init__(self, case, error, **kwargs):
		super(ValidationError, self).__init__()
		self.case = case
		self.error = error
		self._make_error(**kwargs)

	def _make_error(self, **kwargs):
		with open('backend/config/exceptions.yaml', 'r', encoding='utf-8') as file:
			data = yaml.safe_load(file)
		self.message = ' '.join(kwargs.get(word, word) for word in data[self.case][self.error].split())
