import ast
with open('/run/secrets/secret1') as f:
    VRS1 = f.readlines()
    f.close()
with open('/run/secrets/secret2') as f:
    VRS2 = f.readlines()
    f.close()
TwoCaptchaApiKey = VRS1[0].replace('"', '')


def convert_string_to_kwargs(kwargs_string):
    """Безопасное преобразование строки в именованные параметры."""
    kwargs = f'dict({kwargs_string})'
    assert sum(isinstance(node, ast.Call) for node in ast.walk(ast.parse(kwargs))) == 1
    return eval(kwargs)


def db_config():
    """Получение параметров подключение к БД из секретов проекта."""
    return convert_string_to_kwargs(VRS2[0].replace('"', ''))
