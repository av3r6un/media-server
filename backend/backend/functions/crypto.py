from cryptography.fernet import Fernet


def encrypt_data(key, data):
	return Fernet(key).encrypt(data.encode('utf-8'))


def decrypt_data(key, data):
	return Fernet(key).decrypt(data).decode()

